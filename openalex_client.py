"""Credential-safe OpenAlex Works retrieval.

No API call occurs at import.  The page integration entry point is
``fetch_works(query, api_key, *, per_page=50, max_pages=2, year_from=None,
year_to=None, publication_types=(), search_scope='title_abstract_exact',
require_abstract=True)``.  It returns ``(records, metadata)``.  Credentials are
sent only in an Authorization Bearer header, never as URL parameters or in
errors/metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

import requests


class OpenAlexError(RuntimeError):
    """Safe, user-facing error for OpenAlex or transport failures."""


class OpenAlexClient:
    """Small OpenAlex Works client; ``email`` is accepted but never transmitted."""

    BASE_URL = "https://api.openalex.org/works"
    MAX_PAGE_SIZE = 100
    SUPPORTED_TYPES = frozenset(
        {"article", "book-chapter", "conference-paper", "preprint", "review", "report"}
    )

    def __init__(self, api_key: str, email: Optional[str] = None, *, timeout: float = 30.0,
                 session: Optional[requests.Session] = None, base_url: str = BASE_URL) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a nonempty string")
        self._api_key = api_key
        _ = email  # Session-local compatibility; OpenAlex does not need it per query.
        self.timeout = timeout
        self.session = session or requests.Session()
        self.base_url = base_url

    def _request(self, params: Mapping[str, Any]) -> requests.Response:
        try:
            response = self.session.get(
                self.base_url,
                params=dict(params),
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise OpenAlexError("OpenAlex request failed due to a network or timeout error") from exc
        if response.status_code in {401, 403}:
            raise OpenAlexError(f"OpenAlex authentication/authorization failed (HTTP {response.status_code})")
        if response.status_code == 429:
            raise OpenAlexError("OpenAlex rate limit exceeded (HTTP 429)")
        if response.status_code >= 400:
            raise OpenAlexError(f"OpenAlex request failed (HTTP {response.status_code})")
        return response


def fetch_works(
    query: str,
    api_key: str,
    *,
    per_page: int = 50,
    max_pages: int = 2,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    publication_types: Iterable[str] = (),
    search_scope: str = "title_abstract_exact",
    require_abstract: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch OpenAlex Works with bounded cursor pagination.

    ``query`` is passed without altering quotes, Boolean operators, or
    parentheses. ``search_scope`` is ``title_abstract_exact`` or ``broad``;
    the former searches titles and abstracts without stemming. Years are
    inclusive. ``publication_types`` accepts the supported native vocabulary:
    article, book-chapter, conference-paper, preprint, review, report.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a nonempty string")
    if search_scope not in {"title_abstract_exact", "broad"}:
        raise ValueError("search_scope must be 'title_abstract_exact' or 'broad'")
    if not isinstance(per_page, int) or isinstance(per_page, bool) or per_page < 1:
        raise ValueError("per_page must be a positive integer")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")
    if not isinstance(require_abstract, bool):
        raise ValueError("require_abstract must be a boolean")
    if year_from is not None and (not isinstance(year_from, int) or isinstance(year_from, bool)):
        raise ValueError("year_from must be an integer")
    if year_to is not None and (not isinstance(year_to, int) or isinstance(year_to, bool)):
        raise ValueError("year_to must be an integer")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError("year_from cannot exceed year_to")
    types = list(publication_types)
    if any(item not in OpenAlexClient.SUPPORTED_TYPES for item in types):
        raise ValueError("unsupported OpenAlex publication type")

    filters = []
    if year_from is not None:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to is not None:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if types:
        filters.append("type:" + "|".join(types))
    if require_abstract:
        filters.append("has_abstract:true")

    client = OpenAlexClient(api_key)
    search_param = "search.title_and_abstract.exact" if search_scope == "title_abstract_exact" else "search"
    records: list[dict[str, Any]] = []
    cursor = "*"
    total = 0
    pages = 0
    for _ in range(max_pages):
        params: dict[str, Any] = {
            search_param: query,
            "per-page": min(per_page, OpenAlexClient.MAX_PAGE_SIZE),
            "cursor": cursor,
            "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index,cited_by_count,concepts,type",
        }
        if filters:
            params["filter"] = ",".join(filters)
        try:
            payload = client._request(params).json()
        except ValueError as exc:
            raise OpenAlexError("OpenAlex returned an invalid response; please try again.") from exc
        meta = payload.get("meta") or {}
        if pages == 0:
            total = meta.get("count", 0)
        batch = payload.get("results") or []
        records.extend(batch)
        pages += 1
        next_cursor = meta.get("next_cursor")
        if not batch or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    metadata = {
        "query": query,
        "endpoint": OpenAlexClient.BASE_URL,
        "search_param": search_param,
        "scope": search_scope,
        "filters": filters,
        "filter": ",".join(filters),
        "returned_total": total,
        "total_matches": total,
        "pages": pages,
        "pages_fetched": pages,
        "possibly_truncated": bool(next_cursor and batch and pages == max_pages),
        "records_retrieved": len(records),
        "per_page": min(per_page, OpenAlexClient.MAX_PAGE_SIZE),
        "max_pages": max_pages,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return records, metadata
