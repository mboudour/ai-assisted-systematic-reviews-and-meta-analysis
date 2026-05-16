"""
Day 1 — API Query and Deduplication
AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar

This script demonstrates how to query OpenAlex and Semantic Scholar for each of the
four guided case studies and deduplicate the resulting corpus.

Run from the repository root:
    python scripts/python/day1/Day1_API_Query_and_Deduplication.py

Requirements: pandas, requests (pip install pandas requests)
For local LLM use in later days: install Ollama from https://ollama.com
"""

import json
import os
import time

import pandas as pd
import requests

# ── Configuration ──────────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CASE_STUDIES = [
    {
        "id": "ex1_health",
        "label": "Health Inequalities in Chronic Disease Care",
        "api": "openalex",
        "query": "health inequalities diabetes care socioeconomic",
        "per_page": 50,
        "max_pages": 2,
    },
    {
        "id": "ex2_ubi",
        "label": "Universal Basic Income (UBI) Policy Outcomes",
        "api": "semantic_scholar",
        "query": "universal basic income policy evaluation outcomes",
        "limit": 50,
    },
    {
        "id": "ex3_microplastics",
        "label": "Microplastic Pollution in Aquatic Environments",
        "api": "openalex",
        "query": "microplastics aquatic marine pollution concentration",
        "per_page": 50,
        "max_pages": 2,
    },
    {
        "id": "ex4_csr",
        "label": "CSR and Firm Financial Performance",
        "api": "openalex",
        "query": "corporate social responsibility firm financial performance empirical",
        "per_page": 50,
        "max_pages": 2,
    },
]

# ── API functions ──────────────────────────────────────────────────────────────

def query_openalex(search_query, per_page=50, max_pages=2):
    """Query the OpenAlex Works API and return a list of record dicts."""
    base = "https://api.openalex.org/works"
    params = {
        "search": search_query,
        "filter": "has_abstract:true,type:article",
        "per_page": per_page,
        "select": "id,doi,title,publication_year,authorships,host_venue,abstract_inverted_index,cited_by_count,concepts",
        "cursor": "*",
    }
    records = []
    for page in range(max_pages):
        print(f"  Fetching page {page + 1}…")
        r = requests.get(base, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("results", [])
        records.extend(batch)
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        params["cursor"] = cursor
        time.sleep(0.5)
    return records


def query_semantic_scholar(search_query, limit=50):
    """Query the Semantic Scholar Graph API."""
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": search_query,
        "limit": limit,
        "fields": "paperId,externalIds,title,year,authors,venue,abstract,citationCount,fieldsOfStudy",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


# ── Flatten functions ──────────────────────────────────────────────────────────

def openalex_to_df(records):
    """Flatten a list of OpenAlex work records into a tidy DataFrame."""
    rows = []
    for r in records:
        inv = r.get("abstract_inverted_index") or {}
        if inv:
            max_pos = max(p for positions in inv.values() for p in positions)
            words = [""] * (max_pos + 1)
            for word, positions in inv.items():
                for p in positions:
                    words[p] = word
            abstract = " ".join(words).strip()
        else:
            abstract = ""
        authors = "; ".join(
            a.get("author", {}).get("display_name", "") or ""
            for a in (r.get("authorships") or [])[:5]
        )
        venue = (r.get("host_venue") or {}).get("display_name", "")
        concepts = "; ".join(c.get("display_name", "") for c in (r.get("concepts") or [])[:5])
        rows.append({
            "ID": r.get("id", ""),
            "DOI": r.get("doi", "") or "",
            "Title": r.get("title", "") or "",
            "Year": r.get("publication_year", ""),
            "Authors": authors,
            "Venue": venue,
            "Abstract": abstract,
            "Citations": r.get("cited_by_count", 0),
            "Concepts": concepts,
        })
    return pd.DataFrame(rows)


def semantic_scholar_to_df(records):
    """Flatten Semantic Scholar records into a tidy DataFrame."""
    rows = []
    for r in records:
        authors = "; ".join(a.get("name", "") for a in (r.get("authors") or [])[:5])
        fields = "; ".join(r.get("fieldsOfStudy") or [])
        doi = (r.get("externalIds") or {}).get("DOI", "") or ""
        rows.append({
            "ID": r.get("paperId", ""),
            "DOI": doi,
            "Title": r.get("title", "") or "",
            "Year": r.get("year", ""),
            "Authors": authors,
            "Venue": r.get("venue", "") or "",
            "Abstract": r.get("abstract", "") or "",
            "Citations": r.get("citationCount", 0),
            "Fields": fields,
        })
    return pd.DataFrame(rows)


def deduplicate_df(df):
    """Remove duplicate records based on DOI then title."""
    has_doi = df[df["DOI"].str.strip().str.len() > 0].copy()
    no_doi = df[df["DOI"].str.strip().str.len() == 0].copy()
    has_doi_deduped = has_doi.drop_duplicates(subset=["DOI"], keep="first")
    no_doi["_title_norm"] = no_doi["Title"].str.lower().str.strip()
    no_doi_deduped = no_doi.drop_duplicates(subset=["_title_norm"], keep="first").drop(columns=["_title_norm"])
    return pd.concat([has_doi_deduped, no_doi_deduped], ignore_index=True)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for cs in CASE_STUDIES:
        print(f"\n{'='*60}")
        print(f"Case Study: {cs['label']}")
        print(f"API: {cs['api']}  |  Query: {cs['query']}")
        print(f"{'='*60}")

        raw_path = os.path.join(OUTPUT_DIR, f"day1_{cs['id']}_raw.json")
        csv_path = os.path.join(OUTPUT_DIR, f"day1_{cs['id']}_corpus.csv")

        # Fetch or load from cache
        if os.path.exists(raw_path):
            print(f"  Loading from cache: {raw_path}")
            with open(raw_path, encoding="utf-8") as f:
                records = json.load(f)
        else:
            print(f"  Fetching from {cs['api']}…")
            if cs["api"] == "openalex":
                records = query_openalex(cs["query"], cs.get("per_page", 50), cs.get("max_pages", 2))
            else:
                records = query_semantic_scholar(cs["query"], cs.get("limit", 50))
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            print(f"  Saved raw JSON: {raw_path}")

        # Flatten and deduplicate
        if cs["api"] == "openalex":
            df = openalex_to_df(records)
        else:
            df = semantic_scholar_to_df(records)

        before = len(df)
        df = deduplicate_df(df)
        after = len(df)
        print(f"  Records retrieved: {before}  |  After deduplication: {after}")

        df.to_csv(csv_path, index=False)
        print(f"  Corpus saved: {csv_path}")

    print("\n✅ All four case study corpora generated successfully.")
