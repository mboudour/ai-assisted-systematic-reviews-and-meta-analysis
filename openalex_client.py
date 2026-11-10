"""Credential-safe OpenAlex Works retrieval.

No API call occurs at import.  The page integration entry point is
``fetch_works(query, api_key=None, *, per_page=50, max_pages=2, year_from=None,
year_to=None, publication_types=(), search_scope='title_abstract_exact',
require_abstract=True, anonymous=False)``.  It returns ``(records, metadata)``.
Keyed credentials are sent only in an Authorization Bearer header, never as URL
parameters or in errors/metadata. Explicit anonymous mode sends no key or email
and is limited to one cursor page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

import requests


OPENALEX_CLIENT_RELEASE = 2


class OpenAlexError(RuntimeError):
    """Safe, user-facing error for OpenAlex or transport failures."""


def _remove_authorization(request: requests.PreparedRequest) -> requests.PreparedRequest:
    """Prevent both session auth and implicit .netrc credentials in anonymous mode."""
    request.headers.pop("Authorization", None)
    return request


class OpenAlexClient:
    """Small OpenAlex Works client; ``email`` is accepted but never transmitted.

    A blank or absent key requires explicit ``anonymous=True``. A nonempty
    key cannot be combined with anonymous mode.
    """

    BASE_URL = "https://api.openalex.org/works"
    MAX_PAGE_SIZE = 100
    SUPPORTED_TYPES = frozenset(
        {"article", "book-chapter", "conference-paper", "preprint", "review", "report"}
    )

    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None, *,
                 anonymous: bool = False, timeout: float = 30.0,
                 session: Optional[requests.Session] = None, base_url: str = BASE_URL) -> None:
        if not isinstance(anonymous, bool):
            raise ValueError("anonymous must be a boolean")
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("api_key must be a string or None")
        if not anonymous and (api_key is None or not api_key.strip()):
            raise ValueError("api_key must be a nonempty string unless anonymous=True")
        if anonymous and api_key is not None and api_key.strip():
            raise ValueError("api_key must be empty or None when anonymous=True")
        self.anonymous = anonymous
        self._api_key = None if anonymous else api_key
        _ = email  # Session-local compatibility; OpenAlex does not need it per query.
        self.timeout = timeout
        self.session = session or requests.Session()
        self.base_url = base_url

    def _request(self, params: Mapping[str, Any]) -> requests.Response:
        headers = {} if self.anonymous else {"Authorization": f"Bearer {self._api_key}"}
        request_options: dict[str, Any] = {}
        if self.anonymous:
            # A truthy auth callable prevents Requests from consulting .netrc.
            # Redirects are disabled to guarantee one HTTP request and prevent
            # Requests from re-applying .netrc auth during a redirect.
            request_options = {"auth": _remove_authorization, "allow_redirects": False}
        try:
            response = self.session.get(
                self.base_url,
                params=dict(params),
                headers=headers,
                timeout=self.timeout,
                **request_options,
            )
        except requests.RequestException:
            raise OpenAlexError("OpenAlex request failed due to a network or timeout error") from None
        if response.status_code in {401, 403}:
            if self.anonymous:
                raise OpenAlexError(
                    f"OpenAlex rejected the anonymous request (HTTP {response.status_code}); "
                    "try a verified API key. Anonymous cursor paging is limited to the first page."
                )
            raise OpenAlexError(f"OpenAlex authentication/authorization failed (HTTP {response.status_code})")
        if response.status_code == 429:
            if self.anonymous:
                raise OpenAlexError(
                    "OpenAlex rate limit or daily budget exceeded (HTTP 429); the anonymous "
                    "budget is shared by IP. Wait before retrying or use a verified API key."
                )
            raise OpenAlexError("OpenAlex rate limit or daily budget exceeded (HTTP 429); wait before retrying")
        if self.anonymous and 300 <= response.status_code < 400:
            raise OpenAlexError(f"OpenAlex anonymous request was redirected (HTTP {response.status_code}); please try again")
        if response.status_code >= 400:
            raise OpenAlexError(f"OpenAlex request failed (HTTP {response.status_code})")
        return response


def fetch_works(
    query: str,
    api_key: Optional[str] = None,
    *,
    per_page: int = 50,
    max_pages: int = 2,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    publication_types: Iterable[str] = (),
    search_scope: str = "title_abstract_exact",
    require_abstract: bool = True,
    anonymous: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch OpenAlex Works with bounded cursor pagination.

    ``query`` is passed without altering quotes, Boolean operators, or
    parentheses. ``search_scope`` is ``title_abstract_exact`` or ``broad``;
    the former searches titles and abstracts without stemming. Years are
    inclusive. ``publication_types`` accepts the supported native vocabulary:
    article, book-chapter, conference-paper, preprint, review, report.

    By default a nonempty API key is required. Set ``anonymous=True`` with a
    blank or omitted key to send no key or email. Anonymous retrieval always
    makes one first-cursor-page request, even when ``max_pages`` is higher.
    OpenAlex limits pages to 100 works and shares an anonymous daily budget by
    IP. Metadata reports the effective page cap and whether more may exist.
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

    client = OpenAlexClient(api_key, anonymous=anonymous)
    effective_max_pages = 1 if anonymous else max_pages
    search_param = "search.title_and_abstract.exact" if search_scope == "title_abstract_exact" else "search"
    records: list[dict[str, Any]] = []
    cursor = "*"
    total = 0
    pages = 0
    for _ in range(effective_max_pages):
        params: dict[str, Any] = {
            search_param: query,
            "per-page": min(per_page, OpenAlexClient.MAX_PAGE_SIZE),
            "cursor": cursor,
            "select": "id,doi,title,publication_year,authorships,primary_location,abstract_inverted_index,cited_by_count,concepts,type,referenced_works",
        }
        if filters:
            params["filter"] = ",".join(filters)
        try:
            payload = client._request(params).json()
        except ValueError:
            raise OpenAlexError("OpenAlex returned an invalid response; please try again.") from None
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

    # A continuation cursor is conservative evidence even when count is met;
    # a larger count also signals truncation if a cursor is missing.
    count_indicates_more = (
        isinstance(total, int) and not isinstance(total, bool) and total > len(records)
    )
    cursor_indicates_more = bool(next_cursor and batch and pages == effective_max_pages)
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
        "possibly_truncated": bool(count_indicates_more or cursor_indicates_more),
        "records_retrieved": len(records),
        "per_page": min(per_page, OpenAlexClient.MAX_PAGE_SIZE),
        "max_pages": effective_max_pages,
        "anonymous": anonymous,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return records, metadata
