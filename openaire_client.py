"""Anonymous, bounded OpenAIRE Graph v3 publication search.

``fetch_openaire(query, per_page=50, max_pages=1)`` returns a pandas
DataFrame and a request log. No request occurs at import and no credentials
are needed or accepted. OpenAIRE's ``search`` covers research-product content,
not just titles and abstracts. Boolean operands must be double quoted when
using AND/OR/NOT; the query is sent verbatim and is not syntax-checked here.

The API supplies descriptions, which are not necessarily abstracts. The first
nonempty description is carried in the app's Abstract column and its origin is
identified in Abstract Source and the request log. Missing text stays empty.
The Graph is CC-BY; acknowledge OpenAIRE as the source when reusing its data.
"""
from __future__ import annotations

import html
import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import pandas as pd
import requests


ENDPOINT = "https://api.openaire.eu/graph/v3/research-products"
MAX_PAGE_SIZE = 100
MAX_PAGES = 10
TIMEOUT_SECONDS = 30
COLUMNS = [
    "ID", "DOI", "Title", "Year", "Authors", "Venue", "Abstract",
    "Citations", "Concepts", "Publication Type", "Abstract Source",
]


class OpenAIREError(RuntimeError):
    """Sanitized, participant-facing transport or provider error."""


class _TextExtractor(HTMLParser):
    """Strip HTML/JATS tags while preserving inline text and block boundaries."""

    _blocks = {"abstract", "article", "body", "br", "div", "h1", "h2", "h3",
               "h4", "h5", "h6", "li", "p", "sec", "section", "title", "tr"}
    _hidden = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Any]]) -> None:
        name = tag.lower().split(":")[-1]
        if name in self._hidden:
            self.hidden_depth += 1
        elif not self.hidden_depth and name in self._blocks:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower().split(":")[-1]
        if name in self._hidden and self.hidden_depth:
            self.hidden_depth -= 1
        elif not self.hidden_depth and name in self._blocks:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Any]]) -> None:
        if not self.hidden_depth and tag.lower().split(":")[-1] in self._blocks:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _clean_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    # Decode escaped JATS before parsing. HTMLParser does not fetch entities or
    # execute external resources, so XML DTDs and scripts cannot be executed.
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(value))
        parser.close()
        return " ".join("".join(parser.parts).split())
    except (ValueError, AssertionError):
        # Malformed markup should not fail the entire retrieval.
        return " ".join(re.sub(r"</?[A-Za-z][^>]*>", " ", html.unescape(value)).split())


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _doi(record: dict[str, Any]) -> str:
    identifiers = list(_list(record.get("pids")))
    for instance in _list(record.get("instances")):
        instance = _mapping(instance)
        identifiers.extend(_list(instance.get("pids")))
        identifiers.extend(_list(instance.get("alternateIdentifiers")))
    for identifier in identifiers:
        identifier = _mapping(identifier)
        if str(identifier.get("scheme") or "").casefold() != "doi":
            continue
        value = identifier.get("value")
        if isinstance(value, str) and value.strip():
            return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)
    return ""


def _year(record: dict[str, Any]) -> str:
    date = record.get("publicationDate")
    if isinstance(date, str):
        match = re.match(r"^(\d{4})(?:-|$)", date.strip())
        if match:
            return match.group(1)
    return ""


def _row(record: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in _list(record.get("authors")):
        if isinstance(author, str):
            name = _clean_text(author)
        else:
            author = _mapping(author)
            name = _clean_text(author.get("fullName"))
            if not name:
                name = " ".join(filter(None, [_clean_text(author.get("name")), _clean_text(author.get("surname"))]))
        if name:
            authors.append(name)

    concepts = []
    for entry in _list(record.get("subjects")):
        if isinstance(entry, str):
            value = entry
        else:
            subject = _mapping(entry).get("subject")
            value = _mapping(subject).get("value") if isinstance(subject, dict) else subject
        text = _clean_text(value)
        if text:
            concepts.append(text)

    description = ""
    for entry in _list(record.get("descriptions")):
        description = _clean_text(entry)
        if description:
            break

    publication_types = []
    for instance in _list(record.get("instances")):
        value = _clean_text(_mapping(instance).get("type"))
        if value:
            publication_types.append(value)

    impact = _mapping(_mapping(record.get("indicators")).get("citationImpact"))
    citations = impact.get("citationCount")
    if isinstance(citations, bool) or not isinstance(citations, (int, float)) or not math.isfinite(citations) or citations < 0:
        citations = ""
    elif isinstance(citations, float) and citations.is_integer():
        citations = int(citations)

    return {
        "ID": _clean_text(record.get("id")),
        "DOI": _doi(record),
        "Title": _clean_text(record.get("mainTitle")),
        "Year": _year(record),
        "Authors": "; ".join(_unique(authors)),
        "Venue": _clean_text(_mapping(record.get("container")).get("name")),
        "Abstract": description,
        "Citations": citations,
        "Concepts": "; ".join(_unique(concepts)),
        "Publication Type": "; ".join(_unique(publication_types)),
        "Abstract Source": "OpenAIRE description (not necessarily an abstract)" if description else "missing",
    }


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_openaire(query: str, per_page: int = 50, max_pages: int = 1) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Search anonymously, returning ``(DataFrame, request_log)``.

    ``per_page`` must be a positive integer and is capped at 100. ``max_pages``
    must be between 1 and 10 inclusive. At most 1,000 records are requested.
    No automatic retry is performed, respecting anonymous rate limits.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a nonempty string")
    if not isinstance(per_page, int) or isinstance(per_page, bool) or per_page < 1:
        raise ValueError("per_page must be a positive integer")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= MAX_PAGES:
        raise ValueError(f"max_pages must be an integer between 1 and {MAX_PAGES}")

    per_page = min(per_page, MAX_PAGE_SIZE)
    started = _timestamp()
    rows: list[dict[str, Any]] = []
    pages = 0
    raw_received = 0
    skipped = 0
    total: int | None = None
    last_total: int | None = None
    largest_total: int | None = None
    cursor = "*"
    seen_cursors = {cursor}
    next_cursor = None
    termination = "page_limit"
    for _ in range(max_pages):
        params = {"search": query, "type": "publication", "pageSize": per_page, "cursor": cursor}
        try:
            response = requests.get(ENDPOINT, params=params, timeout=TIMEOUT_SECONDS)
        except requests.RequestException:
            raise OpenAIREError("OpenAIRE could not be reached or timed out. Wait and retry, or use another provider.") from None
        status = response.status_code
        if status == 429:
            raise OpenAIREError("OpenAIRE rate-limited this request (HTTP 429). Wait before retrying, or use another provider; anonymous access is rate-limited.") from None
        if not isinstance(status, int) or not 200 <= status < 300:
            code = f" (HTTP {status})" if isinstance(status, int) and not isinstance(status, bool) else ""
            raise OpenAIREError(f"OpenAIRE could not complete this search{code}. Check the query syntax and retry, or use another provider.") from None
        try:
            payload = response.json()
        except (ValueError, TypeError):
            raise OpenAIREError("OpenAIRE returned an invalid response. Retry later or use another provider.") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("header"), dict) or not isinstance(payload.get("results"), list):
            raise OpenAIREError("OpenAIRE returned an invalid response. Retry later or use another provider.") from None
        header = payload["header"]
        current_total = _count(header.get("numFound"))
        if pages == 0:
            total = current_total
        last_total = current_total
        if current_total is not None:
            largest_total = current_total if largest_total is None else max(largest_total, current_total)
        batch = payload["results"]
        raw_received += len(batch)
        pages += 1
        for item in batch:
            if isinstance(item, dict):
                rows.append(_row(item))
            else:
                skipped += 1
        next_cursor = header.get("nextCursor")
        if not batch:
            termination = "empty_page"
            break
        if largest_total is not None and raw_received >= largest_total:
            termination = "reported_total_reached"
            break
        if not isinstance(next_cursor, str) or not next_cursor:
            termination = "no_next_cursor"
            break
        if next_cursor in seen_cursors:
            termination = "repeated_cursor"
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    # Use the first count as the query snapshot; allow for later count changes
    # and report potential incompleteness when malformed records were skipped.
    if largest_total is not None:
        truncated = bool(skipped or len(rows) < largest_total)
    else:
        truncated = bool(skipped or termination != "empty_page")
    log = {
        "query": query,
        "endpoint": ENDPOINT,
        "search_param": "search",
        "scope": "OpenAIRE Graph v3 broad research-product content search; limited to publications, not title/abstract only",
        "filters": ["type=publication"],
        "pagination": "cursor",
        "per_page": per_page,
        "max_pages": max_pages,
        "pages_fetched": pages,
        "pages": pages,
        "numFound": total,
        "total_matches": total,
        "last_page_numFound": last_total,
        "returned": len(rows),
        "records_retrieved": len(rows),
        "raw_records_received": raw_received,
        "invalid_records_skipped": skipped,
        "possibly_truncated": truncated,
        "termination_reason": termination,
        "started_at_utc": started,
        "fetched_at_utc": _timestamp(),
        "description_records": sum(bool(row["Abstract"]) for row in rows),
        "missing_description_records": sum(not row["Abstract"] for row in rows),
        "abstract_note": "Abstract contains the first nonempty OpenAIRE description, which may not be an abstract; missing descriptions remain empty.",
        "license_note": "OpenAIRE Graph metadata is CC-BY; acknowledge OpenAIRE as the source when reusing it.",
    }
    return pd.DataFrame(rows, columns=COLUMNS), log
