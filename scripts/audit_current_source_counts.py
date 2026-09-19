#!/usr/bin/env python3
"""Query current bibliographic source counts without replacing the historical corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "EvidenceQualityAudit/1.0"


def request_json(url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> tuple[dict, bytes]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}", headers={"User-Agent": USER_AGENT, **(headers or {})}
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
            return json.loads(body), body
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def current_count(case: dict) -> tuple[str, int | None, str, bytes | None]:
    retrieval = case["historical_retrieval"]
    source = retrieval["source"]
    query = retrieval["query"]
    if source == "openalex":
        endpoint = "https://api.openalex.org/works"
        data, body = request_json(
            endpoint,
            {"search": query, "filter": "has_abstract:true", "per-page": 1},
        )
        return endpoint, int(data["meta"]["count"]), "ok", body
    if source == "pubmed":
        endpoint = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        data, body = request_json(
            endpoint,
            {"db": "pubmed", "term": query, "retmax": 0, "retmode": "json"},
        )
        return endpoint, int(data["esearchresult"]["count"]), "ok", body
    if source == "europepmc":
        endpoint = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        data, body = request_json(
            endpoint,
            {"query": query, "resultType": "lite", "pageSize": 1, "format": "json"},
        )
        return endpoint, int(data["hitCount"]), "ok", body
    if source == "semanticscholar":
        endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"
        headers = {}
        if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
        data, body = request_json(
            endpoint,
            {"query": query, "limit": 1, "fields": "title"},
            headers=headers,
        )
        return endpoint, int(data["total"]), "ok", body
    if source == "core":
        return "https://api.core.ac.uk/v3/search/works", None, "not_queried_missing_api_key", None
    return "", None, "unsupported_source", None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    cases = json.loads((root / "config" / "cases.json").read_text(encoding="utf-8"))["cases"]
    raw_response_dir = root / "data" / "interim" / "retrieval_count_audit"
    raw_response_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = int(case["case_id"])
        retrieval = case["historical_retrieval"]
        checked = datetime.now(timezone.utc).isoformat()
        try:
            endpoint, count, status, body = current_count(case)
            error_type = ""
            error_message = ""
        except Exception as exc:
            endpoint = ""
            count = None
            status = "request_failed"
            body = None
            error_type = type(exc).__name__
            error_message = str(exc).strip()[:300]
        response_hash = ""
        if body is not None:
            response_hash = hashlib.sha256(body).hexdigest()
            response_path = raw_response_dir / f"case_{case_id:02d}.json"
            response_path.write_bytes(body)
        rows.append(
            {
                "case_id": case_id,
                "slug": case["slug"],
                "source": retrieval["source"],
                "query_sha256": hashlib.sha256(retrieval["query"].encode("utf-8")).hexdigest(),
                "query_semantics": retrieval["query_semantics"],
                "checked_utc": checked,
                "endpoint": endpoint,
                "current_source_reported_hits": "" if count is None else count,
                "status": status,
                "response_sha256": response_hash,
                "error_type": error_type,
                "error_message": error_message,
            }
        )
        if retrieval["source"] == "semanticscholar":
            time.sleep(2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
