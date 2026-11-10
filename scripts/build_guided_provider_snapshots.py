#!/usr/bin/env python3
"""Capture bounded, anonymous provider-specific guided teaching samples.

Run ``python scripts/build_guided_provider_snapshots.py`` from any directory.
The program refreshes one page per fixed case and provider, retries failures,
and reports any failed combinations without fabricating or substituting data.
``--case`` and ``--provider`` restrict a refresh; ``--verify`` performs an
entirely offline audit. Re-running refreshes the same filenames in place; search
results and timestamps can legitimately change. No API keys or prompts are used.

Output: data/guided_provider_snapshots/{case_key}__{provider_slug}.csv and
matching .json, where provider_slug is openalex, europe_pmc or openaire.
CSV is UTF-8, with guided_provider_search.COLUMNS followed by Publication Type
and Abstract Source. Empty metadata is written as an empty field. References
are the explicit identifiers supplied by the existing provider converters.
All abstracts/descriptions are withheld, regardless of apparent license.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import tempfile
import time
from urllib.parse import parse_qsl, urlsplit
from unittest.mock import patch

import pandas as pd
import requests
from requests.auth import AuthBase

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import guided_provider_search as guided  # noqa: E402

OUT = ROOT / "data" / "guided_provider_snapshots"
CASES_PATH = ROOT / "data" / "guided_fixed" / "cases.json"
PROVIDER_SLUGS = {"OpenAlex": "openalex", "Europe PMC": "europe_pmc", "OpenAIRE": "openaire"}
ENDPOINTS = {
    "OpenAlex": "https://api.openalex.org/works",
    "Europe PMC": guided.EUROPE_PMC_ENDPOINT,
    "OpenAIRE": guided.openaire_client.ENDPOINT,
}
COLUMNS = guided.COLUMNS + ["Publication Type", "Abstract Source"]
WITHHELD_SOURCE = "Withheld in this capture; provider availability not assessed"
RETRIES = 3


class AnonymousAuth(AuthBase):
    """Prevent requests from automatically attaching netrc credentials."""
    def __call__(self, request):
        request.headers.pop("Authorization", None)
        return request


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_cases():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("Invalid fixed cases manifest")
    by_key = {case["key"]: case for case in cases}
    if len(by_key) != len(cases) or set(by_key) != set(guided.GUIDED_QUERIES):
        raise ValueError("Fixed case manifest and provider query keys differ")
    for case in cases:
        for field in ("inclusion_terms", "exclusion_terms"):
            if not isinstance(case.get(field), list) or any(not isinstance(x, str) for x in case[field]):
                raise ValueError(f"Invalid {field} for {case['key']}")
    return by_key


def filenames(case_key, provider):
    stem = f"{case_key}__{PROVIDER_SLUGS[provider]}"
    return stem + ".csv", stem + ".json"


def expected_request(case_key, provider):
    query = guided.guided_query(case_key, provider)
    if provider == "OpenAlex":
        params = {"search.title_and_abstract.exact": query, "per-page": guided.PAGE_SIZE,
                  "cursor": "*", "select": guided.OPENALEX_SELECT}
    elif provider == "Europe PMC":
        params = {"query": query, "resultType": "core", "pageSize": guided.PAGE_SIZE,
                  "format": "json", "cursorMark": "*"}
    elif provider == "OpenAIRE":
        params = {"search": query, "type": "publication", "pageSize": guided.PAGE_SIZE, "cursor": "*"}
    else:
        raise ValueError("Unsupported provider")
    return query, ENDPOINTS[provider], params


def nonnegative_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


def raw_count(provider, response):
    """Count objects actually received without saving the response body."""
    if not 200 <= response.status_code < 300:
        return None
    try:
        data = response.json()
        if not isinstance(data, dict):
            return None
        if provider == "OpenAlex":
            records = data.get("results")
        elif provider == "Europe PMC":
            result_list = data.get("resultList")
            records = result_list.get("result") if isinstance(result_list, dict) else None
        else:
            records = data.get("results")
        return len(records) if isinstance(records, list) else None
    except (TypeError, ValueError):
        return None


def capture_once(case_key, provider, attempts):
    """Make one anonymous request and verify the actual prepared parameters."""
    query, endpoint, params = expected_request(case_key, provider)
    actual_calls = []
    real_get = requests.get

    def tracked_get(url, **kwargs):
        started = utc_now()
        # Only a single expected URL and its known request parameters are allowed.
        if url != endpoint or kwargs.get("params") != params or actual_calls:
            raise ValueError("Unexpected provider request or additional page")
        kwargs["auth"] = AnonymousAuth()  # no netrc / user credential fallback
        kwargs["allow_redirects"] = False  # do not hide a second endpoint/request
        call = {"started_at_utc": started}
        actual_calls.append(call)
        try:
            response = real_get(url, **kwargs)
        except requests.RequestException as exc:
            call.update({"finished_at_utc": utc_now(), "error_type": type(exc).__name__})
            raise
        call.update({"finished_at_utc": utc_now(), "http_status": response.status_code,
                     "raw_records_received": raw_count(provider, response),
                     "timeout_seconds": kwargs.get("timeout")})
        prepared = response.request
        if prepared is None or prepared.method != "GET":
            raise ValueError("Could not verify the actual request")
        if prepared.headers.get("Authorization"):
            raise ValueError("An authorization header was unexpectedly present")
        sent = urlsplit(prepared.url)
        target = urlsplit(endpoint)
        actual_params = parse_qsl(sent.query, keep_blank_values=True)
        expected_params = [(key, str(value)) for key, value in params.items()]
        if (sent.scheme, sent.netloc, sent.path) != (target.scheme, target.netloc, target.path) or sorted(actual_params) != sorted(expected_params):
            raise ValueError("Prepared request parameters or endpoint differed from the fixed search")
        call["parameters_verified"] = True
        return response

    try:
        with patch.object(requests, "get", side_effect=tracked_get):
            if provider == "OpenAlex":
                response = requests.get(endpoint, params=params, timeout=guided.TIMEOUT_SECONDS)
                if not 200 <= response.status_code < 300:
                    raise RuntimeError(f"OpenAlex HTTP {response.status_code}")
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("results"), list) or not isinstance(data.get("meta"), dict):
                    raise ValueError("Unexpected OpenAlex response structure")
                raw = data["results"]
                frame = guided.openalex_records_to_frame(raw)
                total = nonnegative_int(data["meta"].get("count"))
                meta = {"case_key": case_key, "provider": provider, "source": provider,
                        "query": query, "endpoint": endpoint, "parameters": params,
                        "returned": len(frame), "total_matches": total,
                        "possibly_truncated": guided._truncated(total, len(frame), len(raw),
                                                                 bool(data["meta"].get("next_cursor"))),
                        "pages_fetched": 1, "page_size": guided.PAGE_SIZE}
            else:
                # Use the existing provider implementations and converters unchanged.
                frame, meta = guided.fetch_guided(case_key, provider)
        if len(actual_calls) != 1 or not actual_calls[0].get("parameters_verified"):
            raise ValueError("The actual anonymous request could not be verified")
        if not isinstance(frame, pd.DataFrame) or not isinstance(meta, dict):
            raise ValueError("Invalid provider result")
        for key, value in (("case_key", case_key), ("provider", provider), ("source", provider),
                           ("query", query), ("endpoint", endpoint), ("parameters", params),
                           ("pages_fetched", 1), ("page_size", guided.PAGE_SIZE), ("returned", len(frame))):
            if meta.get(key) != value:
                raise ValueError(f"Provider metadata mismatch: {key}")
        if actual_calls[0]["raw_records_received"] is None:
            raise ValueError("Could not count the provider response records")
        if len(frame) > guided.PAGE_SIZE or actual_calls[0]["raw_records_received"] > guided.PAGE_SIZE:
            raise ValueError("Provider exceeded the requested one-page cap")
        if "Source" not in frame or not frame["Source"].eq(provider).all():
            raise ValueError("Provider source does not match the retrieved records")
        if any(column not in frame.columns for column in guided.COLUMNS):
            raise ValueError("Provider result is missing common metadata fields")
        attempts.extend(actual_calls)
        return frame, meta, actual_calls[0]
    except Exception:
        attempts.extend(actual_calls or [{"started_at_utc": utc_now(), "error_type": "NoRequest"}])
        raise


def normalized(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return " ".join(str(value).split()).casefold()


def count_screening(frame, case):
    """Mirror guided_workflow's literal, casefolded, whitespace-normalized screen."""
    def matches(row, terms):
        fields = (normalized(row.get("Title")), normalized(row.get("Abstract")))
        return any(normalized(term) and normalized(term) in field for term in terms for field in fields)
    return sum(matches(row, case["inclusion_terms"]) and not matches(row, case["exclusion_terms"])
               for row in frame.to_dict(orient="records"))


def clean_frame(frame):
    # An allowlist avoids retaining descriptions, raw provider payloads or secrets.
    clean = frame.reindex(columns=COLUMNS, fill_value="").copy().fillna("")
    clean["Abstract"] = ""
    clean["Abstract Source"] = WITHHELD_SOURCE
    return clean.reset_index(drop=True)


def make_log(case_key, provider, case, frame, meta, call, attempts, csv_data):
    query, endpoint, params = expected_request(case_key, provider)
    csv_file, log_file = filenames(case_key, provider)
    raw_received = call["raw_records_received"]
    total = nonnegative_int(meta.get("total_matches"))
    truncated = meta.get("possibly_truncated")
    if not isinstance(truncated, bool):
        raise ValueError("Provider truncation indicator is missing")
    if raw_received != len(frame) or (total is not None and total != len(frame)):
        truncated = True
    matching = count_screening(frame, case)
    return {
        "case_key": case_key, "provider": provider, "source": provider,
        "query": query, "endpoint": endpoint, "request_method": "GET",
        "parameters": params, "request_parameters_verified_against_prepared_url": True,
        "timestamp_utc": call["finished_at_utc"], "retrieved_at_utc": call["finished_at_utc"],
        "request_attempts": len(attempts), "request_attempt_details": attempts,
        "pages_fetched": 1, "page_size": guided.PAGE_SIZE, "per_page_cap": guided.PAGE_SIZE,
        "raw_records_received": raw_received, "returned": len(frame), "record_count": len(frame),
        "total_matches": total, "possibly_truncated": truncated,
        "corpus_file": csv_file, "log_file": log_file,
        "corpus_sha256": hashlib.sha256(csv_data).hexdigest(),
        "raw_response_file": None,
        "raw_response_retention": "No raw response body, provider response archive, request URL or credentials are stored.",
        "abstract_note": "All abstracts and descriptions are withheld from this public capture because reuse rights were not independently verified for each actual text. Blank fields do not establish that the provider lacked text; screening is title-only and may miss matches.",
        "screening": {
            "method": "Case-insensitive, whitespace-normalized literal substring match in title OR abstract; any inclusion term and no exclusion term. Human review is required.",
            "inclusion_terms": case["inclusion_terms"], "exclusion_terms": case["exclusion_terms"],
            "matching_records": matching, "excluded_records": len(frame) - matching,
            "note": "All abstracts are withheld, so this count reflects title matches only and may miss studies that would match available abstracts."
        },
        "field_coverage": {field: sum(bool(normalized(v)) for v in frame[field]) for field in guided.COLUMNS},
        "field_notes": {
            "Abstract": "Every abstract/description is deliberately withheld from this publicly shareable capture because rights were not independently verified at record/content level. A blank is not evidence the provider lacked one. Withholding can change screening, extraction and synthesis results.",
            "Abstract Source": "A uniform withholding notice, not an assertion about whether the original provider had text.",
            "References": "JSON array of explicit normalized identifiers supplied by the existing converter; a blank is not evidence that the article has no references. Europe PMC and OpenAIRE converters do not supply references.",
            "Other metadata": "Fields are provider-supplied and may be incomplete or stale; no missing bibliographic values are inferred."
        },
        "rights_note": "Abstracts and descriptions may be copyrighted and no record-level CC BY/CC0 assessment was independently made, so all such text is withheld. Bibliographic metadata may have separate terms: verify provider and source rights before redistribution and acknowledge OpenAIRE as the data source for its records.",
        "sample_note": "A real anonymous single-page bounded teaching sample, not an exhaustive or validated systematic search; provider ranking and results can change. No records are fabricated, merged, or borrowed from another provider.",
        "limitations": [
            "Only one page was fetched, up to 25 records. A total of null is unknown; possibly_truncated is conservative, and the sample is not proof of completeness even when the reported total is reached.",
            "Queries use each provider's own matching and coverage; some matches may be in withheld abstracts or, for OpenAIRE, other research-product fields.",
            "The deterministic screening heuristic is not an eligibility determination; absent abstract text limits extraction and evidence synthesis."
        ]
    }


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".snapshot-", delete=False) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(data)
        temp_path.chmod(0o644)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def refresh(case_key, provider, case):
    attempts = []
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            frame, meta, call = capture_once(case_key, provider, attempts)
            clean = clean_frame(frame)
            csv_data = clean.to_csv(index=False, lineterminator="\n").encode("utf-8")
            log = make_log(case_key, provider, case, clean, meta, call, attempts, csv_data)
            csv_file, log_file = filenames(case_key, provider)
            log_data = (json.dumps(log, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            write_atomic(OUT / csv_file, csv_data)
            write_atomic(OUT / log_file, log_data)
            return log
        except Exception as exc:
            # Errors are safe summaries only: never print a request URL or body.
            status = attempts[-1].get("http_status") if attempts else None
            last_error = f"{type(exc).__name__}" + (f" (HTTP {status})" if status is not None else "")
            if attempt < RETRIES:
                time.sleep(attempt * 2)
    raise RuntimeError(f"{case_key} / {provider}: {last_error} after {RETRIES} attempts")


def verify(case_key, provider, case):
    """Strictly audit locally stored data and provenance without any request."""
    csv_file, log_file = filenames(case_key, provider)
    csv_data = (OUT / csv_file).read_bytes()
    log = json.loads((OUT / log_file).read_text(encoding="utf-8"))
    query, endpoint, params = expected_request(case_key, provider)
    required = {"case_key": case_key, "provider": provider, "source": provider, "query": query,
                "endpoint": endpoint, "parameters": params, "request_method": "GET",
                "pages_fetched": 1, "page_size": guided.PAGE_SIZE, "per_page_cap": guided.PAGE_SIZE,
                "corpus_file": csv_file, "log_file": log_file,
                "corpus_sha256": hashlib.sha256(csv_data).hexdigest(),
                "raw_response_file": None, "request_parameters_verified_against_prepared_url": True}
    for key, expected in required.items():
        if log.get(key) != expected:
            raise ValueError(f"{case_key} / {provider}: {key} mismatch")
    frame = pd.read_csv(io.BytesIO(csv_data), dtype=str, keep_default_na=False)
    if list(frame.columns) != COLUMNS or len(frame) > guided.PAGE_SIZE:
        raise ValueError(f"{case_key} / {provider}: invalid schema or page cap")
    if not frame["Source"].eq(provider).all() or not frame["Abstract"].eq("").all() or not frame["Abstract Source"].eq(WITHHELD_SOURCE).all():
        raise ValueError(f"{case_key} / {provider}: source or abstract-withholding mismatch")
    if (log.get("record_count") != len(frame) or log.get("returned") != len(frame)
            or not isinstance(log.get("possibly_truncated"), bool)):
        raise ValueError(f"{case_key} / {provider}: count or truncation mismatch")
    raw_received = nonnegative_int(log.get("raw_records_received"))
    total = log.get("total_matches")
    if (raw_received is None or raw_received > guided.PAGE_SIZE or raw_received < len(frame)
            or (total is not None and nonnegative_int(total) is None)
            or ((raw_received != len(frame) or (total is not None and total != len(frame)))
                and not log["possibly_truncated"])):
        raise ValueError(f"{case_key} / {provider}: invalid provider counts or truncation")
    try:
        stamp = datetime.fromisoformat(log["retrieved_at_utc"].replace("Z", "+00:00"))
        if stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            raise ValueError
    except (KeyError, AttributeError, TypeError, ValueError):
        raise ValueError(f"{case_key} / {provider}: invalid retrieval timestamp") from None
    if not isinstance(log.get("abstract_note"), str) or not log["abstract_note"]:
        raise ValueError(f"{case_key} / {provider}: missing abstract rights note")
    screening = log.get("screening", {})
    if (screening.get("inclusion_terms") != case["inclusion_terms"]
            or screening.get("exclusion_terms") != case["exclusion_terms"]
            or screening.get("matching_records") != count_screening(frame, case)
            or screening.get("excluded_records") != len(frame) - count_screening(frame, case)):
        raise ValueError(f"{case_key} / {provider}: screening mismatch")
    for value in frame["References"]:
        if value:
            references = json.loads(value)
            if not isinstance(references, list) or any(not isinstance(ref, str) for ref in references):
                raise ValueError(f"{case_key} / {provider}: invalid references")
    return log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify existing files offline; make no HTTP requests")
    parser.add_argument("--case", choices=list(guided.GUIDED_QUERIES), help="Limit to one fixed case")
    parser.add_argument("--provider", choices=list(PROVIDER_SLUGS), help="Limit to one provider (quote Europe PMC)")
    args = parser.parse_args()
    cases = load_cases()
    keys = [args.case] if args.case else list(cases)
    providers = [args.provider] if args.provider else list(PROVIDER_SLUGS)
    failures = []
    combinations = [(key, provider) for key in keys for provider in providers]
    for index, (key, provider) in enumerate(combinations):
        if index and not args.verify:
            time.sleep(1)
        print(f"{'Verifying' if args.verify else 'Fetching'} {key} / {provider}...", flush=True)
        try:
            log = verify(key, provider, cases[key]) if args.verify else refresh(key, provider, cases[key])
            if not args.verify:
                verify(key, provider, cases[key])
            matches = log["screening"]["matching_records"]
            print(f"  {log['record_count']} records; {matches} title-screen matches; total={log['total_matches']}; truncated={log['possibly_truncated']}" + ("; ZERO MATCHES" if matches == 0 else ""), flush=True)
        except Exception as exc:
            # Fixed combination names and sanitized exception class only.
            detail = str(exc) if isinstance(exc, RuntimeError) and str(exc).startswith(f"{key} / {provider}:") else type(exc).__name__
            failures.append(f"{key} / {provider}: {detail}")
            print(f"  FAILED: {detail}", flush=True)
    if failures:
        print("Unsuccessful combinations:", *failures, sep="\n", flush=True)
        return 1
    print(f"{'Verified' if args.verify else 'Wrote and verified'} {len(combinations)} snapshot pairs in {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
