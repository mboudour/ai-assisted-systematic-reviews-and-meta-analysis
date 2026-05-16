"""
Day 3 — From Studies to Evidence
LLM-assisted structured data extraction + narrative/quantitative synthesis
for the four guided examples. No coding required.
"""

import os, json, pathlib
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(
    page_title="Day 3 — From Studies to Evidence",
    page_icon="📊",
    layout="wide",
)

# ── Robust cache directory ─────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent
if _repo_root.name == "pages":
    _repo_root = _repo_root.parent
CACHE_DIR = str(_repo_root / "data" / "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Case study configurations ──────────────────────────────────────────────────

CASE_STUDIES = {
    "🏥 Health Sciences — Health Inequalities in Chronic Disease Care": {
        "id": "ex1_health",
        "synthesis_type": "meta_analysis",
        "extraction_schema": ["Title", "Year", "Country", "Population", "Intervention",
                              "Comparator", "Outcome", "Effect_Size", "CI_Lower", "CI_Upper",
                              "Sample_Size", "Study_Design"],
        "effect_label": "Risk Ratio (RR)",
        "narrative_prompt": (
            "Extract the PICO components and the primary effect size (risk ratio or odds ratio) "
            "for care access or disease outcome disparities by socioeconomic group."
        ),
        "sample_data": [
            {"Title": "Socioeconomic disparities in diabetes care access (UK)", "Year": 2019,
             "Country": "UK", "Effect_Size": 1.42, "CI_Lower": 1.18, "CI_Upper": 1.71, "Sample_Size": 4820},
            {"Title": "Racial inequalities in hypertension management (USA)", "Year": 2020,
             "Country": "USA", "Effect_Size": 1.61, "CI_Lower": 1.35, "CI_Upper": 1.92, "Sample_Size": 9340},
            {"Title": "Income-related inequalities in CVD outcomes (Germany)", "Year": 2021,
             "Country": "Germany", "Effect_Size": 1.28, "CI_Lower": 1.09, "CI_Upper": 1.51, "Sample_Size": 6120},
            {"Title": "Geographic disparities in chronic disease care (Australia)", "Year": 2022,
             "Country": "Australia", "Effect_Size": 1.35, "CI_Lower": 1.12, "CI_Upper": 1.63, "Sample_Size": 3870},
            {"Title": "SES and diabetes control outcomes (Canada)", "Year": 2023,
             "Country": "Canada", "Effect_Size": 1.19, "CI_Lower": 1.04, "CI_Upper": 1.37, "Sample_Size": 5640},
        ],
    },
    "🏛️ Social Sciences — Universal Basic Income (UBI) Policy Outcomes": {
        "id": "ex2_ubi",
        "synthesis_type": "narrative",
        "extraction_schema": ["Title", "Year", "Country", "Programme_Name", "Methodology",
                              "Sample_Size", "Duration_Months", "Key_Finding_Employment",
                              "Key_Finding_Wellbeing", "Key_Finding_Poverty"],
        "effect_label": "N/A (Narrative Synthesis)",
        "narrative_prompt": (
            "Extract the programme name, country, methodology, sample size, duration, "
            "and key findings on employment, well-being, and poverty outcomes."
        ),
        "sample_data": [
            {"Title": "Finland Basic Income Pilot: Two-Year Results", "Year": 2020,
             "Country": "Finland", "Programme_Name": "Finland UBI Pilot",
             "Methodology": "RCT", "Sample_Size": 2000, "Duration_Months": 24,
             "Key_Finding_Employment": "No significant effect on employment",
             "Key_Finding_Wellbeing": "Significant improvement in mental well-being",
             "Key_Finding_Poverty": "Modest reduction in poverty stress"},
            {"Title": "Stockton SEED: Guaranteed Income Outcomes", "Year": 2021,
             "Country": "USA", "Programme_Name": "Stockton SEED",
             "Methodology": "Quasi-experimental", "Sample_Size": 125, "Duration_Months": 24,
             "Key_Finding_Employment": "Full-time employment increased by 12%",
             "Key_Finding_Wellbeing": "Reduced anxiety and depression",
             "Key_Finding_Poverty": "Reduced income volatility"},
            {"Title": "Kenya GiveDirectly Long-Run Evaluation", "Year": 2022,
             "Country": "Kenya", "Programme_Name": "GiveDirectly",
             "Methodology": "RCT", "Sample_Size": 10500, "Duration_Months": 36,
             "Key_Finding_Employment": "Increased self-employment and assets",
             "Key_Finding_Wellbeing": "Improved food security and health",
             "Key_Finding_Poverty": "Significant poverty reduction sustained at 3 years"},
        ],
    },
    "⚗️ Science / Engineering — Microplastic Pollution in Aquatic Environments": {
        "id": "ex3_microplastics",
        "synthesis_type": "quantitative_summary",
        "extraction_schema": ["Title", "Year", "Country", "Environment_Type",
                              "Concentration_Mean", "Concentration_Unit",
                              "Polymer_Types", "Sample_Size", "Detection_Method"],
        "effect_label": "Mean Concentration (particles/L or particles/kg)",
        "narrative_prompt": (
            "Extract the environment type (freshwater/marine), mean microplastic concentration "
            "and unit, dominant polymer types, sample size, and detection method."
        ),
        "sample_data": [
            {"Title": "Microplastic concentrations in the North Sea", "Year": 2020,
             "Country": "Netherlands", "Environment_Type": "Marine",
             "Concentration_Mean": 0.34, "Concentration_Unit": "particles/L",
             "Polymer_Types": "PE, PP, PS", "Sample_Size": 48, "Detection_Method": "FTIR"},
            {"Title": "Freshwater microplastics in the Rhine River", "Year": 2021,
             "Country": "Germany", "Environment_Type": "Freshwater",
             "Concentration_Mean": 1.28, "Concentration_Unit": "particles/L",
             "Polymer_Types": "PE, PET", "Sample_Size": 36, "Detection_Method": "Raman"},
            {"Title": "Microplastic pollution in coastal sediments (China)", "Year": 2022,
             "Country": "China", "Environment_Type": "Marine sediment",
             "Concentration_Mean": 412.0, "Concentration_Unit": "particles/kg",
             "Polymer_Types": "PP, PE, PVC", "Sample_Size": 60, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in Amazon River tributaries", "Year": 2023,
             "Country": "Brazil", "Environment_Type": "Freshwater",
             "Concentration_Mean": 0.87, "Concentration_Unit": "particles/L",
             "Polymer_Types": "PET, PE", "Sample_Size": 24, "Detection_Method": "Visual + FTIR"},
        ],
    },
    "💼 Management / Business — CSR and Firm Financial Performance": {
        "id": "ex4_csr",
        "synthesis_type": "meta_analysis",
        "extraction_schema": ["Title", "Year", "Country", "CSR_Measure", "FP_Measure",
                              "Correlation_r", "Sample_Size", "Industry_Sector"],
        "effect_label": "Correlation Coefficient (r)",
        "narrative_prompt": (
            "Extract the CSR measurement approach, financial performance metric, "
            "correlation coefficient (r), sample size, and industry sector."
        ),
        "sample_data": [
            {"Title": "CSR disclosure and ROA in manufacturing firms", "Year": 2019,
             "Country": "USA", "CSR_Measure": "ESG score", "FP_Measure": "ROA",
             "Correlation_r": 0.21, "CI_Lower": 0.12, "CI_Upper": 0.30, "Sample_Size": 340},
            {"Title": "Environmental CSR and Tobin's Q in European firms", "Year": 2020,
             "Country": "Europe", "CSR_Measure": "Environmental score", "FP_Measure": "Tobin's Q",
             "Correlation_r": 0.18, "CI_Lower": 0.08, "CI_Upper": 0.28, "Sample_Size": 520},
            {"Title": "Social responsibility and ROE in Asian markets", "Year": 2021,
             "Country": "Asia", "CSR_Measure": "Social score", "FP_Measure": "ROE",
             "Correlation_r": 0.14, "CI_Lower": 0.05, "CI_Upper": 0.23, "Sample_Size": 410},
            {"Title": "CSR and stock returns: a meta-analytic review", "Year": 2022,
             "Country": "Global", "CSR_Measure": "Composite ESG", "FP_Measure": "Stock returns",
             "Correlation_r": 0.11, "CI_Lower": 0.04, "CI_Upper": 0.18, "Sample_Size": 890},
            {"Title": "Governance CSR and firm value in emerging markets", "Year": 2023,
             "Country": "Emerging markets", "CSR_Measure": "Governance score", "FP_Measure": "Tobin's Q",
             "Correlation_r": 0.24, "CI_Lower": 0.15, "CI_Upper": 0.33, "Sample_Size": 280},
        ],
    },
}

# ── Forest plot helper ─────────────────────────────────────────────────────────

def draw_forest_plot(df, effect_col, ci_lower_col, ci_upper_col, title_col, effect_label):
    """Draw a basic forest plot using matplotlib."""
    n = len(df)
    fig, ax = plt.subplots(figsize=(10, max(4, n * 0.7 + 1.5)))

    y_positions = list(range(n, 0, -1))
    effects = df[effect_col].tolist()
    lowers = df[ci_lower_col].tolist()
    uppers = df[ci_upper_col].tolist()
    labels = df[title_col].str[:55].tolist()

    for i, (y, eff, lo, hi, lbl) in enumerate(zip(y_positions, effects, lowers, uppers, labels)):
        ax.plot([lo, hi], [y, y], color="#2c7bb6", linewidth=1.5)
        ax.plot(eff, y, "s", color="#d7191c", markersize=8, zorder=5)
        ax.text(-0.05, y, lbl, ha="right", va="center", fontsize=8, transform=ax.get_yaxis_transform())

    # Pooled estimate (inverse-variance weighted mean — simplified)
    weights = [1 / ((hi - lo) / 3.92) ** 2 for lo, hi in zip(lowers, uppers)]
    pooled = sum(w * e for w, e in zip(weights, effects)) / sum(weights)
    pooled_se = 1 / sum(weights) ** 0.5
    pooled_lo = pooled - 1.96 * pooled_se
    pooled_hi = pooled + 1.96 * pooled_se

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
    ax.plot([pooled_lo, pooled_hi], [0.5, 0.5], color="#1a9641", linewidth=2.5)
    ax.plot(pooled, 0.5, "D", color="#1a9641", markersize=10, zorder=6)
    ax.text(-0.05, 0.5, f"Pooled ({effect_label})", ha="right", va="center",
            fontsize=9, fontweight="bold", transform=ax.get_yaxis_transform())

    # Null line
    null_val = 1.0 if "Ratio" in effect_label or "RR" in effect_label or "OR" in effect_label else 0.0
    ax.axvline(null_val, color="black", linestyle="-", linewidth=0.8)

    ax.set_yticks([])
    ax.set_xlabel(effect_label, fontsize=10)
    ax.set_title("Forest Plot", fontsize=12, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    legend_elements = [
        mpatches.Patch(color="#d7191c", label="Individual study estimate"),
        mpatches.Patch(color="#1a9641", label=f"Pooled estimate: {pooled:.3f} [{pooled_lo:.3f}, {pooled_hi:.3f}]"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    plt.tight_layout()
    return fig, pooled, pooled_lo, pooled_hi


def draw_prisma_flow(n_identified, n_after_dedup, n_screened, n_included):
    """Draw a simplified PRISMA 2020 flow diagram."""
    fig, ax = plt.subplots(figsize=(7, 9))
    ax.axis("off")

    boxes = [
        (0.5, 0.90, f"Records identified\nvia API search\n(n = {n_identified})"),
        (0.5, 0.72, f"Records after\ndeduplication\n(n = {n_after_dedup})"),
        (0.5, 0.54, f"Records screened\n(title & abstract)\n(n = {n_screened})"),
        (0.5, 0.36, f"Full-text articles\nassessed for eligibility\n(n = {int(n_screened * 0.4)})"),
        (0.5, 0.18, f"Studies included\nin synthesis\n(n = {n_included})"),
    ]
    excluded = [
        (0.82, 0.72, f"Duplicates removed\n(n = {n_identified - n_after_dedup})"),
        (0.82, 0.54, f"Excluded on\ntitle/abstract\n(n = {int(n_screened * 0.6)})"),
        (0.82, 0.36, f"Excluded on\nfull-text\n(n = {int(n_screened * 0.4) - n_included})"),
    ]

    for x, y, text in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x - 0.22, y - 0.07), 0.44, 0.12,
                     boxstyle="round,pad=0.01", facecolor="#dbeafe", edgecolor="#2563eb", linewidth=1.5))
        ax.text(x, y - 0.01, text, ha="center", va="center", fontsize=8.5, wrap=True)

    for x, y, text in excluded:
        ax.add_patch(mpatches.FancyBboxPatch((x - 0.15, y - 0.06), 0.30, 0.10,
                     boxstyle="round,pad=0.01", facecolor="#fee2e2", edgecolor="#dc2626", linewidth=1.2))
        ax.text(x, y - 0.01, text, ha="center", va="center", fontsize=7.5)

    # Arrows
    for i in range(len(boxes) - 1):
        ax.annotate("", xy=(0.5, boxes[i+1][1] + 0.05), xytext=(0.5, boxes[i][1] - 0.07),
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.2))

    ax.set_title("PRISMA 2020 Flow Diagram", fontsize=12, fontweight="bold", pad=10)
    plt.tight_layout()
    return fig


# ── sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("Day 3 Navigation")
section = st.sidebar.radio(
    "Select section",
    ["Overview", "📌 Guided Examples", "🔎 BYOD — Your Own Synthesis"],
)

# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if section == "Overview":
    st.title("📊 Day 3 — From Studies to Evidence")
    st.markdown("""
**Theme:** Show participants how to extract structured data from included studies and
produce a preliminary narrative or quantitative synthesis, including a PRISMA flow
diagram and a forest plot for meta-analyses.

### What You Will Do Today

The third day brings the pipeline to its conclusion. Having built a corpus on Day 1 and
screened it on Day 2, participants now extract structured data from the included studies
and produce a preliminary synthesis.

**Structured data extraction** uses an LLM prompted with a discipline-specific schema
(e.g., PICO for health sciences, or CSR measure + financial metric for management) to
parse each abstract and return a structured JSON record. The app assembles these records
into a clean extraction table that can be downloaded as a CSV.

**Narrative synthesis** organises the extracted data into a structured summary table
and generates a plain-language synthesis paragraph — suitable for the Results section
of a systematic review.

**Quantitative synthesis (meta-analysis)** pools effect sizes across studies using
inverse-variance weighting and produces a forest plot with a pooled estimate and
confidence interval. This is demonstrated for the Health Sciences and Management case
studies, where effect sizes (risk ratios and correlation coefficients, respectively)
are available.

**PRISMA 2020 flow diagram** is generated automatically from the record counts at
each stage of the pipeline.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce structured data extraction. Explain the difference between narrative and quantitative synthesis. Present the four extraction schemas. |
| **Hour 2** | Demonstrate LLM-assisted extraction for the four case studies. Participants inspect the extraction table, correct errors, and download the CSV. |
| **Hour 3** | Produce the synthesis outputs: narrative summary table, forest plot (meta-analysis cases), and PRISMA flow diagram. Participants export all outputs and discuss limitations. |

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Synthesis**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 3 — Guided Examples")
    st.markdown("Select a case study to see the extraction schema, sample extracted data, and synthesis outputs.")

    case_name = st.selectbox("Select a case study", list(CASE_STUDIES.keys()))
    cs = CASE_STUDIES[case_name]

    st.markdown(f"**Synthesis type:** `{cs['synthesis_type'].replace('_', ' ').title()}`")
    st.markdown(f"**Extraction schema fields:** {', '.join(cs['extraction_schema'])}")
    st.markdown(f"**LLM extraction prompt guidance:** {cs['narrative_prompt']}")

    st.markdown("---")
    st.subheader("Step 1 — Structured Data Extraction")
    st.markdown("""
The LLM extraction module applies a discipline-specific schema to each included study
and returns a structured JSON record. Pre-cached extraction results are shown below
for the guided examples.
    """)

    df_extracted = pd.DataFrame(cs["sample_data"])
    st.success(f"✅ Extraction complete: {len(df_extracted)} studies extracted.")
    st.dataframe(df_extracted, use_container_width=True)

    csv_bytes = df_extracted.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download extraction table as CSV",
        csv_bytes, f"day3_{cs['id']}_extraction.csv", "text/csv",
        key=f"dl_extract_{cs['id']}",
    )

    st.markdown("---")
    st.subheader("Step 2 — PRISMA 2020 Flow Diagram")

    n_id = 100
    n_dedup = 85
    n_screened = 85
    n_included = len(df_extracted)

    if st.button("▶ Generate PRISMA Flow Diagram", key=f"prisma_{cs['id']}"):
        fig = draw_prisma_flow(n_id, n_dedup, n_screened, n_included)
        st.pyplot(fig)
        prisma_path = os.path.join(CACHE_DIR, f"day3_{cs['id']}_prisma.png")
        fig.savefig(prisma_path, dpi=150, bbox_inches="tight")
        with open(prisma_path, "rb") as f:
            st.download_button("⬇️ Download PRISMA diagram (PNG)", f.read(),
                               f"day3_{cs['id']}_prisma.png", "image/png",
                               key=f"dl_prisma_{cs['id']}")

    st.markdown("---")

    if cs["synthesis_type"] == "meta_analysis":
        st.subheader("Step 3 — Forest Plot and Pooled Effect Size")
        st.markdown(f"""
This meta-analysis pools the **{cs['effect_label']}** across the extracted studies
using inverse-variance weighting. The diamond at the bottom represents the pooled
estimate with its 95% confidence interval.
        """)

        if st.button("▶ Generate Forest Plot", key=f"forest_{cs['id']}"):
            if "Correlation_r" in df_extracted.columns:
                eff_col, lo_col, hi_col = "Correlation_r", "CI_Lower", "CI_Upper"
            else:
                eff_col, lo_col, hi_col = "Effect_Size", "CI_Lower", "CI_Upper"

            if lo_col in df_extracted.columns and hi_col in df_extracted.columns:
                fig, pooled, pooled_lo, pooled_hi = draw_forest_plot(
                    df_extracted, eff_col, lo_col, hi_col, "Title", cs["effect_label"]
                )
                st.pyplot(fig)
                st.metric(
                    f"Pooled {cs['effect_label']}",
                    f"{pooled:.3f}",
                    f"95% CI: [{pooled_lo:.3f}, {pooled_hi:.3f}]",
                )
                forest_path = os.path.join(CACHE_DIR, f"day3_{cs['id']}_forest.png")
                fig.savefig(forest_path, dpi=150, bbox_inches="tight")
                with open(forest_path, "rb") as f:
                    st.download_button("⬇️ Download forest plot (PNG)", f.read(),
                                       f"day3_{cs['id']}_forest.png", "image/png",
                                       key=f"dl_forest_{cs['id']}")
            else:
                st.warning("CI columns not found in extraction data.")

    elif cs["synthesis_type"] == "narrative":
        st.subheader("Step 3 — Narrative Synthesis Table")
        st.markdown("""
The narrative synthesis organises the extracted data into a structured summary table
suitable for the Results section of a systematic review.
        """)
        st.dataframe(df_extracted, use_container_width=True)

    elif cs["synthesis_type"] == "quantitative_summary":
        st.subheader("Step 3 — Quantitative Summary")
        st.markdown("Summary statistics for the extracted concentration measurements:")
        if "Concentration_Mean" in df_extracted.columns:
            summary = df_extracted.groupby("Environment_Type")["Concentration_Mean"].agg(
                ["mean", "min", "max", "count"]
            ).rename(columns={"mean": "Mean", "min": "Min", "max": "Max", "count": "N Studies"})
            st.dataframe(summary, use_container_width=True)

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(df_extracted["Title"].str[:30], df_extracted["Concentration_Mean"],
                   color="#2c7bb6", edgecolor="white")
            ax.set_ylabel(f"Mean Concentration ({df_extracted['Concentration_Unit'].iloc[0]})")
            ax.set_title("Mean Microplastic Concentrations by Study")
            plt.xticks(rotation=30, ha="right", fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Your Own Synthesis":
    st.title("🔎 Day 3 — Bring Your Own Data")
    st.markdown("""
Use this section to produce a synthesis from **your own included studies**.
Upload the CSV of included studies from Day 2 (or any CSV with Title, Year, and Abstract columns)
and define your extraction schema.
    """)

    uploaded = st.file_uploader("Upload included studies CSV", type=["csv"])

    if uploaded is None and "byod_included_df" in st.session_state:
        st.info("Using included studies from Day 2 BYOD session.")
        df = st.session_state["byod_included_df"]
    elif uploaded is not None:
        df = pd.read_csv(uploaded)
    else:
        df = None

    if df is not None:
        st.success(f"✅ {len(df)} included studies loaded.")
        st.dataframe(df.head(10), use_container_width=True)

        st.markdown("---")
        st.subheader("Define Your Extraction Schema")
        schema_input = st.text_input(
            "List the fields you want to extract (comma-separated)",
            value="Title, Year, Country, Population, Intervention, Outcome, Effect_Size, Sample_Size",
        )
        schema_fields = [f.strip() for f in schema_input.split(",") if f.strip()]

        synthesis_type = st.selectbox(
            "Synthesis type",
            ["Narrative synthesis", "Meta-analysis (requires Effect_Size, CI_Lower, CI_Upper columns)",
             "Quantitative summary"],
        )

        if st.button("▶ Generate Extraction Template", key="byod_extract"):
            template_df = pd.DataFrame(columns=schema_fields)
            for _, row in df.head(20).iterrows():
                new_row = {f: row.get(f, "") for f in schema_fields}
                template_df = pd.concat([template_df, pd.DataFrame([new_row])], ignore_index=True)
            st.dataframe(template_df, use_container_width=True)
            csv_bytes = template_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download extraction template", csv_bytes,
                               "byod_extraction_template.csv", "text/csv", key="dl_byod_template")

        if "Meta-analysis" in synthesis_type:
            st.markdown("---")
            st.subheader("Forest Plot")
            st.markdown("Upload your completed extraction CSV with Effect_Size, CI_Lower, CI_Upper columns:")
            extracted_upload = st.file_uploader("Upload completed extraction CSV", type=["csv"], key="byod_forest_upload")
            if extracted_upload is not None:
                df_ext = pd.read_csv(extracted_upload)
                required = {"Effect_Size", "CI_Lower", "CI_Upper", "Title"}
                if required.issubset(df_ext.columns):
                    effect_label = st.text_input("Effect size label", value="Effect Size")
                    if st.button("▶ Generate Forest Plot", key="byod_forest"):
                        fig, pooled, pooled_lo, pooled_hi = draw_forest_plot(
                            df_ext, "Effect_Size", "CI_Lower", "CI_Upper", "Title", effect_label
                        )
                        st.pyplot(fig)
                        st.metric(f"Pooled {effect_label}", f"{pooled:.3f}",
                                  f"95% CI: [{pooled_lo:.3f}, {pooled_hi:.3f}]")
                else:
                    st.error(f"Missing columns. Required: {required}")

        st.markdown("---")
        st.subheader("PRISMA Flow Diagram")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            n_id = st.number_input("Records identified", min_value=1, value=200)
        with col2:
            n_dedup = st.number_input("After deduplication", min_value=1, value=180)
        with col3:
            n_screened = st.number_input("Records screened", min_value=1, value=180)
        with col4:
            n_included = st.number_input("Studies included", min_value=1, value=len(df))

        if st.button("▶ Generate PRISMA Diagram", key="byod_prisma"):
            fig = draw_prisma_flow(n_id, n_dedup, n_screened, n_included)
            st.pyplot(fig)
