"""Optional browser-local OpenAlex Works component (Streamlit components v1).

Call ``render_browser_openalex(query, key="unique-widget-key", ...)`` from a
Streamlit page. It returns ``None`` until the user explicitly runs a search,
then ``(records, metadata)``. Records use the selected OpenAlex fields expected
by the existing ``openalex_to_df`` converter. ``metadata['request_id']`` is a
fresh random identifier for each successful click, suitable for deduplication
across Streamlit reruns. Changed settings invalidate earlier values, including
when settings are later changed back.

The JSON file is read by JavaScript in the user's browser, not by Streamlit.
The browser sends the API key only in an HTTPS Authorization header to
OpenAlex; the email is not sent. Results and non-secret search settings do go
to the Streamlit server. This depends on trusting the host's supplied code,
the browser and extensions; it is not protection against a malicious host.
Do not pass credentials to this function or put the component inside a form.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_ENDPOINT = "https://api.openalex.org/works"
_TYPES = frozenset({"article", "book-chapter", "conference-paper", "preprint", "review", "report"})
_component = components.declare_component(
    "openalex_browser_component", path=str(Path(__file__).resolve().parent / "openalex_browser_component")
)


def _positive_int(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _config(query: str, per_page: int, max_pages: int, year_from: int | None,
            year_to: int | None, publication_types: Iterable[str],
            search_scope: str, require_abstract: bool) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a nonempty string")
    if not _positive_int(per_page, 1, 100):
        raise ValueError("per_page must be an integer from 1 to 100")
    if not _positive_int(max_pages, 1, 5):
        raise ValueError("max_pages must be an integer from 1 to 5")
    if year_from is not None and not _positive_int(year_from, 1, 9999):
        raise ValueError("year_from must be an integer from 1 to 9999")
    if year_to is not None and not _positive_int(year_to, 1, 9999):
        raise ValueError("year_to must be an integer from 1 to 9999")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError("year_from cannot exceed year_to")
    if isinstance(publication_types, (str, bytes)):
        raise ValueError("publication_types must be an iterable of supported types")
    try:
        types = list(publication_types)
    except TypeError:
        raise ValueError("publication_types must be an iterable of supported types") from None
    if any(not isinstance(t, str) or t not in _TYPES for t in types):
        raise ValueError("unsupported OpenAlex publication type")
    types = list(dict.fromkeys(types))
    if search_scope not in ("title_abstract_exact", "broad"):
        raise ValueError("search_scope must be 'title_abstract_exact' or 'broad'")
    if not isinstance(require_abstract, bool):
        raise ValueError("require_abstract must be a boolean")
    return {"query": query, "per_page": per_page, "max_pages": max_pages,
            "year_from": year_from, "year_to": year_to, "publication_types": types,
            "search_scope": search_scope, "require_abstract": require_abstract}


def _filters(config: dict[str, Any]) -> list[str]:
    result = []
    if config["year_from"] is not None:
        result.append(f"from_publication_date:{config['year_from']:04d}-01-01")
    if config["year_to"] is not None:
        result.append(f"to_publication_date:{config['year_to']:04d}-12-31")
    if config["publication_types"]:
        result.append("type:" + "|".join(config["publication_types"]))
    if config["require_abstract"]:
        result.append("has_abstract:true")
    return result


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise ValueError("invalid result")


def _number(value: Any) -> int | None:
    if value is None or _positive_int(value, 0, 2**53 - 1):
        return value
    raise ValueError("invalid result")


def _object(value: Any, fields: dict[str, Any]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("invalid result")
    return {name: convert(value[name]) for name, convert in fields.items() if name in value}


def _array(value: Any, convert: Any) -> list[Any] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("invalid result")
    return [convert(item) for item in value]


def _abstract(value: Any) -> dict[str, list[int | None]] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or any(not isinstance(word, str) or not isinstance(positions, list)
                                          for word, positions in value.items()):
        raise ValueError("invalid result")
    return {word: [_number(position) for position in positions] for word, positions in value.items()}


def _display(value: Any) -> dict[str, Any] | None:
    return _object(value, {"display_name": _text})


def _work(value: Any) -> dict[str, Any]:
    record = _object(value, {
        "id": _text, "doi": _text, "title": _text, "publication_year": _number,
        "authorships": lambda v: _array(v, lambda a: _object(a, {"author": _display})),
        "primary_location": lambda v: _object(v, {"source": _display}),
        "abstract_inverted_index": _abstract, "cited_by_count": _number,
        "concepts": lambda v: _array(v, _display), "type": _text,
        "referenced_works": lambda v: _array(v, _text),
    })
    if record is None:
        raise ValueError("invalid result")
    return record


def _unpack(value: Any, config: dict[str, Any], config_id: str,
            revision: int) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Reject stale/malformed values and discard unexpected fields defensively."""
    if not isinstance(value, dict) or not isinstance(value.get("metadata"), dict):
        return None
    metadata = value["metadata"]
    filters = _filters(config)
    expected = {
        "config_id": config_id, "config_revision": revision,
        "query": config["query"], "endpoint": _ENDPOINT,
        "search_param": "search" if config["search_scope"] == "broad" else "search.title_and_abstract.exact",
        "scope": config["search_scope"], "filters": filters, "filter": ",".join(filters),
        "per_page": config["per_page"], "max_pages": config["max_pages"],
    }
    if any(metadata.get(k) != v for k, v in expected.items()):
        return None
    request_id = metadata.get("request_id")
    timestamp = metadata.get("fetched_at_utc")
    records = value.get("records")
    total = metadata.get("total_matches")
    pages = metadata.get("pages_fetched")
    if (not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id)
            or not isinstance(timestamp, str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", timestamp)
            or not isinstance(records, list) or len(records) > config["per_page"] * config["max_pages"]
            or (total is not None and not _positive_int(total, 0, 2**53 - 1))
            or not _positive_int(pages, 1, config["max_pages"])
            or len(records) > pages * config["per_page"]
            or metadata.get("pages") != pages or metadata.get("returned_total") != total
            or metadata.get("records_retrieved") != len(records) or metadata.get("returned") != len(records)
            or not isinstance(metadata.get("possibly_truncated"), bool)):
        return None
    try:
        clean_records = [_work(record) for record in records]
    except (TypeError, ValueError):
        return None
    clean_metadata = {**expected, "request_id": request_id, "fetched_at_utc": timestamp,
                      "returned_total": total, "total_matches": total, "pages": pages,
                      "pages_fetched": pages, "returned": len(records),
                      "records_retrieved": len(records),
                      "possibly_truncated": metadata["possibly_truncated"]}
    return clean_records, clean_metadata


def render_browser_openalex(query: str, *, key: str, per_page: int = 50,
                            max_pages: int = 1, year_from: int | None = None,
                            year_to: int | None = None, publication_types: Iterable[str] = (),
                            search_scope: str = "title_abstract_exact",
                            require_abstract: bool = False
                            ) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Render local-file picker and return the latest current-settings result.

    Only explicit clicks in the iframe trigger requests; errors remain in the
    iframe. ``key`` is a Streamlit widget identity, not an OpenAlex API key.
    Each component instance must have a distinct nonempty key. Results persist
    across normal reruns; use ``metadata['request_id']`` to process them once.
    """
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a nonempty Streamlit widget key")
    config = _config(query, per_page, max_pages, year_from, year_to,
                     publication_types, search_scope, require_abstract)
    config_id = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=True,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    state_key = "_browser_openalex_settings_" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    previous = st.session_state.get(state_key)
    if not isinstance(previous, dict):
        revision = 0
    elif previous.get("config_id") == config_id:
        revision = previous.get("revision", 0)
    else:
        revision = previous.get("revision", 0) + 1
    st.session_state[state_key] = {"config_id": config_id, "revision": revision}
    value = _component(**config, config_id=config_id, config_revision=revision, key=key, default=None)
    return _unpack(value, config, config_id, revision)
