#!/usr/bin/env python3
"""Refresh the four guided teaching snapshots from Crossref's public API.

Run from any directory with ``python scripts/build_guided_snapshots.py``.
Requires ``requests`` and network access. Each case uses one bounded first-page
search (with retries on failures). Search order and metadata can change.
Only corpus CSVs and logs are written; the case manifest is not rewritten.

Abstracts are retained only under the conservative deposited-license policy
documented in each log. A CC BY or CC0 URL is not proof that its terms apply to
every element of an abstract: downstream users must verify the rights, supply
the appropriate attribution for CC BY, and follow any other applicable terms.
Unfiltered HTTP bodies are never saved; only their SHA-256 hashes are recorded.
References are JSON arrays of distinct explicit DOI identifiers. Other raw
reference data are not retained. Normalization mirrors the Day 1 helper without
importing its Streamlit page.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import unquote, urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "guided_fixed"
ENDPOINT = "https://api.crossref.org/works"
PER_PAGE = 50
SELECT = "DOI,title,author,published,container-title,abstract,reference,license"
COLUMNS = ["ID", "DOI", "Title", "Year", "Authors", "Venue", "Abstract",
           "Abstract_License", "Citations", "Concepts", "References", "Source"]
LICENSE_URL = "https://www.crossref.org/documentation/retrieve-metadata/"

ABSTRACT_POLICY = (
    "Keep a cleaned abstract only when the same Crossref item has a valid DOI and explicitly discloses "
    "an exact creativecommons.org CC BY (versions 1.0, 2.0, 2.5, 3.0, 4.0) or "
    "CC0 1.0 license URL in the standard license or legalcode form. Exclude NC, "
    "ND, other terms and ambiguous URLs. The license content-version must be "
    "vor, unspecified, or absent; TDM-only and accepted-manuscript-only entries "
    "are not used. Any supplied start date must be parseable and not in the "
    "future. Record the deposited URL for attribution. Metadata is not proof "
    "that the license covers the abstract or all third-party content; users "
    "must verify applicability and comply with all terms, including attribution."
)

# These are deliberately simple OR lists of case-insensitive substrings,
# applied to title + abstract, not claims of eligibility or empirical design.
CASES = [
    {
        "key": "ex1_health",
        "label": "Health Sciences: Health Inequalities in Chronic Disease Care",
        "question": "What does the empirical literature say about socioeconomic health inequalities in the care and outcomes of patients with chronic diseases such as diabetes, hypertension, and cardiovascular disease?",
        "query": "health inequalities diabetes care socioeconomic",
        "inclusion_terms": ["diabetes", "hypertension", "cardiovascular", "chronic disease"],
        "exclusion_terms": [],
        "corpus_file": "ex1_health_corpus.csv",
        "log_file": "ex1_health_log.json",
    },
    {
        "key": "ex2_ubi",
        "label": "Social Sciences: Universal Basic Income Policy Outcomes",
        "question": "What are the empirically measured outcomes of Universal Basic Income programmes and pilots in terms of employment, poverty, and well-being?",
        "query": "universal basic income policy evaluation employment outcomes",
        "inclusion_terms": ["basic income", "guaranteed income"],
        "exclusion_terms": [],
        "corpus_file": "ex2_ubi_corpus.csv",
        "log_file": "ex2_ubi_log.json",
    },
    {
        "key": "ex3_microplastics",
        "label": "Science / Engineering: Microplastic Pollution in Aquatic Environments",
        "question": "What does the experimental literature report about the concentration, distribution, and ecological impact of microplastic pollution in aquatic environments?",
        "query": "microplastics marine fish freshwater environmental health",
        "inclusion_terms": ["microplastic"],
        "exclusion_terms": [],
        "corpus_file": "ex3_microplastics_corpus.csv",
        "log_file": "ex3_microplastics_log.json",
    },
    {
        "key": "ex4_csr",
        "label": "Management / Business: Corporate Social Responsibility and Firm Financial Performance",
        "question": "What is the empirical evidence on the relationship between Corporate Social Responsibility activities and firm financial performance?",
        "query": "corporate social responsibility firm financial performance empirical",
        "inclusion_terms": ["corporate social responsibility", "csr"],
        "exclusion_terms": [],
        "corpus_file": "ex4_csr_corpus.csv",
        "log_file": "ex4_csr_log.json",
    },
]


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _first_text(value):
    if isinstance(value, str):
        return _text(value)
    if not isinstance(value, list):
        return ""
    return next((text for entry in value if (text := _text(entry))), "")


def _doi(value):
    """Apply the Day 1 helper's DOI parsing; do not infer missing DOIs."""
    if not isinstance(value, str):
        return ""
    doi = re.sub(r"^doi:\s*", "", value.strip(), flags=re.IGNORECASE)
    if any(not char.isprintable() or char.isspace() for char in doi):
        return ""
    if re.match(r"^https?://", doi, flags=re.IGNORECASE):
        try:
            parsed = urlsplit(doi)
            if (parsed.netloc.casefold() not in {"doi.org", "dx.doi.org"}
                    or parsed.query or parsed.fragment or not parsed.path.startswith("/")
                    or re.search(r"%(?![0-9a-fA-F]{2})", parsed.path)):
                return ""
            doi = unquote(parsed.path[1:], encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return ""
    if (not re.fullmatch(r"10\.[0-9]+/.+", doi, flags=re.IGNORECASE)
            or any(not char.isprintable() or char.isspace() for char in doi)):
        return ""
    return f"doi:{doi.lower()}"


def _references(item):
    entries = item.get("reference", [])
    if not isinstance(entries, list):
        entries = []
    identifiers = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        identifier = _doi(entry.get("DOI")) or _doi(entry.get("doi"))
        if identifier and identifier not in seen:
            identifiers.append(identifier)
            seen.add(identifier)
    return json.dumps(identifiers, ensure_ascii=False) if identifiers else ""


def _clean_abstract(value):
    """Use exactly the same cleanup for captured and supplementary text."""
    value = _text(value)
    return " ".join(html.unescape(re.sub(r"</?[A-Za-z][^>]*>", " ", value)).split())


def _valid_license_url(value):
    """Accept only unambiguous canonical CC BY/CC0 or legalcode URLs."""
    if (not isinstance(value, str) or not value or value != value.strip()
            or "?" in value or "#" in value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if (parsed.scheme not in {"http", "https"}
            or parsed.netloc.casefold() != "creativecommons.org"
            or parsed.query or parsed.fragment):
        return False
    return bool(re.fullmatch(
        r"/(?:licenses/by/(?:1\.0|2\.0|2\.5|3\.0|4\.0)|publicdomain/zero/1\.0)"
        r"(?:/legalcode)?/?", parsed.path
    ))


def _license_started(entry, as_of):
    """Reject malformed or future effective dates when a start is provided."""
    start = entry.get("start")
    if start is None:
        return True
    if not isinstance(start, dict):
        return False
    stamp = start.get("date-time")
    if stamp is not None:
        if not isinstance(stamp, str):
            return False
        try:
            date = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if date.tzinfo is None:
                return False
            return date <= as_of
        except ValueError:
            return False
    parts = start.get("date-parts")
    if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], list) or len(parts[0]) != 3:
        return False
    try:
        year, month, day = parts[0]
        if any(not isinstance(x, int) or isinstance(x, bool) for x in (year, month, day)):
            return False
        return datetime(year, month, day, tzinfo=timezone.utc) <= as_of
    except (TypeError, ValueError, OverflowError):
        return False


def _license_entry(item, as_of):
    """Return a qualifying deposited license, never a TDM/AM-only license."""
    entries = item.get("license")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        version = entry.get("content-version")
        if (version not in (None, "", "unspecified", "vor")
                or not _valid_license_url(entry.get("URL"))
                or not _license_started(entry, as_of)):
            continue
        return entry
    return None


def _license_evidence(doi, abstract, entry):
    """Log only the selected license metadata and a hash, not another abstract."""
    return {"doi": doi, "abstract_sha256": _sha256(abstract.encode("utf-8")),
            "license": {key: entry[key] for key in ("URL", "content-version", "start", "delay-in-days")
                        if key in entry}}


def _row(item, as_of=None):
    authors = item.get("author", [])
    authors = authors if isinstance(authors, list) else []
    names = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        name = " ".join(filter(None, (_text(author.get("family")), _text(author.get("given")))))
        # Crossref can deposit a collective author as name rather than family/given.
        name = name or _text(author.get("name"))
        if name:
            names.append(name)
    date = item.get("published", {})
    date = date if isinstance(date, dict) else {}
    dates = date.get("date-parts", [])
    parts = dates[0] if isinstance(dates, list) and dates and isinstance(dates[0], list) else []
    year = parts[0] if parts else ""
    if not isinstance(year, (str, int)) or isinstance(year, bool):
        year = ""
    abstract = _clean_abstract(item.get("abstract"))
    doi = _text(item.get("DOI"))
    license_entry = _license_entry(item, as_of or datetime.now(timezone.utc)) if abstract and _doi(doi) else None
    if license_entry is None:
        abstract = ""
    return {
        "ID": doi,
        "DOI": doi,
        "Title": _first_text(item.get("title")),
        "Year": str(year),
        "Authors": "; ".join(names),
        "Venue": _first_text(item.get("container-title")),
        "Abstract": abstract,
        "Abstract_License": license_entry["URL"] if license_entry else "",
        "Citations": "",
        "Concepts": "",
        "References": _references(item),
        "Source": "Crossref",
    }


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _matches(row, terms):
    """Match the guided renderer's case/whitespace-normalized field search."""
    fields = [" ".join(row[field].split()).casefold() for field in ("Title", "Abstract")]
    return any(" ".join(term.split()).casefold() in field
               for term in terms if term.strip() for field in fields)


def _fetch(case):
    params = {"query": case["query"], "rows": PER_PAGE, "select": SELECT}
    attempts = []
    for attempt in range(1, 4):
        started = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        try:
            response = requests.get(ENDPOINT, params=params, timeout=60,
                                    headers={"User-Agent": "guided-review-snapshots/1.0"})
            response.raise_for_status()
            received_at = datetime.now(timezone.utc)
            attempts.append({"started_at_utc": started, "finished_at_utc": received_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                             "http_status": response.status_code})
            break
        except requests.RequestException as exc:
            attempts.append({"started_at_utc": started,
                             "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                             "error_type": type(exc).__name__})
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    retrieved = received_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    payload = response.json()
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("items"), list):
        raise ValueError(f"{case['key']}: unexpected Crossref response")
    items = message["items"]
    if any(not isinstance(item, dict) for item in items):
        raise ValueError(f"{case['key']}: non-object Crossref item; snapshot not written")
    rows = [_row(item, received_at) for item in items]
    total = message.get("total-results")
    if not isinstance(total, int) or isinstance(total, bool) or total < len(rows):
        raise ValueError(f"{case['key']}: invalid result count")
    if not 40 <= len(rows) <= PER_PAGE:
        raise ValueError(f"{case['key']}: expected 40–50 returned records, got {len(rows)}")
    if sum(bool(row["Title"]) for row in rows) < 2:
        raise ValueError(f"{case['key']}: fewer than two records have titles")
    matches = sum(
        _matches(row, case["inclusion_terms"])
        and not _matches(row, case["exclusion_terms"])
        for row in rows
    )
    if matches < 2:
        raise ValueError(f"{case['key']}: fewer than two title/abstract heuristic matches")
    included_with_abstract = sum(
        bool(row["Abstract"]) and _matches(row, case["inclusion_terms"])
        and not _matches(row, case["exclusion_terms"])
        for row in rows
    )
    if not included_with_abstract:
        raise ValueError(f"{case['key']}: no heuristic-included record has a qualifying licensed abstract")

    csv_data = _csv_bytes(rows)
    license_evidence = [
        _license_evidence(row["DOI"], row["Abstract"], _license_entry(item, received_at))
        for row, item in zip(rows, items) if row["Abstract"]
    ]
    log = {
        "case_key": case["key"],
        "source": "Crossref",
        "endpoint": ENDPOINT,
        "retrieved_at_utc": retrieved,
        "query": case["query"],
        "parameters": params,
        "request_url": response.url,
        "request_method": "GET",
        "request_attempts": attempt,
        "request_attempt_details": attempts,
        "pages_fetched": 1,
        "pagination": "First page only; no additional pages requested.",
        "scope": "Provider-specific plain-text relevance search; no Boolean interpretation assumed.",
        "filters": [],
        "returned": len(rows),
        "total_matches": total,
        "possibly_truncated": total > len(rows),
        "field_coverage": {field: sum(bool(row[field]) for row in rows)
                           for field in ("DOI", "Title", "Year", "Authors", "Venue", "Abstract", "Abstract_License", "References")},
        "corpus_file": case["corpus_file"],
        "corpus_sha256": _sha256(csv_data),
        "raw_response_file": None,
        "raw_response_sha256": _sha256(response.content),
        "raw_response_retention": "Hash only; no unfiltered raw response body is retained. The hash cannot reconstruct the response or independently prove its contents.",
        "license_screening": {
            "policy": ABSTRACT_POLICY,
            "source": "License, DOI and abstract selected together in the original Crossref request; each license comes from the same item as its abstract.",
            "abstracts_recorded_in_response": sum(bool(_clean_abstract(item.get("abstract"))) for item in items),
            "retained_abstracts": len(license_evidence),
            "missing_or_reuse_unconfirmed": len(rows) - len(license_evidence),
            "included_records_with_licensed_abstract": included_with_abstract,
            "retained_license_evidence": license_evidence,
        },
        "screening": {
            "method": "Case-insensitive, whitespace-normalized substring match on title or abstract: at least one inclusion term and no exclusion term. Human review is required.",
            "inclusion_terms": case["inclusion_terms"],
            "exclusion_terms": case["exclusion_terms"],
            "matching_records": matches,
            "excluded_records": len(rows) - matches,
        },
        "field_notes": {
            "References": "JSON array of unique explicit reference DOIs, normalized as doi: identifiers; a blank means no usable DOI was supplied, not that the work has no references. Other raw reference entries are not retained.",
            "Concepts": "Blank: not supplied by this Crossref request.",
            "Citations": "Blank: not supplied by this Crossref request.",
            "Abstract": "JATS/XML tags are stripped for display. A blank means missing or reuse-unconfirmed; it does not establish that the provider lacked an abstract. Withholding may affect teaching-screen decisions.",
            "Abstract_License": "URL from the item's deposited license metadata for the retained abstract. Use the title, authors and DOI for attribution and verify applicability and terms independently.",
        },
        "license": "Crossref bibliographic metadata and abstracts may have different rights. Abstracts can retain publisher or author copyright; do not assume they are CC0. The deposited license metadata is an indicator, not independent verification of rights or scope. Attribute CC BY material and verify the applicable license and any third-party rights.",
        "license_info_url": LICENSE_URL,
        "limitations": "A single bounded relevance-ranked page is a teaching sample, not an exhaustive or validated systematic-review search. Coverage and record fields vary; no publication-type, date, or abstract filter was applied to the API query. Abstracts were filtered locally for reuse and missing text can change screening outcomes.",
    }
    return csv_data, log


def _discard_stale_response(case):
    """Remove a legacy raw archive, keeping any existing capture log truthful."""
    raw_name = case["key"] + "_response.json.gz"
    path = OUT / raw_name
    if not path.exists():
        return
    path.unlink()
    log_path = OUT / case["log_file"]
    if not log_path.exists():
        return
    log = json.loads(log_path.read_text(encoding="utf-8"))
    if isinstance(log, dict) and log.get("raw_response_file") == raw_name:
        log["raw_response_file"] = None
        log["raw_response_retention"] = (
            "Hash only; the legacy raw response archive was deleted. Any gzip "
            "hash is historical only; no raw body is retained. Hashes cannot "
            "reconstruct the response or independently prove its contents."
        )
        notes = log.get("field_notes")
        if isinstance(notes, dict) and isinstance(notes.get("References"), str):
            notes["References"] = notes["References"].replace(
                "The raw response retains all deposited reference entries.",
                "Other raw reference entries are not retained."
            )
        log_path.write_bytes(_json_bytes(log))


def main():
    manifest = json.loads((OUT / "cases.json").read_text(encoding="utf-8"))
    if manifest != CASES:
        raise ValueError("The fixed cases manifest differs from the builder; refusing to refresh mismatched data.")
    for case in CASES:
        _discard_stale_response(case)
    results = []
    for index, case in enumerate(CASES):
        if index:
            time.sleep(1.1)  # Public-pool limit is commonly 1 request per second.
        print(f"Retrieving {case['key']} from Crossref...", flush=True)
        results.append((case, *_fetch(case)))
    # Avoid partially refreshing the checked-in set if any retrieval fails.
    OUT.mkdir(parents=True, exist_ok=True)
    for case, csv_data, log in results:
        (OUT / case["corpus_file"]).write_bytes(csv_data)
        (OUT / case["log_file"]).write_bytes(_json_bytes(log))
        print(f"{case['key']}: {log['returned']} records; {log['screening']['matching_records']} heuristic matches; total {log['total_matches']}; truncated={log['possibly_truncated']}", flush=True)
    print(f"Wrote snapshots to {OUT}", flush=True)


if __name__ == "__main__":
    main()
