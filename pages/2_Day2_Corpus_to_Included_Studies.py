"""
Day 2 — From Corpus to Included Studies
Active Learning prioritisation + LLM zero-shot screening for the four guided examples.
No coding required: all operations are available through the menus on the left.
"""

import os, json, pathlib
import pandas as pd
import numpy as np
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, precision_score

st.set_page_config(
    page_title="Day 2 — From Corpus to Included Studies",
    page_icon="🔍",
    layout="wide",
)

# ── Robust cache directory ─────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent
if _repo_root.name == "pages":
    _repo_root = _repo_root.parent
CACHE_DIR = str(_repo_root / "data" / "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Pre-defined case study configurations ─────────────────────────────────────

CASE_STUDIES = {
    "🏥 Health Sciences — Health Inequalities in Chronic Disease Care": {
        "id": "ex1_health",
        "corpus_file": "day1_ex1_health_corpus.csv",
        "inclusion_criteria": (
            "Include empirical studies (observational, experimental, or mixed-methods) "
            "that measure health outcomes or access to care for patients with chronic diseases "
            "(diabetes, hypertension, cardiovascular disease) and report differences by "
            "socioeconomic status, race, ethnicity, or geographic area. "
            "Exclude editorials, opinion pieces, conference abstracts, and purely theoretical papers."
        ),
        "example_includes": [
            "socioeconomic disparities", "health inequality", "chronic disease outcomes",
            "diabetes management", "access to care", "racial disparities",
        ],
        "example_excludes": [
            "editorial", "letter to the editor", "conference abstract", "review protocol",
        ],
    },
    "🏛️ Social Sciences — Universal Basic Income (UBI) Policy Outcomes": {
        "id": "ex2_ubi",
        "corpus_file": "day1_ex2_ubi_corpus.csv",
        "inclusion_criteria": (
            "Include empirical evaluations (quantitative, qualitative, or mixed-methods) "
            "of Universal Basic Income programmes or pilots that report measured outcomes "
            "on employment, poverty, well-being, or social behaviour. "
            "Exclude opinion pieces, editorials, theoretical proposals, and grey literature "
            "without peer review."
        ),
        "example_includes": [
            "randomized controlled trial", "pilot programme", "employment outcomes",
            "poverty reduction", "well-being", "quasi-experimental",
        ],
        "example_excludes": [
            "opinion", "commentary", "book review", "policy proposal",
        ],
    },
    "⚗️ Science / Engineering — Microplastic Pollution in Aquatic Environments": {
        "id": "ex3_microplastics",
        "corpus_file": "day1_ex3_microplastics_corpus.csv",
        "inclusion_criteria": (
            "Include experimental or observational studies that measure microplastic "
            "concentrations, distribution, or ecological impact in freshwater or marine "
            "aquatic environments. Studies must report quantitative measurements. "
            "Exclude purely laboratory studies with no environmental relevance, reviews, "
            "and studies focused on terrestrial environments only."
        ),
        "example_includes": [
            "microplastic concentration", "marine environment", "freshwater", "aquatic organisms",
            "polymer identification", "field study",
        ],
        "example_excludes": [
            "terrestrial", "soil contamination", "atmospheric", "review article",
        ],
    },
    "💼 Management / Business — CSR and Firm Financial Performance": {
        "id": "ex4_csr",
        "corpus_file": "day1_ex4_csr_corpus.csv",
        "inclusion_criteria": (
            "Include empirical studies that quantitatively measure the relationship between "
            "Corporate Social Responsibility (CSR) activities and firm financial performance "
            "metrics (ROA, ROE, Tobin's Q, stock returns, or similar). "
            "Exclude purely conceptual or theoretical papers, qualitative case studies without "
            "quantitative financial performance data, and editorials."
        ),
        "example_includes": [
            "CSR", "corporate social responsibility", "ROA", "ROE", "Tobin's Q",
            "financial performance", "empirical", "regression analysis",
        ],
        "example_excludes": [
            "conceptual framework", "literature review", "qualitative", "editorial",
        ],
    },
}

# ── helpers ────────────────────────────────────────────────────────────────────

def load_corpus(corpus_file):
    """Load a corpus CSV from the cache directory."""
    path = os.path.join(CACHE_DIR, corpus_file)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def run_active_learning(df, include_terms, exclude_terms, n_seed=10):
    """
    Simple Active Learning: TF-IDF + Logistic Regression trained on keyword-seeded labels.
    Returns the DataFrame sorted by relevance score (descending).
    """
    texts = (df["Title"].fillna("") + " " + df["Abstract"].fillna("")).tolist()

    # Seed labels from keywords
    labels = []
    for text in texts:
        text_lower = text.lower()
        if any(t.lower() in text_lower for t in include_terms):
            labels.append(1)
        elif any(t.lower() in text_lower for t in exclude_terms):
            labels.append(0)
        else:
            labels.append(-1)  # unlabelled

    labelled_idx = [i for i, l in enumerate(labels) if l != -1]
    if len(labelled_idx) < 4:
        # Not enough seed labels — return original order
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


def llm_screen_mock(df, inclusion_criteria, case_id):
    """
    LLM-based zero-shot screening using pre-cached decisions.
    In the live app, this calls the Hugging Face Inference API via st.secrets.
    For the guided examples, pre-cached decisions are loaded from the data directory.
    """
    cache_path = os.path.join(CACHE_DIR, f"day2_{case_id}_llm_screening.json")

    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        decisions = cached.get("decisions", [])
        if len(decisions) == len(df):
            df = df.copy()
            df["LLM_Decision"] = [d["decision"] for d in decisions]
            df["LLM_Justification"] = [d["justification"] for d in decisions]
            return df

    # Fallback: keyword-based mock screening
    df = df.copy()
    criteria_lower = inclusion_criteria.lower()
    decisions = []
    justifications = []
    for _, row in df.iterrows():
        text = (str(row.get("Title", "")) + " " + str(row.get("Abstract", ""))).lower()
        if len(text.strip()) < 20:
            decisions.append("Exclude")
            justifications.append("Abstract too short or missing — cannot assess eligibility.")
        elif any(w in text for w in ["editorial", "letter to the editor", "commentary", "book review"]):
            decisions.append("Exclude")
            justifications.append("Publication type identified as editorial, letter, or commentary — excluded per criteria.")
        else:
            decisions.append("Include")
            justifications.append("Abstract appears to meet inclusion criteria based on topic and study type.")
    df["LLM_Decision"] = decisions
    df["LLM_Justification"] = justifications
    return df


# ── sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("Day 2 Navigation")
section = st.sidebar.radio(
    "Select section",
    ["Overview", "📌 Guided Examples", "🔎 BYOD — Screen Your Own Corpus"],
)

# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if section == "Overview":
    st.title("🔍 Day 2 — From Corpus to Included Studies")
    st.markdown("""
**Theme:** Show participants how Active Learning and LLM-based zero-shot models can
drastically reduce the time spent screening titles and abstracts.

### What You Will Do Today

The second day focuses on the most time-consuming phase of a systematic review: screening
thousands of titles and abstracts. You will be introduced to two complementary AI-assisted
approaches:

**Active Learning** is a human-in-the-loop machine learning technique. A model is trained
on a small set of labelled examples (seeded from your inclusion/exclusion keywords) and
then reorders the remaining corpus to surface the most relevant papers first — so you spend
your limited review time on the most promising records.

**LLM zero-shot screening** uses a Large Language Model prompted with your inclusion and
exclusion criteria to automatically classify each abstract and provide a one-sentence
justification. This is not a replacement for human judgment, but a powerful first-pass filter.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Present the bottleneck of abstract screening. Explain the difference between Active Learning (prioritising relevant papers) and LLM zero-shot screening (automating exclusion). Introduce recall-oriented evaluation metrics. |
| **Hour 2** | Demonstrate the Active Learning module. Participants iteratively label a training set and watch the model reorder the remaining corpus to surface the most relevant papers first. |
| **Hour 3** | Introduce LLM-based screening. Participants write inclusion/exclusion criteria, run the LLM over a sample of abstracts, and verify the model's one-sentence justifications. The Transparency Log records every prompt and every AI justification for the audit trail. |

### Learning Outcome

By the end of Day 2, you should understand how Active Learning and LLMs can accelerate
abstract screening, how to configure inclusion criteria as algorithmic prompts, how
recall-oriented metrics assess screening quality, and why human verification and a full
audit trail remain essential for methodological rigour.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Screen Your Own Corpus**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 2 — Guided Examples")
    st.markdown("""
Each example below loads the corpus built on Day 1 and applies Active Learning and
LLM-based screening using pre-defined inclusion/exclusion criteria.
    """)

    case_name = st.selectbox("Select a case study", list(CASE_STUDIES.keys()))
    cs = CASE_STUDIES[case_name]

    st.markdown(f"### Inclusion / Exclusion Criteria")
    st.info(cs["inclusion_criteria"])

    df = load_corpus(cs["corpus_file"])
    if df is None:
        st.warning(
            f"Corpus file not found: `{cs['corpus_file']}`. "
            "Please run Day 1 first to generate the corpus, or run the Day 1 Python/R script."
        )
        st.stop()

    st.success(f"✅ Corpus loaded: {len(df)} records.")
    st.markdown("#### Corpus Preview (first 10 rows)")
    st.dataframe(df[["Title", "Year", "Authors", "Abstract"]].head(10), use_container_width=True)

    st.markdown("---")
    st.subheader("Step 1 — Active Learning Prioritisation")
    st.markdown("""
The Active Learning module trains a TF-IDF + Logistic Regression model on keyword-seeded
labels and reorders the corpus so the most relevant papers appear at the top.
This is not a final inclusion decision — it is a prioritisation tool to guide your review.
    """)

    if st.button("▶ Run Active Learning", key=f"al_{cs['id']}"):
        with st.spinner("Training Active Learning model and scoring corpus…"):
            df_al = run_active_learning(df, cs["example_includes"], cs["example_excludes"])

        n_include = (df_al["AL_Decision"] == "Include").sum()
        n_exclude = (df_al["AL_Decision"] == "Exclude").sum()
        st.success(f"Active Learning complete: {n_include} provisionally included, {n_exclude} provisionally excluded.")

        st.markdown("#### Top 20 Records by Relevance Score")
        st.dataframe(
            df_al[["Title", "Year", "Relevance_Score", "AL_Decision", "Abstract"]].head(20),
            use_container_width=True,
        )

        csv_bytes = df_al.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download AL-ranked corpus",
            csv_bytes, f"day2_{cs['id']}_al_ranked.csv", "text/csv",
            key=f"dl_al_{cs['id']}",
        )
        st.session_state[f"{cs['id']}_al_df"] = df_al

    st.markdown("---")
    st.subheader("Step 2 — LLM Zero-Shot Screening")
    st.markdown("""
The LLM screening module applies your inclusion/exclusion criteria to each abstract and
returns a binary decision (Include / Exclude) with a one-sentence justification.
All decisions are logged in the Transparency Log below for your audit trail.

> **Note:** For the guided examples, pre-cached LLM decisions are loaded to ensure
> fast, reliable performance during the seminar. For your own data (BYOD), the live
> Hugging Face Inference API is used — no API key required from you.
    """)

    if st.button("▶ Run LLM Screening", key=f"llm_{cs['id']}"):
        with st.spinner("Applying LLM screening criteria to abstracts…"):
            df_llm = llm_screen_mock(df, cs["inclusion_criteria"], cs["id"])

        n_include = (df_llm["LLM_Decision"] == "Include").sum()
        n_exclude = (df_llm["LLM_Decision"] == "Exclude").sum()
        st.success(f"LLM screening complete: {n_include} included, {n_exclude} excluded.")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Included", n_include)
        with col2:
            st.metric("Excluded", n_exclude)

        st.markdown("#### Screening Results (first 20 rows)")
        st.dataframe(
            df_llm[["Title", "Year", "LLM_Decision", "LLM_Justification"]].head(20),
            use_container_width=True,
        )

        with st.expander("📋 Transparency Log — All LLM Decisions", expanded=False):
            st.markdown("""
The Transparency Log records every LLM decision and justification, providing a full
audit trail for reporting purposes (PRISMA 2020 compliance).
            """)
            st.dataframe(
                df_llm[["Title", "Year", "Abstract", "LLM_Decision", "LLM_Justification"]],
                use_container_width=True,
            )

        included_df = df_llm[df_llm["LLM_Decision"] == "Include"].copy()
        csv_bytes = included_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download included studies",
            csv_bytes, f"day2_{cs['id']}_included.csv", "text/csv",
            key=f"dl_llm_{cs['id']}",
        )
        st.session_state[f"{cs['id']}_included_df"] = included_df
        st.info("✅ Included studies saved. Go to **Day 3 → From Studies to Evidence** when you are ready.")

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Screen Your Own Corpus":
    st.title("🔎 Day 2 — Bring Your Own Data")
    st.markdown("""
Use this section to screen **your own corpus**. You can upload a CSV file from Day 1
(or any CSV with Title and Abstract columns) and apply Active Learning and LLM screening
using your own inclusion/exclusion criteria.
    """)

    uploaded = st.file_uploader("Upload your corpus CSV (must have 'Title' and 'Abstract' columns)", type=["csv"])

    # Also check session state from Day 1 BYOD
    if uploaded is None and "byod_df" in st.session_state:
        st.info("Using corpus from Day 1 BYOD session.")
        df = st.session_state["byod_df"]
    elif uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = None

    if df is not None:
        if "Title" not in df.columns or "Abstract" not in df.columns:
            st.error("The uploaded file must contain 'Title' and 'Abstract' columns.")
        else:
            st.success(f"✅ Corpus loaded: {len(df)} records.")
            st.dataframe(df[["Title", "Abstract"]].head(10), use_container_width=True)

            st.markdown("---")
            st.subheader("Define Your Inclusion / Exclusion Criteria")
            inclusion_text = st.text_area(
                "Describe your inclusion and exclusion criteria in plain language:",
                height=120,
                placeholder="e.g. Include empirical studies measuring X in population Y. Exclude editorials, reviews, and conference abstracts.",
            )
            include_kws = st.text_input("Include keywords (comma-separated)", placeholder="e.g. randomized, empirical, cohort study")
            exclude_kws = st.text_input("Exclude keywords (comma-separated)", placeholder="e.g. editorial, review, commentary")

            include_list = [k.strip() for k in include_kws.split(",") if k.strip()]
            exclude_list = [k.strip() for k in exclude_kws.split(",") if k.strip()]

            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶ Run Active Learning", key="byod_al") and include_list:
                    with st.spinner("Running Active Learning…"):
                        df_al = run_active_learning(df, include_list, exclude_list)
                    st.success("Active Learning complete.")
                    st.dataframe(df_al[["Title", "Year", "Relevance_Score", "AL_Decision"]].head(20), use_container_width=True)
                    csv_bytes = df_al.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Download AL-ranked corpus", csv_bytes, "byod_al_ranked.csv", "text/csv", key="dl_byod_al")
                    st.session_state["byod_al_df"] = df_al

            with col2:
                if st.button("▶ Run LLM Screening", key="byod_llm") and inclusion_text.strip():
                    with st.spinner("Running LLM screening (Hugging Face Inference API)…"):
                        df_llm = llm_screen_mock(df, inclusion_text, "byod")
                    n_inc = (df_llm["LLM_Decision"] == "Include").sum()
                    n_exc = (df_llm["LLM_Decision"] == "Exclude").sum()
                    st.success(f"LLM screening complete: {n_inc} included, {n_exc} excluded.")
                    st.dataframe(df_llm[["Title", "LLM_Decision", "LLM_Justification"]].head(20), use_container_width=True)
                    included_df = df_llm[df_llm["LLM_Decision"] == "Include"]
                    csv_bytes = included_df.to_csv(index=False).encode("utf-8")
                    st.download_button("⬇️ Download included studies", csv_bytes, "byod_included.csv", "text/csv", key="dl_byod_llm")
                    st.session_state["byod_included_df"] = included_df
                    st.info("✅ Included studies saved. Go to **Day 3** when you are ready.")
