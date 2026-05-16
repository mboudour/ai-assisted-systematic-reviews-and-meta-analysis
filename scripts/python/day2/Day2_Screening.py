"""
Day 2 — Active Learning and LLM Screening
AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar

This script demonstrates Active Learning (TF-IDF + Logistic Regression) and
LLM zero-shot screening (via Ollama for fully local, offline use) for the four
guided case studies.

Run from the repository root:
    python scripts/python/day2/Day2_Screening.py

Requirements: pandas, scikit-learn, requests
For local LLM: install Ollama from https://ollama.com and run:
    ollama pull llama3:8b
"""

import json
import os
import time

import numpy as np
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# ── Configuration ──────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b"

CASE_STUDIES = [
    {
        "id": "ex1_health",
        "label": "Health Inequalities in Chronic Disease Care",
        "corpus_file": "day1_ex1_health_corpus.csv",
        "inclusion_criteria": (
            "Include empirical studies (observational, experimental, or mixed-methods) "
            "that measure health outcomes or access to care for patients with chronic diseases "
            "(diabetes, hypertension, cardiovascular disease) and report differences by "
            "socioeconomic status, race, ethnicity, or geographic area. "
            "Exclude editorials, opinion pieces, conference abstracts, and purely theoretical papers."
        ),
        "include_terms": ["socioeconomic disparities", "health inequality", "chronic disease outcomes",
                          "diabetes management", "access to care", "racial disparities"],
        "exclude_terms": ["editorial", "letter to the editor", "conference abstract", "review protocol"],
    },
    {
        "id": "ex2_ubi",
        "label": "Universal Basic Income (UBI) Policy Outcomes",
        "corpus_file": "day1_ex2_ubi_corpus.csv",
        "inclusion_criteria": (
            "Include empirical evaluations (quantitative, qualitative, or mixed-methods) "
            "of Universal Basic Income programmes or pilots that report measured outcomes "
            "on employment, poverty, well-being, or social behaviour. "
            "Exclude opinion pieces, editorials, theoretical proposals, and grey literature."
        ),
        "include_terms": ["randomized controlled trial", "pilot programme", "employment outcomes",
                          "poverty reduction", "well-being", "quasi-experimental"],
        "exclude_terms": ["opinion", "commentary", "book review", "policy proposal"],
    },
    {
        "id": "ex3_microplastics",
        "label": "Microplastic Pollution in Aquatic Environments",
        "corpus_file": "day1_ex3_microplastics_corpus.csv",
        "inclusion_criteria": (
            "Include experimental or observational studies that measure microplastic "
            "concentrations, distribution, or ecological impact in freshwater or marine "
            "aquatic environments. Studies must report quantitative measurements. "
            "Exclude purely laboratory studies with no environmental relevance, reviews, "
            "and studies focused on terrestrial environments only."
        ),
        "include_terms": ["microplastic concentration", "marine environment", "freshwater",
                          "aquatic organisms", "polymer identification", "field study"],
        "exclude_terms": ["terrestrial", "soil contamination", "atmospheric", "review article"],
    },
    {
        "id": "ex4_csr",
        "label": "CSR and Firm Financial Performance",
        "corpus_file": "day1_ex4_csr_corpus.csv",
        "inclusion_criteria": (
            "Include empirical studies that quantitatively measure the relationship between "
            "Corporate Social Responsibility (CSR) activities and firm financial performance "
            "metrics (ROA, ROE, Tobin's Q, stock returns, or similar). "
            "Exclude purely conceptual or theoretical papers, qualitative case studies without "
            "quantitative financial performance data, and editorials."
        ),
        "include_terms": ["CSR", "corporate social responsibility", "ROA", "ROE", "Tobin's Q",
                          "financial performance", "empirical", "regression analysis"],
        "exclude_terms": ["conceptual framework", "literature review", "qualitative", "editorial"],
    },
]

# ── Active Learning ────────────────────────────────────────────────────────────

def run_active_learning(df, include_terms, exclude_terms):
    """TF-IDF + Logistic Regression Active Learning with keyword-seeded labels."""
    texts = (df["Title"].fillna("") + " " + df["Abstract"].fillna("")).tolist()
    labels = []
    for text in texts:
        text_lower = text.lower()
        if any(t.lower() in text_lower for t in include_terms):
            labels.append(1)
        elif any(t.lower() in text_lower for t in exclude_terms):
            labels.append(0)
        else:
            labels.append(-1)

    labelled_idx = [i for i, l in enumerate(labels) if l != -1]
    if len(labelled_idx) < 4:
        df = df.copy()
        df["Relevance_Score"] = 0.5
        df["AL_Decision"] = "Unlabelled"
        return df

    X_texts = [texts[i] for i in labelled_idx]
    y = [labels[i] for i in labelled_idx]

    vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True)
    X_train = vec.fit_transform(X_texts)
    X_all = vec.transform(texts)

    clf = LogisticRegression(max_iter=500, C=1.0)
    clf.fit(X_train, y)

    scores = clf.predict_proba(X_all)[:, 1]
    preds = clf.predict(X_all)

    df = df.copy()
    df["Relevance_Score"] = np.round(scores, 3)
    df["AL_Decision"] = ["Include" if p == 1 else "Exclude" for p in preds]
    df = df.sort_values("Relevance_Score", ascending=False).reset_index(drop=True)
    return df

# ── LLM Screening via Ollama ───────────────────────────────────────────────────

def llm_screen_ollama(title, abstract, inclusion_criteria, model=OLLAMA_MODEL):
    """
    Zero-shot LLM screening using Ollama (fully local, no API key required).
    Returns a dict with 'decision' (Include/Exclude) and 'justification'.
    """
    prompt = f"""You are a systematic review screener. Apply the following inclusion/exclusion criteria to the study below.
Respond with exactly two lines:
Line 1: Decision: Include OR Decision: Exclude
Line 2: Justification: [one sentence explaining the decision]

Inclusion/Exclusion Criteria:
{inclusion_criteria}

Study Title: {title}
Abstract: {abstract[:500]}

Your response:"""

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        r.raise_for_status()
        response_text = r.json().get("response", "").strip()
        lines = response_text.split("\n")
        decision = "Include" if "Include" in lines[0] else "Exclude"
        justification = lines[1].replace("Justification:", "").strip() if len(lines) > 1 else ""
        return {"decision": decision, "justification": justification}
    except Exception as e:
        return {"decision": "Exclude", "justification": f"LLM error: {e}"}


def check_ollama_available():
    """Check if Ollama is running locally."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ollama_available = check_ollama_available()
    if not ollama_available:
        print("⚠️  Ollama is not running. LLM screening will be skipped.")
        print("   To enable: install Ollama from https://ollama.com, then run: ollama pull llama3:8b")

    for cs in CASE_STUDIES:
        print(f"\n{'='*60}")
        print(f"Case Study: {cs['label']}")
        print(f"{'='*60}")

        corpus_path = os.path.join(DATA_DIR, cs["corpus_file"])
        if not os.path.exists(corpus_path):
            print(f"  ⚠️  Corpus not found: {corpus_path}. Run Day 1 script first.")
            continue

        df = pd.read_csv(corpus_path)
        print(f"  Corpus loaded: {len(df)} records.")

        # Active Learning
        print("  Running Active Learning…")
        df_al = run_active_learning(df, cs["include_terms"], cs["exclude_terms"])
        n_inc = (df_al["AL_Decision"] == "Include").sum()
        n_exc = (df_al["AL_Decision"] == "Exclude").sum()
        print(f"  AL result: {n_inc} included, {n_exc} excluded.")

        al_path = os.path.join(DATA_DIR, f"day2_{cs['id']}_al_ranked.csv")
        df_al.to_csv(al_path, index=False)
        print(f"  AL-ranked corpus saved: {al_path}")

        # LLM Screening (if Ollama is available)
        if ollama_available:
            print(f"  Running LLM screening (Ollama / {OLLAMA_MODEL})…")
            decisions = []
            for i, row in df.iterrows():
                if i % 10 == 0:
                    print(f"    Screening record {i+1}/{len(df)}…")
                result = llm_screen_ollama(
                    str(row.get("Title", "")),
                    str(row.get("Abstract", "")),
                    cs["inclusion_criteria"],
                )
                decisions.append(result)
                time.sleep(0.1)

            df_llm = df.copy()
            df_llm["LLM_Decision"] = [d["decision"] for d in decisions]
            df_llm["LLM_Justification"] = [d["justification"] for d in decisions]

            llm_path = os.path.join(DATA_DIR, f"day2_{cs['id']}_llm_screening.csv")
            df_llm.to_csv(llm_path, index=False)
            print(f"  LLM screening saved: {llm_path}")

            # Cache decisions as JSON for Streamlit app
            cache_path = os.path.join(DATA_DIR, f"day2_{cs['id']}_llm_screening.json")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"decisions": decisions}, f, indent=2)
            print(f"  LLM decisions cached: {cache_path}")

    print("\n✅ Day 2 screening complete.")
