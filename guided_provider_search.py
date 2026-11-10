"""Live, bounded retrieval for the fixed guided cases; no Streamlit or file I/O.

Public entry points: ``guided_query(case_key, provider)``,
``openalex_records_to_frame(records)``, and
``fetch_guided(case_key, provider, api_key='')``. A single provider page is
returned for teaching, not a comprehensive systematic review. OpenAlex needs a
key; the other providers are anonymous. Provider responses are not cached.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import html
import json
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

import pandas as pd
import requests

import openalex_client
import openaire_client


PROVIDERS = ("OpenAlex", "Crossref", "Europe PMC", "OpenAIRE")
PAGE_SIZE = 25
COLUMNS = ["ID", "DOI", "Title", "Year", "Authors", "Venue", "Abstract",
           "Citations", "Concepts", "References", "Source"]
CROSSREF_ENDPOINT = "https://api.crossref.org/works"
EUROPE_PMC_ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TIMEOUT_SECONDS = 30
OPENALEX_SELECT = ("id,doi,title,publication_year,authorships,primary_location,"
                   "abstract_inverted_index,cited_by_count,concepts,type,referenced_works")
CROSSREF_SELECT = ("DOI,title,author,published,container-title,abstract,reference,"
                   "is-referenced-by-count,subject")

# The provider-specific strings are deliberately fixed. Crossref's query is a
# relevance search, not a Boolean expression. All OpenAIRE Boolean operands are
# quoted. Europe PMC and OpenAlex receive literal words and quoted phrases.
GUIDED_QUERIES = MappingProxyType({
    "ex1_health": MappingProxyType({
        "OpenAlex": '("health inequalities" OR "health disparities") AND (diabetes OR hypertension OR "cardiovascular disease")',
        "Crossref": "socioeconomic health inequalities diabetes chronic disease care",
        "Europe PMC": '("health inequalities" OR "health disparities") AND (diabetes OR hypertension OR "cardiovascular disease")',
        "OpenAIRE": '("health inequalities" OR "health disparities") AND ("diabetes" OR "hypertension" OR "cardiovascular disease")',
    }),
    "ex2_ubi": MappingProxyType({
        "OpenAlex": '("universal basic income" OR "guaranteed income") AND (employment OR poverty OR "well-being")',
        "Crossref": "universal basic income policy employment poverty well-being evaluation",
        "Europe PMC": '("universal basic income" OR "guaranteed income") AND (employment OR poverty OR "well-being")',
        "OpenAIRE": '("universal basic income" OR "guaranteed income") AND ("employment" OR "poverty" OR "well-being")',
    }),
    "ex3_microplastics": MappingProxyType({
        "OpenAlex": 'microplastics AND (marine OR freshwater OR aquatic)',
        "Crossref": "microplastics aquatic marine freshwater ecological pollution",
        "Europe PMC": 'microplastics AND (marine OR freshwater OR aquatic)',
        "OpenAIRE": '"microplastics" AND ("marine" OR "freshwater" OR "aquatic")',
    }),
    "ex4_csr": MappingProxyType({
        "OpenAlex": '("corporate social responsibility" OR CSR) AND ("financial performance" OR profitability)',
        "Crossref": "corporate social responsibility firm financial performance profitability",
        "Europe PMC": '("corporate social responsibility" OR CSR) AND ("financial performance" OR profitability)',
        "OpenAIRE": '("corporate social responsibility" OR "CSR") AND ("financial performance" OR "profitability")',
    }),
})


class GuidedSearchError(RuntimeError):
    """A sanitized, user-facing provider or response error."""


def guided_query(case_key: str, provider: str) -> str:
    """Return the immutable fixed query for one supported case and provider."""
    if not isinstance(case_key, str) or case_key not in GUIDED_QUERIES:
        raise ValueError("Unsupported guided case.")
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError("Unsupported guided provider.")
    return GUIDED_QUERIES[case_key][provider]


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return _text(value)
    return next((text for item in _list(value) if (text := _text(item))), "")


def _count(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


class _PlainText(HTMLParser):
    """Strip markup without adding whitespace inside inline elements."""
    blocks = {"p", "br", "div", "section", "sec", "abstract", "title", "li"}
    hidden = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower().split(":")[-1]
        if tag in self.hidden:
            self.depth += 1
        elif not self.depth and tag in self.blocks:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower().split(":")[-1]
        if tag in self.hidden and self.depth:
            self.depth -= 1
        elif not self.depth and tag in self.blocks:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        if not self.depth and tag.lower().split(":")[-1] in self.blocks:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.depth:
            self.parts.append(data)


def _plain(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _PlainText()
    try:
        parser.feed(html.unescape(value))
        parser.close()
        return " ".join("".join(parser.parts).split())
    except (ValueError, AssertionError):
        return " ".join(re.sub(r"</?[A-Za-z][^>]*>", " ", html.unescape(value)).split())


def _openalex_ref(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    match = re.fullmatch(r"(?:(?:https?://openalex\.org/)|(?:https?://api\.openalex\.org/works/)|openalex:)?W([0-9]+)/?", value.strip(), flags=re.I)
    return "openalex:W" + match.group(1) if match else ""


def _doi_ref(value: Any) -> str:
    """Normalize only an explicitly provided DOI, never infer one from text."""
    if not isinstance(value, str):
        return ""
    doi = re.sub(r"^doi:\s*", "", value.strip(), flags=re.I)
    if any(not c.isprintable() or c.isspace() for c in doi):
        return ""
    if re.match(r"^https?://", doi, flags=re.I):
        try:
            parsed = urlsplit(doi)
            if (parsed.netloc.casefold() not in {"doi.org", "dx.doi.org"}
                    or parsed.query or parsed.fragment or not parsed.path.startswith("/")
                    or re.search(r"%(?![0-9a-fA-F]{2})", parsed.path)):
                return ""
            doi = unquote(parsed.path[1:], encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return ""
    if not re.fullmatch(r"10\.[0-9]+/.+", doi, flags=re.I) or any(not c.isprintable() or c.isspace() for c in doi):
        return ""
    return "doi:" + doi.casefold()


def _reference_json(values: Any) -> str:
    """Preserve distinct supplied identifiers in JSON, including semicolons."""
    unique = list(dict.fromkeys(value for value in values if value))
    return json.dumps(unique, ensure_ascii=False) if unique else ""


def _abstract(index: Any) -> str:
    positions: dict[int, str] = {}
    for word, offsets in _mapping(index).items():
        if not isinstance(word, str):
            continue
        for offset in _list(offsets):
            if isinstance(offset, int) and not isinstance(offset, bool) and offset >= 0:
                positions[offset] = word
    # Sorting sparse positions rather than allocating to the maximum avoids
    # unbounded allocation for a malformed provider response.
    return " ".join(positions[offset] for offset in sorted(positions))


def openalex_records_to_frame(records: Any) -> pd.DataFrame:
    """Normalize supplied OpenAlex Works; skip non-records and infer nothing."""
    rows = []
    for record in _list(records):
        if not isinstance(record, dict):
            continue
        names = [(_text(_mapping(_mapping(entry).get("author")).get("display_name"))
                  or _text(_mapping(entry).get("raw_author_name")))
                 for entry in _list(record.get("authorships"))]
        concepts = [_text(_mapping(entry).get("display_name")) for entry in _list(record.get("concepts"))]
        location = _mapping(_mapping(record.get("primary_location")).get("source"))
        year = record.get("publication_year")
        rows.append({
            "ID": _text(record.get("id")), "DOI": _text(record.get("doi")),
            "Title": _text(record.get("title")),
            "Year": str(year) if (isinstance(year, (str, int)) and not isinstance(year, bool)) else "",
            "Authors": "; ".join(name for name in names if name),
            "Venue": _text(location.get("display_name")),
            "Abstract": _abstract(record.get("abstract_inverted_index")),
            "Citations": _count(record.get("cited_by_count")) if _count(record.get("cited_by_count")) is not None else "",
            "Concepts": "; ".join(name for name in concepts if name),
            "References": _reference_json(_openalex_ref(v) for v in _list(record.get("referenced_works"))),
            "Source": "OpenAlex",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def _crossref_row(item: dict) -> dict:
    authors = []
    for author in _list(item.get("author")):
        author = _mapping(author)
        # Preserve the literal supplied parts in natural given/family order.
        name = " ".join(part for part in (_text(author.get("given")), _text(author.get("family"))) if part)
        if not name:
            name = _text(author.get("name"))  # Crossref organizational author
        if name:
            authors.append(name)
    dates = _list(_mapping(item.get("published")).get("date-parts"))
    parts = _list(dates[0]) if dates else []
    year = parts[0] if parts else None
    references = []
    for entry in _list(item.get("reference")):
        entry = _mapping(entry)
        references.append(_doi_ref(entry.get("DOI")) or _doi_ref(entry.get("doi")))
    citations = _count(item.get("is-referenced-by-count"))
    return {
        "ID": _text(item.get("DOI")), "DOI": _text(item.get("DOI")),
        "Title": _plain(_first_text(item.get("title"))),
        "Year": str(year) if isinstance(year, (int, str)) and not isinstance(year, bool) else "",
        "Authors": "; ".join(authors), "Venue": _plain(_first_text(item.get("container-title"))),
        "Abstract": _plain(item.get("abstract")), "Citations": citations if citations is not None else "",
        "Concepts": "; ".join(text for entry in _list(item.get("subject")) if (text := _plain(entry))),
        "References": _reference_json(references), "Source": "Crossref",
    }


def _europepmc_row(item: dict) -> dict:
    authors = [_text(_mapping(author).get("fullName"))
               for author in _list(_mapping(item.get("authorList")).get("author"))]
    names = "; ".join(name for name in authors if name)
    # Do not guess where individual names begin or end in authorString.
    if not names:
        names = _text(item.get("authorString"))
    year = item.get("pubYear")
    citations = _count(item.get("citedByCount"))
    journal_info = _mapping(item.get("journalInfo"))
    journal = _mapping(journal_info.get("journal"))
    return {
        "ID": _text(item.get("id")), "DOI": _text(item.get("doi")),
        "Title": _plain(item.get("title")),
        "Year": str(year) if isinstance(year, (int, str)) and not isinstance(year, bool) else "",
        "Authors": names, "Venue": _text(item.get("journalTitle")) or _text(journal.get("title")),
        "Abstract": _plain(item.get("abstractText")), "Citations": citations if citations is not None else "",
        "Concepts": "", "References": "", "Source": "Europe PMC",
    }


def _get_json(provider: str, endpoint: str, params: dict) -> dict:
    try:
        response = requests.get(endpoint, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        raise GuidedSearchError(f"{provider} could not be reached or timed out. Please retry.") from None
    status = response.status_code
    if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status < 300:
        if status == 429:
            raise GuidedSearchError(f"{provider} rate-limited this request (HTTP 429). Wait and retry.") from None
        safe_status = f" (HTTP {status})" if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599 else ""
        raise GuidedSearchError(f"{provider} could not complete this search{safe_status}. Please retry.") from None
    try:
        payload = response.json()
    except (ValueError, TypeError):
        raise GuidedSearchError(f"{provider} returned an invalid response. Please retry.") from None
    if not isinstance(payload, dict):
        raise GuidedSearchError(f"{provider} returned an invalid response. Please retry.") from None
    return payload


def _truncated(total: int | None, returned: int, raw_received: int, possibly_more: bool = False) -> bool:
    # Unknown/inconsistent count cannot establish completeness. Skipped malformed
    # records also prevent the returned DataFrame from representing the full set.
    if raw_received != returned:
        return True
    if total is not None:
        return total != returned
    return bool(possibly_more or raw_received)


def _metadata(provider: str, case_key: str, query: str, endpoint: str, parameters: dict,
              returned: int, total: int | None, truncated: bool, caveats: list[str]) -> dict:
    # Allowlist only local, known metadata. Never pass through arbitrary client
    # logs, response bodies, URLs, headers, exceptions or credentials.
    return {
        "case_key": case_key, "provider": provider, "source": provider,
        "query": query, "endpoint": endpoint, "parameters": parameters,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "returned": returned, "total_matches": total, "possibly_truncated": truncated,
        "pages_fetched": 1, "page_size": PAGE_SIZE,
        "sample_note": "One-page bounded live sample; not a comprehensive systematic search. Results may change over time.",
        "limitations": caveats,
    }


def _fetch_guided(case_key: str, provider: str, api_key: str = "") -> tuple[pd.DataFrame, dict]:
    """Fetch one page from the selected provider, returning (DataFrame, metadata).

    A blank API key is valid only for anonymous providers. Errors are sanitized
    and never expose request URLs, provider bodies, credentials or inner errors.
    Only OpenAlex receives the key, through its existing client bearer header.
    """
    query = guided_query(case_key, provider)
    if provider == "OpenAlex":
        if not isinstance(api_key, str) or not api_key.strip():
            raise GuidedSearchError("OpenAlex requires an API key.")
        params = {"search.title_and_abstract.exact": query, "per-page": PAGE_SIZE,
                  "cursor": "*", "select": OPENALEX_SELECT}
        try:
            records, log = openalex_client.fetch_works(
                query, api_key, per_page=PAGE_SIZE, max_pages=1,
                search_scope="title_abstract_exact", require_abstract=False,
            )
        except Exception:
            raise GuidedSearchError("OpenAlex could not complete this search. Check the API key or retry.") from None
        if not isinstance(records, list) or not isinstance(log, dict):
            raise GuidedSearchError("OpenAlex returned an invalid response. Please retry.")
        frame = openalex_records_to_frame(records)
        total = _count(log.get("total_matches"))
        # fetch_works substitutes 0 when meta.count is absent. Its log cannot
        # distinguish that from a real zero; conservatively label zero unknown.
        if total == 0:
            total = None
        truncated = _truncated(total, len(frame), len(records), bool(log.get("possibly_truncated")))
        caveats = ["OpenAlex matches the fixed query against titles and abstracts with exact scope; provider matching and ranking determine results.",
                   "Abstracts are reconstructed from supplied inverted indexes and may be missing; no abstract filter is applied.",
                   "Only explicitly supplied OpenAlex work reference IDs are shown; missing references are not inferred."]
        if total is None:
            caveats.append("The OpenAlex client cannot distinguish a reported zero count from a missing count; total is shown as unknown.")
        return frame, _metadata(provider, case_key, query, openalex_client.OpenAlexClient.BASE_URL,
                                params, len(frame), total, truncated, caveats)

    if provider == "OpenAIRE":
        params = {"search": query, "type": "publication", "pageSize": PAGE_SIZE, "cursor": "*"}
        try:
            frame, log = openaire_client.fetch_openaire(query, per_page=PAGE_SIZE, max_pages=1)
        except Exception:
            raise GuidedSearchError("OpenAIRE could not complete this search. Wait and retry, or use another provider.") from None
        if not isinstance(frame, pd.DataFrame) or not isinstance(log, dict):
            raise GuidedSearchError("OpenAIRE returned an invalid response. Please retry.")
        # Retain the client's already-normalized fields, including its description
        # provenance; add the common schema without assuming references exist.
        frame = frame.copy().reset_index(drop=True)
        for column in COLUMNS:
            if column not in frame:
                frame[column] = ""
        frame["Source"] = "OpenAIRE"
        extras = [column for column in frame.columns if column not in COLUMNS]
        frame = frame[COLUMNS + extras]
        total = _count(log.get("total_matches"))
        raw_received = _count(log.get("raw_records_received"))
        if raw_received is None:
            raw_received = len(frame)
        truncated = _truncated(total, len(frame), raw_received, bool(log.get("possibly_truncated")))
        caveats = ["Search covers broad research-product content, not just titles and abstracts; results are restricted to publications.",
                   "The Abstract field is the first supplied description and may not be a formal abstract.",
                   "This client does not supply reference lists; references are not inferred."]
        return frame, _metadata(provider, case_key, query, openaire_client.ENDPOINT,
                                params, len(frame), total, truncated, caveats)

    if provider == "Crossref":
        endpoint = CROSSREF_ENDPOINT
        params = {"query": query, "rows": PAGE_SIZE, "select": CROSSREF_SELECT}
        payload = _get_json(provider, endpoint, params)
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("items"), list):
            raise GuidedSearchError("Crossref returned an invalid response. Please retry.")
        items = message["items"]
        frame = pd.DataFrame([_crossref_row(item) for item in items if isinstance(item, dict)], columns=COLUMNS)
        total = _count(message.get("total-results"))
        caveats = ["Crossref query is provider relevance matching, not guaranteed Boolean or title/abstract matching.",
                   "Abstracts and references depend on deposited metadata and can be missing.",
                   "Only explicit DOI fields in reference entries are shown; unstructured citations and reference counts are not converted to IDs."]
    else:  # Europe PMC: only literal words, quoted phrases and Boolean operators.
        endpoint = EUROPE_PMC_ENDPOINT
        params = {"query": query, "resultType": "core", "pageSize": PAGE_SIZE, "format": "json", "cursorMark": "*"}
        payload = _get_json(provider, endpoint, params)
        result_list = payload.get("resultList")
        if not isinstance(result_list, dict) or not isinstance(result_list.get("result"), list):
            raise GuidedSearchError("Europe PMC returned an invalid response. Please retry.")
        items = result_list["result"]
        frame = pd.DataFrame([_europepmc_row(item) for item in items if isinstance(item, dict)], columns=COLUMNS)
        total = _count(payload.get("hitCount"))
        caveats = ["Europe PMC searches its life-sciences-oriented index using provider Boolean syntax; matches and coverage differ from other providers.",
                   "Core metadata may omit abstracts; structured author lists may be incomplete.",
                   "The search response does not supply a reference list here; no reference IDs are inferred."]
    truncated = _truncated(total, len(frame), len(items))
    return frame, _metadata(provider, case_key, query, endpoint, params, len(frame), total, truncated, caveats)


def fetch_guided(case_key: str, provider: str, api_key: str = "") -> tuple[pd.DataFrame, dict]:
    """Fetch exactly one bounded live page, with credential-safe errors.

    Invalid case/provider values raise a sanitized ValueError. Provider or
    malformed-response failures raise a sanitized GuidedSearchError, including
    unexpected exceptions, without forwarding exception chains or response text.
    """
    guided_query(case_key, provider)  # Validate without echoing user inputs.
    try:
        return _fetch_guided(case_key, provider, api_key)
    except GuidedSearchError:
        raise
    except Exception:
        raise GuidedSearchError("The selected provider returned invalid data or could not be reached. Please retry.") from None


__all__ = ["COLUMNS", "GUIDED_QUERIES", "GuidedSearchError", "PAGE_SIZE", "PROVIDERS",
           "fetch_guided", "guided_query", "openalex_records_to_frame"]
