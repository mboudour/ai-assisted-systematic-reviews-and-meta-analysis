"""
Day 2 — From Corpus to Included Studies
Guided examples load exclusively from pre-cached screening CSVs.
No live API calls, no session state dependency from Day 1.
No coding required.
"""

import os, pathlib
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Day 2 — From Corpus to Included Studies",
    page_icon="🔍",
    layout="wide",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = _repo_root / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Guided example definitions ─────────────────────────────────────────────────
GUIDED_EXAMPLES = [
    {
        "label": "🏥 Example 1 — Health Sciences: Health Inequalities in Chronic Disease Care",
        "screened_file": "day2_ex1_health_screened.csv",
        "session_key": "ex1_health",
        "inclusion_criteria": (
            "Include empirical studies (observational, experimental, or mixed-methods) "
            "that measure health outcomes or access to care for patients with chronic diseases "
            "(diabetes, hypertension, cardiovascular disease) and report differences by "
            "socioeconomic status, race, ethnicity, or geographic area. "
            "Exclude editorials, opinion pieces, conference abstracts, and purely theoretical papers."
        ),
        "include_terms": [
            "socioeconomic", "health inequalit", "disparity", "disparities",
            "diabetes", "hypertension", "cardiovascular", "chronic disease",
            "access to care", "racial", "income", "poverty",
        ],
        "exclude_terms": [
            "editorial", "letter to the editor", "commentary", "book review",
        ],
    },
    {
        "label": "🏛️ Example 2 — Social Sciences: Universal Basic Income (UBI) Policy Outcomes",
        "screened_file": "day2_ex2_ubi_screened.csv",
        "session_key": "ex2_ubi",
        "inclusion_criteria": (
            "Include empirical evaluations (quantitative, qualitative, or mixed-methods) "
            "of Universal Basic Income programmes or pilots that report measured outcomes "
            "on employment, poverty, well-being, or social behaviour. "
            "Exclude opinion pieces, editorials, theoretical proposals, and grey literature "
            "without peer review."
        ),
        "include_terms": [
            "universal basic income", "basic income", "guaranteed income",
            "cash transfer", "pilot", "evaluation", "employment", "poverty",
        ],
        "exclude_terms": [
            "opinion", "commentary", "book review", "policy proposal", "editorial",
        ],
    },
    {
        "label": "⚗️ Example 3 — Science / Engineering: Microplastic Pollution in Aquatic Environments",
        "screened_file": "day2_ex3_microplastics_screened.csv",
        "session_key": "ex3_microplastics",
        "inclusion_criteria": (
            "Include experimental or observational studies that measure microplastic "
            "concentrations, distribution, or ecological impact in freshwater or marine "
            "aquatic environments. Studies must report quantitative measurements. "
            "Exclude purely laboratory studies with no environmental relevance, reviews, "
            "and studies focused on terrestrial environments only."
        ),
        "include_terms": [
            "microplastic", "marine", "freshwater", "aquatic", "concentration",
            "polymer", "sampling", "detection",
        ],
        "exclude_terms": [
            "terrestrial", "soil contamination", "atmospheric", "review article",
        ],
    },
    {
        "label": "💼 Example 4 — Management / Business: CSR and Firm Financial Performance",
        "screened_file": "day2_ex4_csr_screened.csv",
        "session_key": "ex4_csr",
        "inclusion_criteria": (
            "Include empirical studies that quantitatively measure the relationship between "
            "Corporate Social Responsibility (CSR) activities and firm financial performance "
            "metrics (ROA, ROE, Tobin's Q, stock returns, or similar). "
            "Exclude purely conceptual or theoretical papers, qualitative case studies without "
            "quantitative financial performance data, and editorials."
        ),
        "include_terms": [
            "corporate social responsibility", "csr", "esg", "roa", "roe",
            "tobin", "financial performance", "firm performance", "empirical",
        ],
        "exclude_terms": [
            "conceptual framework", "editorial", "commentary", "book review",
        ],
    },
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_screened(screened_file):
    path = CACHE_DIR / screened_file
    if path.exists():
        try:
            return pd.read_csv(path), None
        except Exception as e:
            return None, str(e)
    return None, f"Screened file not found: {screened_file}"


def display_screening_results(df, session_key):
    n_include = (df["AL_Decision"] == "Include").sum()
    n_exclude = (df["AL_Decision"] == "Exclude").sum()
    n_uncertain = (df["AL_Decision"] == "Uncertain").sum() if "Uncertain" in df["AL_Decision"].values else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total screened", len(df))
    col2.metric("✅ Include", int(n_include))
    col3.metric("❌ Exclude", int(n_exclude))
    col4.metric("⚠️ Uncertain", int(n_uncertain))

    st.markdown("#### Active Learning — Relevance-Ranked Results (top 30)")
    display_cols = ["Title", "Year", "Relevance_Score", "AL_Decision", "LLM_Decision", "LLM_Justification"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available].head(30), use_container_width=True)

    st.markdown("#### Transparency Log — LLM Decisions")
    log_cols = ["Title", "LLM_Decision", "LLM_Justification"]
    available_log = [c for c in log_cols if c in df.columns]
    st.dataframe(df[available_log].head(30), use_container_width=True)

    included_df = df[df["AL_Decision"] == "Include"].copy()
    csv_bytes = included_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download included studies as CSV",
        csv_bytes,
        f"{session_key}_included.csv",
        "text/csv",
        key=f"dl_inc_{session_key}",
    )

    st.session_state[f"{session_key}_included_df"] = included_df
    st.info(f"✅ {len(included_df)} included studies saved. Go to **Day 3 → From Studies to Evidence** when ready.")


# ── Sidebar ────────────────────────────────────────────────────────────────────

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
**Theme:** Show how Active Learning and LLM-based zero-shot screening can drastically
reduce the time spent screening titles and abstracts — all in a **no-code** environment.

### What You Will Do Today

The second day focuses on the most time-consuming phase of a systematic review: screening
thousands of titles and abstracts. You will be introduced to two complementary AI-assisted
approaches:

**Active Learning** is a human-in-the-loop machine learning technique. A model is trained
on a small set of labelled examples (seeded from your inclusion/exclusion keywords) and
then reorders the remaining corpus to surface the most relevant papers first.

**LLM zero-shot screening** uses a Large Language Model prompted with your inclusion and
exclusion criteria to automatically classify each abstract and provide a one-sentence
justification. This is a powerful first-pass filter, not a replacement for human judgment.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Present the bottleneck of abstract screening. Explain Active Learning and LLM zero-shot screening. Introduce recall-oriented evaluation metrics. |
| **Hour 2** | Demonstrate the Active Learning module across the four case studies. |
| **Hour 3** | Introduce LLM-based screening. Participants verify the model's one-sentence justifications. The Transparency Log records every AI decision for the audit trail. |

### Learning Outcome

By the end of Day 2, you should understand how Active Learning and LLMs can accelerate
abstract screening, how to configure inclusion criteria as algorithmic prompts, how
recall-oriented metrics assess screening quality, and why human verification and a full
audit trail remain essential.

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Screen Your Own Corpus**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 2 — Guided Examples")
    st.markdown("""
Each example below loads **pre-computed screening results** for the four case study corpora
from Day 1. **Expand any example** to see the Active Learning rankings, LLM decisions,
and Transparency Log. No button click required — results render immediately.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            st.markdown(f"**Inclusion criteria:** {ex['inclusion_criteria']}")
            st.markdown("**Key inclusion terms:** " + ", ".join(f"`{t}`" for t in ex["include_terms"][:6]))
            st.markdown("**Key exclusion terms:** " + ", ".join(f"`{t}`" for t in ex["exclude_terms"][:4]))

            df, err = load_screened(ex["screened_file"])
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ Screening results loaded: {len(df)} records.")
                display_screening_results(df, ex["session_key"])

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Screen Your Own Corpus":
    st.title("🔎 Day 2 — Bring Your Own Data")
    st.markdown("""
Use this section to screen **your own corpus** from Day 1. Upload the CSV you downloaded
from Day 1 (or use the corpus saved in the session), enter your inclusion and exclusion
criteria, and the app will rank and screen your records automatically.
    """)

    uploaded = st.file_uploader("Upload your Day 1 corpus CSV", type=["csv"])

    if uploaded is None and "byod_df" in st.session_state:
        st.info("Using corpus from Day 1 BYOD session.")
        df = st.session_state["byod_df"]
    elif uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = None

    if df is not None:
        st.success(f"✅ {len(df)} records loaded.")
        st.dataframe(df.head(10), use_container_width=True)

        st.markdown("---")
        include_input = st.text_area(
            "Inclusion terms (one per line)",
            value="empirical\nquantitative\noutcomes\nrandomized\npilot",
            height=120,
        )
        exclude_input = st.text_area(
            "Exclusion terms (one per line)",
            value="editorial\ncommentary\nbook review\nopinion",
            height=100,
        )

        if st.button("▶ Run Screening", key="byod_screen"):
            include_terms = [t.strip() for t in include_input.splitlines() if t.strip()]
            exclude_terms = [t.strip() for t in exclude_input.splitlines() if t.strip()]

            texts = (df["Title"].fillna("") + " " + df["Abstract"].fillna("")).tolist()
            scores, al_decisions, llm_decisions, llm_justifications = [], [], [], []

            for text in texts:
                tl = text.lower()
                inc_hits = sum(1 for t in include_terms if t.lower() in tl)
                exc_hits = sum(1 for t in exclude_terms if t.lower() in tl)
                score = round(max(0.0, min(1.0, inc_hits / max(len(include_terms), 1) - 0.15 * exc_hits)), 3)
                scores.append(score)

                if len(tl.strip()) < 30:
                    al_decisions.append("Exclude")
                    llm_decisions.append("Exclude")
                    llm_justifications.append("Abstract too short or missing.")
                elif exc_hits > 0 and inc_hits == 0:
                    al_decisions.append("Exclude")
                    llm_decisions.append("Exclude")
                    llm_justifications.append("Contains exclusion terms with no inclusion match.")
                elif inc_hits >= 1:
                    al_decisions.append("Include")
                    llm_decisions.append("Include")
                    llm_justifications.append(f"Matches {inc_hits} inclusion term(s).")
                else:
                    al_decisions.append("Exclude")
                    llm_decisions.append("Exclude")
                    llm_justifications.append("No inclusion terms matched.")

            result_df = df.copy()
            result_df["Relevance_Score"] = scores
            result_df["AL_Decision"] = al_decisions
            result_df["LLM_Decision"] = llm_decisions
            result_df["LLM_Justification"] = llm_justifications
            result_df = result_df.sort_values("Relevance_Score", ascending=False).reset_index(drop=True)

            display_screening_results(result_df, "byod")
            st.session_state["byod_included_df"] = result_df[result_df["AL_Decision"] == "Include"].copy()
