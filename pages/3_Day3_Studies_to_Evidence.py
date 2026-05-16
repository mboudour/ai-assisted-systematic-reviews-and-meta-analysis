"""
Day 3 — From Studies to Evidence
LLM-assisted structured data extraction + narrative/quantitative synthesis.
Guided examples use pre-cached sample data — no API calls required.
PRISMA flow diagram uses a clean, non-overlapping layout.
No coding required.
"""

import os, pathlib
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.patches import FancyArrowPatch

st.set_page_config(
    page_title="Day 3 — From Studies to Evidence",
    page_icon="📊",
    layout="wide",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = _repo_root / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Case study sample data ─────────────────────────────────────────────────────

CASE_STUDIES = {
    "🏥 Health Sciences — Health Inequalities in Chronic Disease Care": {
        "id": "ex1_health",
        "synthesis_type": "meta_analysis",
        "effect_label": "Risk Ratio (RR)",
        "prisma_counts": (150, 135, 135, 5),
        "sample_data": pd.DataFrame([
            {"Title": "Socioeconomic disparities in diabetes care access (UK)",
             "Year": 2019, "Country": "UK", "Population": "Low-SES adults with T2DM",
             "Intervention": "Standard NHS care", "Comparator": "High-SES adults",
             "Outcome": "HbA1c control", "Effect_Size": 1.42,
             "CI_Lower": 1.18, "CI_Upper": 1.71, "Sample_Size": 4820, "Study_Design": "Cohort"},
            {"Title": "Racial inequalities in hypertension management (USA)",
             "Year": 2020, "Country": "USA", "Population": "Black adults with hypertension",
             "Intervention": "Routine primary care", "Comparator": "White adults",
             "Outcome": "BP control", "Effect_Size": 1.61,
             "CI_Lower": 1.35, "CI_Upper": 1.92, "Sample_Size": 9340, "Study_Design": "Cross-sectional"},
            {"Title": "Income-related inequalities in CVD outcomes (Germany)",
             "Year": 2021, "Country": "Germany", "Population": "Low-income CVD patients",
             "Intervention": "Standard care", "Comparator": "High-income patients",
             "Outcome": "30-day mortality", "Effect_Size": 1.28,
             "CI_Lower": 1.09, "CI_Upper": 1.51, "Sample_Size": 6120, "Study_Design": "Registry study"},
            {"Title": "Geographic disparities in chronic disease care (Australia)",
             "Year": 2022, "Country": "Australia", "Population": "Rural chronic disease patients",
             "Intervention": "Rural GP care", "Comparator": "Urban patients",
             "Outcome": "Specialist referral rate", "Effect_Size": 1.35,
             "CI_Lower": 1.12, "CI_Upper": 1.63, "Sample_Size": 3870, "Study_Design": "Cohort"},
            {"Title": "SES and diabetes control outcomes (Canada)",
             "Year": 2023, "Country": "Canada", "Population": "Low-SES T2DM patients",
             "Intervention": "Community health centre care", "Comparator": "High-SES patients",
             "Outcome": "HbA1c ≥8%", "Effect_Size": 1.19,
             "CI_Lower": 1.04, "CI_Upper": 1.37, "Sample_Size": 5640, "Study_Design": "Cohort"},
        ]),
    },
    "🏛️ Social Sciences — Universal Basic Income (UBI) Policy Outcomes": {
        "id": "ex2_ubi",
        "synthesis_type": "narrative",
        "effect_label": "N/A (Narrative Synthesis)",
        "prisma_counts": (150, 138, 138, 3),
        "sample_data": pd.DataFrame([
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
        ]),
    },
    "⚗️ Science / Engineering — Microplastic Pollution in Aquatic Environments": {
        "id": "ex3_microplastics",
        "synthesis_type": "quantitative_summary",
        "effect_label": "Mean Concentration (particles/L or particles/kg)",
        "prisma_counts": (150, 142, 142, 4),
        "sample_data": pd.DataFrame([
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
             "Polymer_Types": "PET, PE", "Sample_Size": 24,
             "Detection_Method": "Visual + FTIR"},
        ]),
    },
    "💼 Management / Business — CSR and Firm Financial Performance": {
        "id": "ex4_csr",
        "synthesis_type": "meta_analysis",
        "effect_label": "Correlation Coefficient (r)",
        "prisma_counts": (150, 140, 140, 5),
        "sample_data": pd.DataFrame([
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
             "Country": "Emerging markets", "CSR_Measure": "Governance score",
             "FP_Measure": "Tobin's Q",
             "Correlation_r": 0.24, "CI_Lower": 0.15, "CI_Upper": 0.33, "Sample_Size": 280},
        ]),
    },
}

# ── Forest plot ────────────────────────────────────────────────────────────────

def draw_forest_plot(df, effect_col, ci_lower_col, ci_upper_col, title_col, effect_label):
    n = len(df)
    fig_height = max(5, n * 0.8 + 2.5)
    fig, ax = plt.subplots(figsize=(11, fig_height))

    # Study rows: y positions n down to 1; pooled at 0 with gap
    y_studies = list(range(n, 0, -1))
    effects = df[effect_col].tolist()
    lowers = df[ci_lower_col].tolist()
    uppers = df[ci_upper_col].tolist()
    labels = [str(t)[:60] for t in df[title_col].tolist()]

    for y, eff, lo, hi, lbl in zip(y_studies, effects, lowers, uppers, labels):
        ax.plot([lo, hi], [y, y], color="#2c7bb6", linewidth=1.8, solid_capstyle="round")
        ax.plot(eff, y, "s", color="#d7191c", markersize=9, zorder=5)
        ax.text(-0.02, y, lbl, ha="right", va="center", fontsize=8.5,
                transform=ax.get_yaxis_transform())

    # Pooled estimate
    weights = []
    for lo, hi in zip(lowers, uppers):
        se = (hi - lo) / 3.92
        weights.append(1 / se**2 if se > 0 else 0)
    total_w = sum(weights)
    pooled = sum(w * e for w, e in zip(weights, effects)) / total_w if total_w > 0 else np.mean(effects)
    pooled_se = 1 / total_w**0.5 if total_w > 0 else 0
    pooled_lo = pooled - 1.96 * pooled_se
    pooled_hi = pooled + 1.96 * pooled_se

    # Pooled row at y = -0.5 (well below the last study row)
    pooled_y = -0.5
    ax.axhline(y=pooled_y + 0.5, color="lightgray", linestyle="--", linewidth=0.6)
    ax.plot([pooled_lo, pooled_hi], [pooled_y, pooled_y], color="#1a9641", linewidth=3.0)
    ax.plot(pooled, pooled_y, "D", color="#1a9641", markersize=12, zorder=6)
    ax.text(-0.02, pooled_y, f"Pooled ({effect_label})", ha="right", va="center",
            fontsize=9, fontweight="bold", transform=ax.get_yaxis_transform())

    # Null line
    null_val = 1.0 if any(x in effect_label for x in ["Ratio", "RR", "OR"]) else 0.0
    ax.axvline(null_val, color="black", linestyle="-", linewidth=0.9, zorder=3)

    ax.set_yticks([])
    ax.set_ylim(pooled_y - 0.8, n + 0.8)
    ax.set_xlabel(effect_label, fontsize=10)
    ax.set_title("Forest Plot", fontsize=13, fontweight="bold", pad=12)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    legend_elements = [
        mpatches.Patch(color="#d7191c", label="Individual study estimate"),
        mpatches.Patch(color="#1a9641",
                       label=f"Pooled: {pooled:.3f}  95% CI [{pooled_lo:.3f}, {pooled_hi:.3f}]"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8.5, framealpha=0.9)
    plt.tight_layout()
    return fig, pooled, pooled_lo, pooled_hi


# ── PRISMA flow diagram (fixed, non-overlapping) ───────────────────────────────

def draw_prisma_flow(n_identified, n_after_dedup, n_screened, n_included):
    """
    Clean PRISMA 2020 flow diagram.
    Left column: 5 main boxes stacked vertically with equal spacing.
    Right column: 3 exclusion boxes aligned with their corresponding left boxes.
    Arrows connect boxes correctly with no overlap.
    """
    fig, ax = plt.subplots(figsize=(9, 11))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Layout constants
    BOX_W = 0.38        # width of main (left) boxes
    BOX_H = 0.10        # height of all boxes
    EXC_W = 0.30        # width of exclusion (right) boxes
    LEFT_X = 0.21       # centre x of left column
    RIGHT_X = 0.78      # centre x of right column

    # Y centres for the 5 main boxes — evenly spaced
    Y_TOPS = [0.92, 0.74, 0.56, 0.38, 0.20]

    n_duplicates = n_identified - n_after_dedup
    n_excluded_screen = n_screened - int(n_screened * 0.4)
    n_fulltext = int(n_screened * 0.4)
    n_excluded_fulltext = n_fulltext - n_included

    main_boxes = [
        f"Records identified\nvia API search\n(n = {n_identified})",
        f"Records after\ndeduplication\n(n = {n_after_dedup})",
        f"Records screened\n(title & abstract)\n(n = {n_screened})",
        f"Full-text articles\nassessed for eligibility\n(n = {n_fulltext})",
        f"Studies included\nin synthesis\n(n = {n_included})",
    ]

    # Exclusion boxes aligned with boxes 1, 2, 3 (index 1, 2, 3)
    excl_boxes = [
        (Y_TOPS[1], f"Duplicates removed\n(n = {n_duplicates})"),
        (Y_TOPS[2], f"Excluded on\ntitle/abstract\n(n = {n_excluded_screen})"),
        (Y_TOPS[3], f"Excluded on\nfull-text\n(n = {n_excluded_fulltext})"),
    ]

    # Draw main (left) boxes
    for y_c, text in zip(Y_TOPS, main_boxes):
        x0 = LEFT_X - BOX_W / 2
        y0 = y_c - BOX_H / 2
        box = FancyBboxPatch((x0, y0), BOX_W, BOX_H,
                             boxstyle="round,pad=0.015",
                             facecolor="#dbeafe", edgecolor="#2563eb", linewidth=1.8,
                             transform=ax.transData, zorder=3)
        ax.add_patch(box)
        ax.text(LEFT_X, y_c, text, ha="center", va="center",
                fontsize=8.5, zorder=4, linespacing=1.4)

    # Draw exclusion (right) boxes
    for y_c, text in excl_boxes:
        x0 = RIGHT_X - EXC_W / 2
        y0 = y_c - BOX_H / 2
        box = FancyBboxPatch((x0, y0), EXC_W, BOX_H,
                             boxstyle="round,pad=0.015",
                             facecolor="#fee2e2", edgecolor="#dc2626", linewidth=1.5,
                             transform=ax.transData, zorder=3)
        ax.add_patch(box)
        ax.text(RIGHT_X, y_c, text, ha="center", va="center",
                fontsize=8, zorder=4, linespacing=1.4)

    # Vertical arrows between main boxes (bottom of box i → top of box i+1)
    for i in range(len(Y_TOPS) - 1):
        y_start = Y_TOPS[i] - BOX_H / 2      # bottom of current box
        y_end   = Y_TOPS[i + 1] + BOX_H / 2  # top of next box
        ax.annotate("",
                    xy=(LEFT_X, y_end), xytext=(LEFT_X, y_start),
                    arrowprops=dict(arrowstyle="-|>", color="#1e3a5f",
                                   lw=1.5, mutation_scale=14),
                    zorder=5)

    # Horizontal arrows from main boxes to exclusion boxes
    # Arrow from right edge of box[1] → left edge of excl[0]  (dedup)
    # Arrow from right edge of box[2] → left edge of excl[1]  (title/abstract)
    # Arrow from right edge of box[3] → left edge of excl[2]  (full-text)
    excl_source_indices = [1, 2, 3]
    for src_idx, (y_c, _) in zip(excl_source_indices, excl_boxes):
        x_start = LEFT_X + BOX_W / 2          # right edge of main box
        x_end   = RIGHT_X - EXC_W / 2         # left edge of exclusion box
        ax.annotate("",
                    xy=(x_end, y_c), xytext=(x_start, y_c),
                    arrowprops=dict(arrowstyle="-|>", color="#991b1b",
                                   lw=1.2, mutation_scale=12),
                    zorder=5)

    ax.set_title("PRISMA 2020 Flow Diagram", fontsize=13, fontweight="bold", pad=14)
    plt.tight_layout()
    return fig


# ── Sidebar ────────────────────────────────────────────────────────────────────

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
**Theme:** Extract structured data from included studies and produce a preliminary
narrative or quantitative synthesis — including a PRISMA flow diagram and a forest
plot for meta-analyses — all in a **no-code** environment.

### What You Will Do Today

The third day brings the pipeline to its conclusion. Having built a corpus on Day 1 and
screened it on Day 2, participants now extract structured data from the included studies
and produce a preliminary synthesis.

**Structured data extraction** uses an LLM prompted with a discipline-specific schema
(e.g., PICO for health sciences, or CSR measure + financial metric for management) to
parse each abstract and return a structured record. The app assembles these records into
a clean extraction table that can be downloaded as a CSV.

**Narrative synthesis** organises the extracted data into a structured summary table
suitable for the Results section of a systematic review.

**Quantitative synthesis (meta-analysis)** pools effect sizes using inverse-variance
weighting and produces a forest plot with a pooled estimate and confidence interval.

**PRISMA 2020 flow diagram** is generated automatically from the record counts at each
stage of the pipeline.

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce structured data extraction. Explain narrative vs. quantitative synthesis. Present the four extraction schemas. |
| **Hour 2** | Demonstrate LLM-assisted extraction for the four case studies. Participants inspect the extraction table and download the CSV. |
| **Hour 3** | Produce synthesis outputs: narrative summary table, forest plot (meta-analysis cases), and PRISMA flow diagram. |

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Synthesis**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 3 — Guided Examples")
    st.markdown("Select a case study to view the extraction table, synthesis outputs, and PRISMA diagram.")

    case_name = st.selectbox("Select a case study", list(CASE_STUDIES.keys()))
    cs = CASE_STUDIES[case_name]
    df_extracted = cs["sample_data"].copy()

    # ── Step 1: Extraction table ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 1 — Structured Data Extraction")
    st.markdown("""
The table below shows the structured extraction output for the selected case study.
Each row corresponds to one included study; fields were extracted using a
discipline-specific LLM prompt schema.
    """)
    st.success(f"✅ {len(df_extracted)} studies extracted.")
    st.dataframe(df_extracted, use_container_width=True)
    csv_bytes = df_extracted.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download extraction table as CSV",
        csv_bytes, f"day3_{cs['id']}_extraction.csv", "text/csv",
        key=f"dl_extract_{cs['id']}",
    )

    # ── Step 2: Synthesis ──────────────────────────────────────────────────────
    st.markdown("---")

    if cs["synthesis_type"] == "meta_analysis":
        st.subheader("Step 2 — Forest Plot and Pooled Effect Size")
        st.markdown(f"""
This meta-analysis pools the **{cs['effect_label']}** across the extracted studies
using inverse-variance weighting. The diamond represents the pooled estimate with its
95% confidence interval.
        """)
        if st.button("▶ Generate Forest Plot", key=f"forest_{cs['id']}"):
            if "Correlation_r" in df_extracted.columns:
                eff_col, lo_col, hi_col = "Correlation_r", "CI_Lower", "CI_Upper"
            else:
                eff_col, lo_col, hi_col = "Effect_Size", "CI_Lower", "CI_Upper"

            fig, pooled, pooled_lo, pooled_hi = draw_forest_plot(
                df_extracted, eff_col, lo_col, hi_col, "Title", cs["effect_label"]
            )
            st.pyplot(fig)
            plt.close(fig)
            st.metric(
                f"Pooled {cs['effect_label']}",
                f"{pooled:.3f}",
                f"95% CI: [{pooled_lo:.3f}, {pooled_hi:.3f}]",
            )
            forest_path = CACHE_DIR / f"day3_{cs['id']}_forest.png"
            fig2, pooled2, _, _ = draw_forest_plot(
                df_extracted, eff_col, lo_col, hi_col, "Title", cs["effect_label"]
            )
            fig2.savefig(str(forest_path), dpi=150, bbox_inches="tight")
            plt.close(fig2)
            with open(str(forest_path), "rb") as f:
                st.download_button(
                    "⬇️ Download forest plot (PNG)", f.read(),
                    f"day3_{cs['id']}_forest.png", "image/png",
                    key=f"dl_forest_{cs['id']}",
                )

    elif cs["synthesis_type"] == "narrative":
        st.subheader("Step 2 — Narrative Synthesis Table")
        st.markdown("""
The narrative synthesis organises the extracted data into a structured summary table
suitable for the Results section of a systematic review.
        """)
        st.dataframe(df_extracted, use_container_width=True)

    elif cs["synthesis_type"] == "quantitative_summary":
        st.subheader("Step 2 — Quantitative Summary")
        if "Concentration_Mean" in df_extracted.columns:
            summary = (
                df_extracted.groupby("Environment_Type")["Concentration_Mean"]
                .agg(["mean", "min", "max", "count"])
                .rename(columns={"mean": "Mean", "min": "Min", "max": "Max", "count": "N Studies"})
            )
            st.dataframe(summary, use_container_width=True)
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(
                df_extracted["Title"].str[:35],
                df_extracted["Concentration_Mean"],
                color="#2c7bb6", edgecolor="white",
            )
            unit = df_extracted["Concentration_Unit"].iloc[0]
            ax.set_ylabel(f"Mean Concentration ({unit})")
            ax.set_title("Mean Microplastic Concentrations by Study")
            plt.xticks(rotation=30, ha="right", fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    # ── Step 3: PRISMA ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Step 3 — PRISMA 2020 Flow Diagram")
    n_id, n_dedup, n_screened, n_included = cs["prisma_counts"]
    st.markdown(f"""
The diagram below shows the record flow for this case study:
**{n_id}** records identified → **{n_dedup}** after deduplication →
**{n_screened}** screened → **{n_included}** included in synthesis.
    """)
    if st.button("▶ Generate PRISMA Flow Diagram", key=f"prisma_{cs['id']}"):
        fig = draw_prisma_flow(n_id, n_dedup, n_screened, n_included)
        st.pyplot(fig)
        prisma_path = CACHE_DIR / f"day3_{cs['id']}_prisma.png"
        fig.savefig(str(prisma_path), dpi=150, bbox_inches="tight")
        plt.close(fig)
        with open(str(prisma_path), "rb") as f:
            st.download_button(
                "⬇️ Download PRISMA diagram (PNG)", f.read(),
                f"day3_{cs['id']}_prisma.png", "image/png",
                key=f"dl_prisma_{cs['id']}",
            )

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Your Own Synthesis":
    st.title("🔎 Day 3 — Bring Your Own Data")
    st.markdown("""
Use this section to produce a synthesis from **your own included studies**.
Upload the CSV of included studies from Day 2 (or any CSV with Title, Year, and Abstract
columns) and define your extraction schema below.
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
        st.subheader("Extraction Template")
        schema_input = st.text_input(
            "Fields to extract (comma-separated)",
            value="Title, Year, Country, Population, Intervention, Outcome, Effect_Size, Sample_Size",
        )
        schema_fields = [f.strip() for f in schema_input.split(",") if f.strip()]

        if st.button("▶ Generate Extraction Template", key="byod_extract"):
            template_df = pd.DataFrame([
                {f: row.get(f, "") for f in schema_fields}
                for _, row in df.head(20).iterrows()
            ])
            st.dataframe(template_df, use_container_width=True)
            csv_bytes = template_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download extraction template", csv_bytes,
                "byod_extraction_template.csv", "text/csv",
                key="dl_byod_template",
            )

        st.markdown("---")
        st.subheader("Forest Plot (if you have effect size data)")
        extracted_upload = st.file_uploader(
            "Upload completed extraction CSV (must have Effect_Size, CI_Lower, CI_Upper, Title columns)",
            type=["csv"], key="byod_forest_upload",
        )
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
                    plt.close(fig)
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
            n_included_byod = st.number_input("Studies included", min_value=1, value=max(1, len(df)))

        if st.button("▶ Generate PRISMA Diagram", key="byod_prisma"):
            fig = draw_prisma_flow(int(n_id), int(n_dedup), int(n_screened), int(n_included_byod))
            st.pyplot(fig)
            plt.close(fig)
