"""
01_retrieval.py
---------------
Retrieves raw records for all 20 case studies from their assigned bibliographic databases.
Outputs one CSV per case to data/raw/case_{id:02d}_{slug}.csv

Run:
    python scripts/01_retrieval.py

Requires: api_keys.env in the project root.

Self-healing: any existing output file that is empty or has fewer than 10 rows
is automatically deleted and re-fetched on the next run.
"""

import os, time, re, hashlib, requests
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from tqdm import tqdm

# ── Load API keys ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "api_keys.env")

OPENALEX_EMAIL   = os.getenv("OPENALEX_EMAIL", "")
SCOPUS_KEY       = os.getenv("SCOPUS_API_KEY", "")
CORE_KEY         = os.getenv("CORE_API_KEY", "")
S2_KEY           = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
PHILPAPERS_KEY   = os.getenv("PHILPAPERS_API_KEY", "")
DIMENSIONS_KEY   = os.getenv("DIMENSIONS_API_KEY", "")

RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Case study definitions ────────────────────────────────────────────────────
CASES = [
    # ── Health & Clinical Sciences ──────────────────────────────────────────
    dict(id=1,  slug="nurse_staffing_mortality",
         db="pubmed",
         query='("nurse-to-patient ratio" OR "nursing staffing" OR "staffing ratio") AND ("patient mortality" OR "adverse events" OR "patient outcomes") AND ("acute care" OR "hospital")',
         max_records=5000),
    dict(id=2,  slug="mindfulness_anxiety",
         db="europepmc",
         query='("mindfulness-based" OR "MBSR" OR "MBCT") AND ("anxiety disorder" OR "generalised anxiety" OR "panic disorder") AND ("randomised controlled trial" OR "RCT" OR "meta-analysis")',
         max_records=4000),
    dict(id=3,  slug="glp1_cardiovascular",
         db="openalex",
         query='("GLP-1 receptor agonist" OR "semaglutide" OR "liraglutide" OR "dulaglutide") AND ("cardiovascular outcome" OR "MACE" OR "heart failure" OR "myocardial infarction")',
         max_records=6000),
    dict(id=4,  slug="ai_radiology_diagnosis",
         db="openalex",
         query='("artificial intelligence" OR "deep learning" OR "convolutional neural network") AND ("radiology" OR "medical imaging" OR "diagnostic imaging") AND ("accuracy" OR "sensitivity" OR "specificity")',
         max_records=10000),
    # ── Social & Behavioural Sciences ───────────────────────────────────────
    dict(id=5,  slug="cash_transfers_education",
         db="openalex",
         query='("conditional cash transfer" OR "CCT" OR "unconditional cash transfer") AND ("educational attainment" OR "school enrolment" OR "dropout" OR "attendance")',
         max_records=4500),
    dict(id=6,  slug="social_media_mental_health",
         db="openalex",
         query='("social media" OR "Instagram" OR "TikTok" OR "Facebook") AND ("mental health" OR "depression" OR "anxiety" OR "wellbeing") AND ("adolescent" OR "teenager" OR "youth")',
         max_records=4000),
    dict(id=7,  slug="restorative_justice_recidivism",
         db="core",
         query='("restorative justice" OR "restorative practice" OR "victim-offender mediation") AND ("recidivism" OR "reoffending" OR "criminal behaviour")',
         max_records=5000),
    dict(id=8,  slug="gender_pay_gap",
         db="openalex",
         query='("gender pay gap" OR "gender wage gap" OR "gender earnings gap") AND ("OECD" OR "labour market" OR "wage inequality")',
         max_records=8000),
    # ── Education & Learning Sciences ───────────────────────────────────────
    dict(id=9,  slug="intelligent_tutoring_scores",
         db="openalex",
         query='("intelligent tutoring system" OR "ITS" OR "adaptive learning system") AND ("test scores" OR "academic achievement" OR "learning outcomes") AND ("randomised" OR "experiment" OR "quasi-experiment")',
         max_records=4000),
    dict(id=10, slug="game_based_learning_motivation",
         db="semanticscholar",
         query='game-based learning student motivation engagement gamification',
         max_records=4500),
    dict(id=11, slug="class_size_achievement",
         db="openalex",
         query='("class size" OR "pupil-teacher ratio" OR "student-teacher ratio") AND ("academic achievement" OR "test scores" OR "attainment") AND ("primary school" OR "secondary school" OR "elementary")',
         max_records=5000),
    dict(id=12, slug="llm_higher_education",
         db="core",
         query='("large language model" OR "ChatGPT" OR "GPT-4" OR "generative AI") AND ("higher education" OR "university" OR "college") AND ("pedagogy" OR "teaching" OR "learning" OR "assessment")',
         max_records=9000),
    # ── Environmental & Sustainability Sciences ──────────────────────────────
    dict(id=13, slug="marine_protected_areas",
         db="openalex",
         query='("marine protected area" OR "MPA" OR "ocean reserve") AND ("fish biomass" OR "fish abundance" OR "species richness") AND ("meta-analysis" OR "systematic review" OR "empirical")',
         max_records=4000),
    dict(id=14, slug="reforestation_carbon",
         db="openalex",
         query='("reforestation" OR "afforestation" OR "forest restoration") AND ("carbon sequestration" OR "carbon stock" OR "CO2 uptake") AND ("tropical" OR "temperate" OR "boreal")',
         max_records=4000),
    dict(id=15, slug="indoor_air_pollution_health",
         db="openalex",
         query='("indoor air pollution" OR "household air pollution" OR "biomass fuel") AND ("health outcome" OR "respiratory disease" OR "mortality") AND ("low-income" OR "developing country" OR "sub-Saharan")',
         max_records=6000),
    dict(id=16, slug="microplastics_freshwater",
         db="europepmc",
         query='("microplastic" OR "nanoplastic" OR "plastic pollution") AND ("freshwater" OR "river" OR "lake" OR "drinking water")',
         max_records=8000),
    # ── Computer Science & AI ────────────────────────────────────────────────
    dict(id=17, slug="llm_reasoning_benchmarks",
         db="semanticscholar",
         query='large language model reasoning benchmark evaluation MMLU HellaSwag',
         max_records=4000),
    dict(id=18, slug="federated_learning_privacy",
         db="openalex",
         query='("federated learning" OR "federated machine learning") AND ("privacy" OR "differential privacy" OR "data leakage") AND ("utility" OR "accuracy" OR "performance trade-off")',
         max_records=5000),
    dict(id=19, slug="ai_ethics_autonomous_systems",
         db="semanticscholar",
         query='autonomous system ethical framework moral responsibility algorithmic accountability AI ethics',
         max_records=3000),
    dict(id=20, slug="deep_learning_predictive_maintenance",
         db="openalex",
         query='("deep learning" OR "neural network" OR "convolutional neural network") AND ("predictive maintenance" OR "condition monitoring" OR "fault detection") AND ("manufacturing" OR "industrial")',
         max_records=10000),
]

# ── Utility: deduplication ────────────────────────────────────────────────────
def dedup(records: list) -> list:
    seen_dois, seen_hashes, out = set(), set(), []
    for r in records:
        doi = (r.get("doi") or "").strip().lower()
        title_hash = hashlib.md5((r.get("title") or "").strip().lower().encode()).hexdigest()
        if doi and doi in seen_dois:
            continue
        if title_hash in seen_hashes:
            continue
        if doi:
            seen_dois.add(doi)
        seen_hashes.add(title_hash)
        out.append(r)
    return out

# ── Self-healing: remove empty or near-empty output files ────────────────────
def purge_empty_outputs():
    """Remove output files that are empty, corrupt, or have <50% abstract coverage."""
    removed = []
    for f in RAW_DIR.glob("case_*.csv"):
        try:
            df = pd.read_csv(f)
            if len(df) < 10:
                f.unlink(); removed.append(f.name + " (empty)"); continue
            cov = (df["abstract"].fillna("").astype(str).str.len() > 10).mean()
            if cov < 0.50:
                f.unlink(); removed.append(f.name + f" (abstract cov {cov:.0%})")
        except Exception:
            f.unlink()
            removed.append(f.name + " (corrupt)")
    if removed:
        print(f"[CLEANUP] Removed {len(removed)} file(s): {', '.join(removed)}")

# ── Reconstruct abstract from OpenAlex inverted index ────────────────────────
def reconstruct_abstract(inv: dict) -> str:
    if not inv:
        return ""
    try:
        max_pos = max(p for positions in inv.values() for p in positions)
        words = [""] * (max_pos + 1)
        for word, positions in inv.items():
            for p in positions:
                words[p] = word
        return " ".join(words)
    except Exception:
        return ""

# ── Per-database retrieval functions ─────────────────────────────────────────

def retrieve_openalex(case: dict) -> list:
    records, cursor = [], "*"
    per_page = 200
    headers = {"User-Agent": f"mailto:{OPENALEX_EMAIL}"} if OPENALEX_EMAIL else {}
    pbar = tqdm(desc=f"  OpenAlex case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        params = {
            "search": case["query"],
            "filter": "has_abstract:true",
            "per-page": per_page,
            "cursor": cursor,
            "select": "id,doi,title,publication_year,abstract_inverted_index",
        }
        try:
            resp = requests.get("https://api.openalex.org/works",
                                params=params, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"\n  [OpenAlex error] {e}")
            time.sleep(5)
            break
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        for r in results:
            records.append({
                "title":    r.get("title", ""),
                "year":     r.get("publication_year", ""),
                "doi":      r.get("doi", ""),
                "abstract": reconstruct_abstract(r.get("abstract_inverted_index") or {}),
                "source":   "OpenAlex",
                "case_id":  case["id"],
            })
        pbar.update(len(results))
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.1)
    pbar.close()
    return records


def retrieve_pubmed(case: dict) -> list:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    try:
        search_resp = requests.get(base + "esearch.fcgi", params={
            "db": "pubmed", "term": case["query"],
            "retmax": min(case["max_records"], 9999),
            "retmode": "json", "usehistory": "y",
        }, timeout=30)
        search_resp.raise_for_status()
    except Exception as e:
        print(f"\n  [PubMed search error] {e}")
        return []
    search_data = search_resp.json()
    webenv    = search_data["esearchresult"]["webenv"]
    query_key = search_data["esearchresult"]["querykey"]
    total     = int(search_data["esearchresult"]["count"])
    records, batch = [], 200
    for start in tqdm(range(0, min(total, case["max_records"]), batch),
                      desc=f"  PubMed case {case['id']}", unit="batch"):
        for attempt in range(3):
            try:
                fetch_resp = requests.get(base + "efetch.fcgi", params={
                    "db": "pubmed", "rettype": "abstract", "retmode": "xml",
                    "retstart": start, "retmax": batch,
                    "webenv": webenv, "query_key": query_key,
                }, timeout=60)
                fetch_resp.raise_for_status()
                break
            except requests.exceptions.ReadTimeout:
                time.sleep(5 * (attempt + 1))
        else:
            continue
        titles    = re.findall(r"<ArticleTitle>(.*?)</ArticleTitle>", fetch_resp.text, re.S)
        abstracts = re.findall(r"<AbstractText.*?>(.*?)</AbstractText>", fetch_resp.text, re.S)
        years     = re.findall(r"<PubDate>.*?<Year>(\d{4})</Year>", fetch_resp.text, re.S)
        dois      = re.findall(r'<ArticleId IdType="doi">(.*?)</ArticleId>', fetch_resp.text)
        for i, title in enumerate(titles):
            records.append({
                "title":    re.sub(r"<[^>]+>", "", title).strip(),
                "year":     years[i] if i < len(years) else "",
                "doi":      dois[i] if i < len(dois) else "",
                "abstract": re.sub(r"<[^>]+>", "", abstracts[i]).strip() if i < len(abstracts) else "",
                "source":   "PubMed",
                "case_id":  case["id"],
            })
        time.sleep(0.35)
    return records


def retrieve_europepmc(case: dict) -> list:
    records, cursor = [], None
    pbar = tqdm(desc=f"  EuropePMC case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        params = {
            "query": case["query"],
            "resultType": "core",
            "pageSize": 1000,
            "format": "json",
        }
        if cursor:
            params["cursorMark"] = cursor
        try:
            resp = requests.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params=params, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            print(f"\n  [EuropePMC error] {e}")
            time.sleep(5)
            break
        data    = resp.json()
        results = data.get("resultList", {}).get("result", [])
        if not results:
            break
        for r in results:
            records.append({
                "title":    r.get("title", ""),
                "year":     r.get("pubYear", ""),
                "doi":      r.get("doi", ""),
                "abstract": r.get("abstractText", ""),
                "source":   "EuropePMC",
                "case_id":  case["id"],
            })
        pbar.update(len(results))
        new_cursor = data.get("nextCursorMark")
        if not new_cursor or new_cursor == cursor:
            break
        cursor = new_cursor
        time.sleep(0.2)
    pbar.close()
    return records


def retrieve_core(case: dict) -> list:
    if not CORE_KEY:
        print(f"  [SKIP] CORE key not set for case {case['id']}")
        return []
    records, offset = [], 0
    pbar = tqdm(desc=f"  CORE case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        for attempt in range(3):
            try:
                resp = requests.post(
                    "https://api.core.ac.uk/v3/search/works",
                    json={"q": case["query"], "limit": 100, "offset": offset},
                    headers={"Authorization": f"Bearer {CORE_KEY}"},
                    timeout=90)
                break
            except requests.exceptions.ReadTimeout:
                print(f"\n  [CORE timeout at offset {offset}] retry {attempt+1}/3...")
                time.sleep(10 * (attempt + 1))
        else:
            print(f"\n  [CORE] giving up at offset {offset}")
            break
        if resp.status_code == 429:
            time.sleep(10)
            continue
        if not resp.ok:
            print(f"\n  [CORE error {resp.status_code}] {resp.text[:200]}")
            break
        results = resp.json().get("results", [])
        if not results:
            break
        for r in results:
            records.append({
                "title":    r.get("title", ""),
                "year":     r.get("yearPublished", ""),
                "doi":      r.get("doi", ""),
                "abstract": r.get("abstract", ""),
                "source":   "CORE",
                "case_id":  case["id"],
            })
        pbar.update(len(results))
        offset += 100
        time.sleep(0.3)
    pbar.close()
    return records


def retrieve_semanticscholar(case: dict) -> list:
    """
    Semantic Scholar Graph API.
    Note: uses simple keyword query (no boolean operators) — S2 search
    does not support boolean syntax. Complex queries are simplified to
    keyword form in the CASES definition above.
    """
    headers = {"x-api-key": S2_KEY} if S2_KEY else {}
    records, offset = [], 0
    pbar = tqdm(desc=f"  SemanticScholar case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        for attempt in range(5):
            try:
                resp = requests.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query":  case["query"],
                        "fields": "title,year,externalIds,abstract",
                        "limit":  100,
                        "offset": offset,
                    },
                    headers=headers, timeout=30)
            except requests.exceptions.ReadTimeout:
                time.sleep(10)
                continue
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"\n  [S2 rate limit] waiting {wait}s...")
                time.sleep(wait)
                continue
            break
        if not resp.ok:
            print(f"\n  [S2 error {resp.status_code}] {resp.text[:200]}")
            break
        data    = resp.json()
        results = data.get("data", [])
        if not results:
            break
        for r in results:
            records.append({
                "title":    r.get("title", ""),
                "year":     r.get("year", ""),
                "doi":      (r.get("externalIds") or {}).get("DOI", ""),
                "abstract": r.get("abstract") or "",
                "source":   "SemanticScholar",
                "case_id":  case["id"],
            })
        pbar.update(len(results))
        # S2 caps offset at 10000
        offset += 100
        if offset >= min(case["max_records"], 10000):
            break
        time.sleep(3.0)   # S2 unauthenticated: ~1 req/3s; authenticated: ~1 req/s
    pbar.close()
    return records


def retrieve_dimensions(case: dict) -> list:
    """
    Dimensions Analytics API via DSL.
    Uses keyword-only search (no nested quotes) to avoid DSL parser errors.
    Extracts unquoted keywords from the boolean query for the search string.
    """
    if not DIMENSIONS_KEY:
        print(f"  [SKIP] Dimensions key not set for case {case['id']}")
        return []
    # Authenticate
    try:
        auth = requests.post("https://app.dimensions.ai/api/auth",
            json={"key": DIMENSIONS_KEY}, timeout=20)
        auth.raise_for_status()
        token = auth.json()["token"]
    except Exception as e:
        print(f"  [Dimensions auth error] {e}")
        return []

    # Build a simple keyword search string:
    # Strip all boolean operators and quotes, keep only the key terms.
    # Dimensions DSL `for "..."` does NOT support nested quotes or boolean ops.
    raw = re.sub(r'["()]+', ' ', case["query"])          # remove quotes/parens
    raw = re.sub(r'\b(AND|OR|NOT)\b', ' ', raw)          # remove boolean ops
    keywords = re.sub(r'\s+', ' ', raw).strip()[:200]    # collapse whitespace, cap length

    records, skip = [], 0
    pbar = tqdm(desc=f"  Dimensions case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        limit = min(500, case["max_records"] - len(records))
        dsl = (
            f'search publications in title_abstract_only '
            f'for "{keywords}" '
            f'return publications[id+title+year+doi+abstract][{skip}:{skip+limit}]'
        )
        resp = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    "https://app.dimensions.ai/api/dsl.json",
                    data=dsl,
                    headers={"Authorization": f"JWT {token}"},
                    timeout=60)
            except requests.exceptions.ReadTimeout:
                time.sleep(10 * (attempt + 1))
                continue
            if resp.status_code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            if resp.status_code == 403:
                try:
                    auth2 = requests.post("https://app.dimensions.ai/api/auth",
                        json={"key": DIMENSIONS_KEY}, timeout=20)
                    auth2.raise_for_status()
                    token = auth2.json()["token"]
                except Exception:
                    pass
                continue
            break
        if resp is None or not resp.ok:
            print(f"\n  [Dimensions ERROR {resp.status_code if resp else 'None'}] "
                  f"{resp.text[:300] if resp else ''}")
            break
        pubs = resp.json().get("publications", [])
        if not pubs:
            break
        for p in pubs:
            records.append({
                "title":    p.get("title", ""),
                "year":     p.get("year", ""),
                "doi":      p.get("doi", ""),
                "abstract": p.get("abstract", ""),
                "source":   "Dimensions",
                "case_id":  case["id"],
            })
        pbar.update(len(pubs))
        skip += limit
        time.sleep(0.5)
    pbar.close()
    return records


def retrieve_crossref(case: dict) -> list:
    records, offset = [], 0
    pbar = tqdm(desc=f"  Crossref case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        try:
            resp = requests.get("https://api.crossref.org/works", params={
                "query":   case["query"],
                "rows":    1000,
                "offset":  offset,
                "select":  "title,published,DOI,abstract",
                "mailto":  OPENALEX_EMAIL,
            }, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"\n  [Crossref error] {e}")
            break
        items = resp.json().get("message", {}).get("items", [])
        if not items:
            break
        for item in items:
            title = " ".join(item.get("title", []))
            year  = ""
            pub   = item.get("published", {})
            if pub.get("date-parts"):
                year = str(pub["date-parts"][0][0])
            records.append({
                "title":    title,
                "year":     year,
                "doi":      item.get("DOI", ""),
                "abstract": re.sub(r"<[^>]+>", "", item.get("abstract", "")),
                "source":   "Crossref",
                "case_id":  case["id"],
            })
        pbar.update(len(items))
        offset += 1000
        time.sleep(0.2)
    pbar.close()
    return records


def retrieve_philpapers(case: dict) -> list:
    records, page = [], 1
    pbar = tqdm(desc=f"  PhilPapers case {case['id']}", unit="rec")
    while len(records) < case["max_records"]:
        try:
            resp = requests.get("https://philpapers.org/api/search", params={
                "query":    case["query"],
                "format":   "json",
                "page":     page,
                "per_page": 100,
            }, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"\n  [PhilPapers error] {e}")
            break
        data  = resp.json()
        items = data.get("entries", [])
        if not items:
            break
        for item in items:
            records.append({
                "title":    item.get("title", ""),
                "year":     str(item.get("pub_year", "")),
                "doi":      item.get("doi", ""),
                "abstract": item.get("abstract", ""),
                "source":   "PhilPapers",
                "case_id":  case["id"],
            })
        pbar.update(len(items))
        page += 1
        time.sleep(0.5)
    pbar.close()
    return records


# ── Dispatch table ────────────────────────────────────────────────────────────
RETRIEVERS = {
    "openalex":        retrieve_openalex,
    "pubmed":          retrieve_pubmed,
    "europepmc":       retrieve_europepmc,
    "core":            retrieve_core,
    "semanticscholar": retrieve_semanticscholar,
    "dimensions":      retrieve_dimensions,
    "crossref":        retrieve_crossref,
    "philpapers":      retrieve_philpapers,
}

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Self-heal: remove any empty or corrupt output files before starting
    purge_empty_outputs()

    summary_rows = []
    for case in tqdm(CASES, desc="Overall progress", unit="case"):
        out_path = RAW_DIR / f"case_{case['id']:02d}_{case['slug']}.csv"

        if out_path.exists():
            print(f"[SKIP] Case {case['id']:02d} already retrieved: {out_path.name}")
            df = pd.read_csv(out_path)
            summary_rows.append({
                "case_id":           case["id"],
                "slug":              case["slug"],
                "db":                case["db"],
                "raw":               len(df),
                "after_dedup":       len(df),
                "abstract_coverage": round((df["abstract"].fillna("").astype(str).str.len() > 10).mean(), 4),
            })
            continue

        print(f"\n[CASE {case['id']:02d}] {case['slug']} → {case['db'].upper()}")
        retriever = RETRIEVERS.get(case["db"])
        if retriever is None:
            print(f"  [ERROR] No retriever for db={case['db']}")
            continue

        records = []
        try:
            records = retriever(case)
        except Exception as exc:
            print(f"  [ERROR] {exc}")

        raw_n    = len(records)
        records  = dedup(records)
        dedup_n  = len(records)

        if dedup_n == 0:
            print(f"  [WARN] No records retrieved for case {case['id']} — skipping file write.")
            summary_rows.append({
                "case_id": case["id"], "slug": case["slug"], "db": case["db"],
                "raw": 0, "after_dedup": 0, "abstract_coverage": 0.0,
            })
            continue

        df = pd.DataFrame(records)
        df.to_csv(out_path, index=False)
        abstract_cov = (df["abstract"].str.len() > 10).mean()
        flag = "✓" if abstract_cov > 0.5 else "⚠ LOW"
        print(f"  Raw: {raw_n} → After dedup: {dedup_n} | Abstract coverage: {abstract_cov:.1%}  {flag}")
        summary_rows.append({
            "case_id":           case["id"],
            "slug":              case["slug"],
            "db":                case["db"],
            "raw":               raw_n,
            "after_dedup":       dedup_n,
            "abstract_coverage": round(abstract_cov, 4),
        })

    # Save retrieval summary
    summary_df   = pd.DataFrame(summary_rows)
    summary_path = ROOT / "outputs" / "retrieval_summary.csv"
    summary_path.parent.mkdir(exist_ok=True)
    summary_df.to_csv(summary_path, index=False)
    print(f"\nRetrieval summary saved to {summary_path}")
    print("\nPer-case abstract coverage:")
    for row in summary_rows:
        cov  = row.get("abstract_coverage", 0)
        flag = "✓" if cov > 0.5 else "⚠ LOW"
        print(f"  Case {row['case_id']:02d} ({row['db']:>15s}): {cov:.1%}  {flag}")


if __name__ == "__main__":
    main()
