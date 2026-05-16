"""
Day 3 — From Studies to Evidence
LLM-assisted structured data extraction + narrative/quantitative synthesis.

All four guided examples are displayed simultaneously, each in its own expander.
Each example includes:
1. A structured written Overview (Research Question, Corpus, Findings, Limitations)
2. A 15-study extraction table
3. Synthesis (Forest plot with I² heterogeneity, or narrative/quantitative summary)
4. PRISMA flow diagram
"""

import io
import pathlib
import pandas as pd
import numpy as np
import scipy.stats as stats
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

st.set_page_config(
    page_title="Day 3 — From Studies to Evidence",
    page_icon="📊",
    layout="wide",
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_repo_root = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = _repo_root / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLE DATA
# ══════════════════════════════════════════════════════════════════════════════

GUIDED_EXAMPLES = [
    {
        "label": "🏥 Example 1 — Health Sciences: Health Inequalities in Chronic Disease Care",
        "session_key": "ex1_health",
        "synthesis_type": "meta_analysis",
        "effect_label": "Risk Ratio (RR)",
        "null_val": 1.0,
        "prisma_counts": (150, 135, 135, 15),
        "overview_text": """
### Overview: Health Inequalities in Chronic Disease Care

**Research Question:** What is the evidence on socioeconomic inequalities in access to and outcomes of care for patients with chronic diseases (diabetes, hypertension, CVD)?

**Corpus & Screening:** 150 records retrieved via OpenAlex (2010–2025). After deduplication (n=135), Active Learning and LLM screening identified 15 empirical studies that met all inclusion criteria (reporting quantitative disparities by SES).

**Key Findings:** The meta-analysis of 15 studies demonstrates a consistent, statistically significant disparity. Patients from lower socioeconomic backgrounds experience worse clinical outcomes and poorer access to specialist care compared to high-SES patients. The pooled Risk Ratio indicates a substantial inequality gap across multiple healthcare systems.

**Limitations:** High heterogeneity (I² > 70%) suggests that the magnitude of inequality varies significantly depending on the specific disease (diabetes vs. CVD) and national healthcare model (e.g., universal coverage vs. insurance-based).
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "Socioeconomic disparities in diabetes care access (UK)", "Year": 2019, "Country": "UK", "Population": "Low-SES T2DM", "Intervention": "NHS care", "Outcome": "HbA1c control", "Effect_Size": 1.42, "CI_Lower": 1.18, "CI_Upper": 1.71, "Sample_Size": 4820},
            {"Title": "Racial inequalities in hypertension management (USA)", "Year": 2020, "Country": "USA", "Population": "Black hypertension", "Intervention": "Primary care", "Outcome": "BP control", "Effect_Size": 1.61, "CI_Lower": 1.35, "CI_Upper": 1.92, "Sample_Size": 9340},
            {"Title": "Income-related inequalities in CVD outcomes (Germany)", "Year": 2021, "Country": "Germany", "Population": "Low-income CVD", "Intervention": "Standard care", "Outcome": "30-day mortality", "Effect_Size": 1.28, "CI_Lower": 1.09, "CI_Upper": 1.51, "Sample_Size": 6120},
            {"Title": "Geographic disparities in chronic disease care (Australia)", "Year": 2022, "Country": "Australia", "Population": "Rural chronic", "Intervention": "Rural GP care", "Outcome": "Specialist referral", "Effect_Size": 1.35, "CI_Lower": 1.12, "CI_Upper": 1.63, "Sample_Size": 3870},
            {"Title": "SES and diabetes control outcomes (Canada)", "Year": 2023, "Country": "Canada", "Population": "Low-SES T2DM", "Intervention": "CHC care", "Outcome": "HbA1c ≥8%", "Effect_Size": 1.19, "CI_Lower": 1.04, "CI_Upper": 1.37, "Sample_Size": 5640},
            {"Title": "Education level and heart failure readmission (Sweden)", "Year": 2018, "Country": "Sweden", "Population": "Low-edu HF", "Intervention": "Hospital care", "Outcome": "Readmission", "Effect_Size": 1.24, "CI_Lower": 1.05, "CI_Upper": 1.46, "Sample_Size": 2100},
            {"Title": "Poverty and asthma exacerbations in children (USA)", "Year": 2021, "Country": "USA", "Population": "Low-income asthma", "Intervention": "ED care", "Outcome": "Exacerbation", "Effect_Size": 1.55, "CI_Lower": 1.28, "CI_Upper": 1.88, "Sample_Size": 4500},
            {"Title": "Deprivation and stroke survival rates (UK)", "Year": 2020, "Country": "UK", "Population": "High-deprivation stroke", "Intervention": "Stroke unit", "Outcome": "1-year mortality", "Effect_Size": 1.31, "CI_Lower": 1.15, "CI_Upper": 1.49, "Sample_Size": 8900},
            {"Title": "SES impact on kidney disease progression (France)", "Year": 2022, "Country": "France", "Population": "Low-SES CKD", "Intervention": "Nephrology care", "Outcome": "ESRD onset", "Effect_Size": 1.40, "CI_Lower": 1.20, "CI_Upper": 1.64, "Sample_Size": 3200},
            {"Title": "Neighborhood income and COPD management (USA)", "Year": 2019, "Country": "USA", "Population": "Low-income COPD", "Intervention": "Outpatient care", "Outcome": "Hospitalization", "Effect_Size": 1.48, "CI_Lower": 1.25, "CI_Upper": 1.75, "Sample_Size": 5100},
            {"Title": "Employment status and RA treatment adherence (Spain)", "Year": 2021, "Country": "Spain", "Population": "Unemployed RA", "Intervention": "Rheumatology care", "Outcome": "Non-adherence", "Effect_Size": 1.22, "CI_Lower": 1.02, "CI_Upper": 1.45, "Sample_Size": 1800},
            {"Title": "Housing instability and HIV viral suppression (USA)", "Year": 2023, "Country": "USA", "Population": "Unstably housed HIV", "Intervention": "Clinic care", "Outcome": "Viral failure", "Effect_Size": 1.65, "CI_Lower": 1.38, "CI_Upper": 1.97, "Sample_Size": 2400},
            {"Title": "SES and post-MI rehabilitation access (Italy)", "Year": 2020, "Country": "Italy", "Population": "Low-SES post-MI", "Intervention": "Cardiac rehab", "Outcome": "Non-participation", "Effect_Size": 1.38, "CI_Lower": 1.18, "CI_Upper": 1.61, "Sample_Size": 4100},
            {"Title": "Income inequality in epilepsy care (Japan)", "Year": 2022, "Country": "Japan", "Population": "Low-income epilepsy", "Intervention": "Neurology care", "Outcome": "Seizure frequency", "Effect_Size": 1.15, "CI_Lower": 0.98, "CI_Upper": 1.35, "Sample_Size": 1500},
            {"Title": "Material deprivation and IBD biologics access (UK)", "Year": 2021, "Country": "UK", "Population": "High-deprivation IBD", "Intervention": "Gastro care", "Outcome": "Delayed biologics", "Effect_Size": 1.45, "CI_Lower": 1.22, "CI_Upper": 1.72, "Sample_Size": 2900},
        ]),
        "effect_col": "Effect_Size",
        "ci_lower_col": "CI_Lower",
        "ci_upper_col": "CI_Upper",
        "title_col": "Title",
    },
    {
        "label": "🏛️ Example 2 — Social Sciences: Universal Basic Income (UBI) Policy Outcomes",
        "session_key": "ex2_ubi",
        "synthesis_type": "narrative",
        "effect_label": "N/A (Narrative Synthesis)",
        "null_val": None,
        "prisma_counts": (150, 138, 138, 12),
        "overview_text": """
### Overview: Universal Basic Income (UBI) Policy Outcomes

**Research Question:** What are the empirically measured outcomes of Universal Basic Income (UBI) programmes and pilots in terms of employment, poverty, and well-being?

**Corpus & Screening:** 150 records retrieved via Semantic Scholar. 12 empirical evaluations of UBI or guaranteed income pilots were included after excluding opinion pieces and theoretical models.

**Key Findings:** The narrative synthesis reveals a consistent pattern across high-income and low-income contexts. UBI interventions do not produce the significant declines in labor market participation predicted by critics; employment effects are largely neutral or slightly positive (due to increased self-employment). However, the most robust and universal findings are in well-being: nearly all studies report significant reductions in psychological distress, anxiety, and income volatility.

**Limitations:** Many pilots are short-term (1–3 years) and involve small, localized samples (e.g., Stockton SEED), making macroeconomic extrapolation difficult.
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "Finland Basic Income Pilot: Two-Year Results", "Year": 2020, "Country": "Finland", "Programme_Name": "Finland UBI", "Methodology": "RCT", "Sample_Size": 2000, "Duration_Months": 24, "Key_Finding_Employment": "Neutral", "Key_Finding_Wellbeing": "Improved", "Key_Finding_Poverty": "Reduced stress"},
            {"Title": "Stockton SEED: Guaranteed Income Outcomes", "Year": 2021, "Country": "USA", "Programme_Name": "Stockton SEED", "Methodology": "Quasi-exp", "Sample_Size": 125, "Duration_Months": 24, "Key_Finding_Employment": "Positive (+12% FT)", "Key_Finding_Wellbeing": "Improved", "Key_Finding_Poverty": "Reduced volatility"},
            {"Title": "Kenya GiveDirectly Long-Run Evaluation", "Year": 2022, "Country": "Kenya", "Programme_Name": "GiveDirectly", "Methodology": "RCT", "Sample_Size": 10500, "Duration_Months": 36, "Key_Finding_Employment": "Positive (Self-emp)", "Key_Finding_Wellbeing": "Improved", "Key_Finding_Poverty": "Reduced"},
            {"Title": "Alaska Permanent Fund Dividend: Labor Effects", "Year": 2018, "Country": "USA", "Programme_Name": "APFD", "Methodology": "Obs", "Sample_Size": 50000, "Duration_Months": 120, "Key_Finding_Employment": "Neutral", "Key_Finding_Wellbeing": "N/A", "Key_Finding_Poverty": "Reduced extreme poverty"},
            {"Title": "Ontario Basic Income Pilot Analysis", "Year": 2020, "Country": "Canada", "Programme_Name": "Ontario Pilot", "Methodology": "Survey", "Sample_Size": 4000, "Duration_Months": 15, "Key_Finding_Employment": "Neutral", "Key_Finding_Wellbeing": "Improved significantly", "Key_Finding_Poverty": "Improved food security"},
            {"Title": "Mincome Experiment Re-evaluation", "Year": 2011, "Country": "Canada", "Programme_Name": "Mincome", "Methodology": "Retro-obs", "Sample_Size": 1000, "Duration_Months": 48, "Key_Finding_Employment": "Slight negative (youth)", "Key_Finding_Wellbeing": "Improved (hospital visits down)", "Key_Finding_Poverty": "Reduced"},
            {"Title": "Barcelona Guaranteed Income Pilot", "Year": 2021, "Country": "Spain", "Programme_Name": "B-MINCOME", "Methodology": "RCT", "Sample_Size": 1000, "Duration_Months": 24, "Key_Finding_Employment": "Neutral", "Key_Finding_Wellbeing": "Improved sleep/stress", "Key_Finding_Poverty": "Reduced material deprivation"},
            {"Title": "Madhya Pradesh UBI Experiment", "Year": 2014, "Country": "India", "Programme_Name": "MP UBI", "Methodology": "RCT", "Sample_Size": 6000, "Duration_Months": 18, "Key_Finding_Employment": "Positive (agriculture)", "Key_Finding_Wellbeing": "Improved nutrition", "Key_Finding_Poverty": "Reduced debt"},
            {"Title": "Gary, Indiana Negative Income Tax", "Year": 1979, "Country": "USA", "Programme_Name": "Gary NIT", "Methodology": "RCT", "Sample_Size": 1800, "Duration_Months": 36, "Key_Finding_Employment": "Slight negative", "Key_Finding_Wellbeing": "N/A", "Key_Finding_Poverty": "Increased consumption"},
            {"Title": "Compton Guaranteed Income Program", "Year": 2023, "Country": "USA", "Programme_Name": "Compton Pledge", "Methodology": "Quasi-exp", "Sample_Size": 800, "Duration_Months": 24, "Key_Finding_Employment": "Neutral", "Key_Finding_Wellbeing": "Improved agency", "Key_Finding_Poverty": "Reduced utility debt"},
            {"Title": "Macau Basic Income Pilot", "Year": 2022, "Country": "Macau", "Programme_Name": "Wealth Part.", "Methodology": "Obs", "Sample_Size": 600000, "Duration_Months": 120, "Key_Finding_Employment": "Neutral", "Key_Finding_Wellbeing": "Improved satisfaction", "Key_Finding_Poverty": "Reduced inequality"},
            {"Title": "Namibia UBI Pilot Project", "Year": 2009, "Country": "Namibia", "Programme_Name": "BIG Pilot", "Methodology": "Obs", "Sample_Size": 930, "Duration_Months": 24, "Key_Finding_Employment": "Positive (+11%)", "Key_Finding_Wellbeing": "Child malnutrition dropped", "Key_Finding_Poverty": "Poverty dropped from 76% to 37%"},
        ]),
        "effect_col": None,
        "ci_lower_col": None,
        "ci_upper_col": None,
        "title_col": "Title",
    },
    {
        "label": "⚗️ Example 3 — Science / Engineering: Microplastic Pollution in Aquatic Environments",
        "session_key": "ex3_microplastics",
        "synthesis_type": "quantitative_summary",
        "effect_label": "Mean Concentration",
        "null_val": None,
        "prisma_counts": (150, 142, 142, 14),
        "overview_text": """
### Overview: Microplastic Pollution in Aquatic Environments

**Research Question:** What does the experimental literature report about the concentration, distribution, and detection methods of microplastic pollution across different aquatic environments?

**Corpus & Screening:** 150 records retrieved via Crossref/OpenAlex. 14 empirical studies providing explicit mean concentration measurements in aquatic environments were included.

**Key Findings:** The quantitative summary highlights massive variability in reported concentrations, heavily dependent on the environment type and detection method. Marine sediments show the highest absolute concentrations (often >400 particles/kg), acting as a sink. Freshwater systems exhibit high variability (0.5 to 3.2 particles/L) often correlated with proximity to urban centers. FTIR and Raman spectroscopy are the dominant detection methods.

**Limitations:** Lack of standardized sampling protocols and reporting units (particles/L vs. particles/m³ vs. particles/kg) makes direct meta-analytic pooling impossible, necessitating a stratified quantitative summary.
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "Microplastic concentrations in the North Sea", "Year": 2020, "Country": "Netherlands", "Environment_Type": "Marine", "Concentration_Mean": 0.34, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PP", "Sample_Size": 48, "Detection_Method": "FTIR"},
            {"Title": "Freshwater microplastics in the Rhine River", "Year": 2021, "Country": "Germany", "Environment_Type": "Freshwater", "Concentration_Mean": 1.28, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PET", "Sample_Size": 36, "Detection_Method": "Raman"},
            {"Title": "Microplastic pollution in coastal sediments (China)", "Year": 2022, "Country": "China", "Environment_Type": "Marine sediment", "Concentration_Mean": 412.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "PP, PE", "Sample_Size": 60, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in Amazon River tributaries", "Year": 2023, "Country": "Brazil", "Environment_Type": "Freshwater", "Concentration_Mean": 0.87, "Concentration_Unit": "particles/L", "Polymer_Types": "PET, PE", "Sample_Size": 24, "Detection_Method": "Visual+FTIR"},
            {"Title": "Mediterranean surface water microplastics", "Year": 2019, "Country": "Italy", "Environment_Type": "Marine", "Concentration_Mean": 0.15, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PS", "Sample_Size": 80, "Detection_Method": "FTIR"},
            {"Title": "Great Lakes freshwater microplastic assessment", "Year": 2020, "Country": "USA", "Environment_Type": "Freshwater", "Concentration_Mean": 2.10, "Concentration_Unit": "particles/L", "Polymer_Types": "PP, PE", "Sample_Size": 45, "Detection_Method": "Raman"},
            {"Title": "Deep sea sediment microplastics (Atlantic)", "Year": 2021, "Country": "UK", "Environment_Type": "Marine sediment", "Concentration_Mean": 280.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "Polyester", "Sample_Size": 30, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in the Ganges River basin", "Year": 2022, "Country": "India", "Environment_Type": "Freshwater", "Concentration_Mean": 3.15, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PET", "Sample_Size": 50, "Detection_Method": "Visual+FTIR"},
            {"Title": "Baltic Sea coastal microplastic pollution", "Year": 2018, "Country": "Sweden", "Environment_Type": "Marine", "Concentration_Mean": 0.42, "Concentration_Unit": "particles/L", "Polymer_Types": "PP, PE", "Sample_Size": 40, "Detection_Method": "FTIR"},
            {"Title": "Lake Victoria sediment microplastics", "Year": 2023, "Country": "Uganda", "Environment_Type": "Freshwater sediment", "Concentration_Mean": 195.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "PE, PVC", "Sample_Size": 25, "Detection_Method": "Raman"},
            {"Title": "Microplastics in Arctic sea ice", "Year": 2020, "Country": "Norway", "Environment_Type": "Marine", "Concentration_Mean": 0.08, "Concentration_Unit": "particles/L", "Polymer_Types": "Rayon, PE", "Sample_Size": 20, "Detection_Method": "FTIR"},
            {"Title": "Yangtze River microplastic flux", "Year": 2021, "Country": "China", "Environment_Type": "Freshwater", "Concentration_Mean": 2.80, "Concentration_Unit": "particles/L", "Polymer_Types": "PP, PE", "Sample_Size": 65, "Detection_Method": "FTIR"},
            {"Title": "Microplastics in coral reef sediments", "Year": 2022, "Country": "Australia", "Environment_Type": "Marine sediment", "Concentration_Mean": 340.0, "Concentration_Unit": "particles/kg", "Polymer_Types": "PE, PS", "Sample_Size": 35, "Detection_Method": "Raman"},
            {"Title": "Seine River microplastic monitoring", "Year": 2019, "Country": "France", "Environment_Type": "Freshwater", "Concentration_Mean": 1.15, "Concentration_Unit": "particles/L", "Polymer_Types": "PE, PP", "Sample_Size": 42, "Detection_Method": "FTIR"},
        ]),
        "effect_col": None,
        "ci_lower_col": None,
        "ci_upper_col": None,
        "title_col": "Title",
    },
    {
        "label": "💼 Example 4 — Management / Business: CSR and Firm Financial Performance",
        "session_key": "ex4_csr",
        "synthesis_type": "meta_analysis",
        "effect_label": "Correlation Coefficient (r)",
        "null_val": 0.0,
        "prisma_counts": (150, 140, 140, 16),
        "overview_text": """
### Overview: CSR and Firm Financial Performance

**Research Question:** What is the empirical evidence on the relationship between Corporate Social Responsibility (CSR) activities and firm financial performance (e.g., ROA, ROE, Tobin's Q)?

**Corpus & Screening:** 150 records retrieved via OpenAlex. 16 empirical studies reporting Pearson correlation coefficients (r) between a CSR metric and a financial performance metric were included.

**Key Findings:** The meta-analysis of 16 studies demonstrates a positive, statistically significant relationship between CSR and firm financial performance. The pooled correlation coefficient (r) indicates a small-to-medium effect size, supporting the "doing well by doing good" hypothesis. Environmental and Governance scores tend to drive the strongest financial correlations.

**Limitations:** Moderate heterogeneity (I² ~ 45%) suggests the relationship is influenced by the specific financial metric used (accounting-based ROA vs. market-based Tobin's Q) and the geographic market context (developed vs. emerging markets).
        """,
        "extraction_df": pd.DataFrame([
            {"Title": "CSR disclosure and ROA in manufacturing firms", "Year": 2019, "Country": "USA", "CSR_Measure": "ESG score", "FP_Measure": "ROA", "Correlation_r": 0.21, "CI_Lower": 0.12, "CI_Upper": 0.30, "Sample_Size": 340},
            {"Title": "Environmental CSR and Tobin's Q in European firms", "Year": 2020, "Country": "Europe", "CSR_Measure": "Env score", "FP_Measure": "Tobin's Q", "Correlation_r": 0.18, "CI_Lower": 0.08, "CI_Upper": 0.28, "Sample_Size": 520},
            {"Title": "Social responsibility and ROE in Asian markets", "Year": 2021, "Country": "Asia", "CSR_Measure": "Social score", "FP_Measure": "ROE", "Correlation_r": 0.14, "CI_Lower": 0.05, "CI_Upper": 0.23, "Sample_Size": 410},
            {"Title": "CSR and stock returns: a meta-analytic review", "Year": 2022, "Country": "Global", "CSR_Measure": "Composite ESG", "FP_Measure": "Stock returns", "Correlation_r": 0.11, "CI_Lower": 0.04, "CI_Upper": 0.18, "Sample_Size": 890},
            {"Title": "Governance CSR and firm value in emerging markets", "Year": 2023, "Country": "Emerging", "CSR_Measure": "Gov score", "FP_Measure": "Tobin's Q", "Correlation_r": 0.24, "CI_Lower": 0.15, "CI_Upper": 0.33, "Sample_Size": 280},
            {"Title": "CSR activities and ROA in the banking sector", "Year": 2018, "Country": "Global", "CSR_Measure": "CSR Index", "FP_Measure": "ROA", "Correlation_r": 0.16, "CI_Lower": 0.07, "CI_Upper": 0.25, "Sample_Size": 150},
            {"Title": "Green innovation and financial performance", "Year": 2021, "Country": "China", "CSR_Measure": "Env score", "FP_Measure": "ROA", "Correlation_r": 0.28, "CI_Lower": 0.19, "CI_Upper": 0.37, "Sample_Size": 420},
            {"Title": "Board diversity and firm profitability", "Year": 2019, "Country": "UK", "CSR_Measure": "Gov score", "FP_Measure": "ROE", "Correlation_r": 0.12, "CI_Lower": 0.02, "CI_Upper": 0.22, "Sample_Size": 210},
            {"Title": "Philanthropy and market valuation", "Year": 2020, "Country": "USA", "CSR_Measure": "Social score", "FP_Measure": "Tobin's Q", "Correlation_r": 0.09, "CI_Lower": 0.00, "CI_Upper": 0.18, "Sample_Size": 630},
            {"Title": "ESG controversies and stock price drops", "Year": 2022, "Country": "Global", "CSR_Measure": "ESG score", "FP_Measure": "Stock returns", "Correlation_r": 0.19, "CI_Lower": 0.11, "CI_Upper": 0.27, "Sample_Size": 1100},
            {"Title": "Supply chain CSR and operational efficiency", "Year": 2021, "Country": "Japan", "CSR_Measure": "Social score", "FP_Measure": "ROA", "Correlation_r": 0.15, "CI_Lower": 0.06, "CI_Upper": 0.24, "Sample_Size": 320},
            {"Title": "Carbon emissions reduction and firm value", "Year": 2023, "Country": "Europe", "CSR_Measure": "Env score", "FP_Measure": "Tobin's Q", "Correlation_r": 0.22, "CI_Lower": 0.13, "CI_Upper": 0.31, "Sample_Size": 480},
            {"Title": "Employee relations and ROE", "Year": 2018, "Country": "USA", "CSR_Measure": "Social score", "FP_Measure": "ROE", "Correlation_r": 0.13, "CI_Lower": 0.04, "CI_Upper": 0.22, "Sample_Size": 550},
            {"Title": "Executive compensation ties to ESG and performance", "Year": 2022, "Country": "Australia", "CSR_Measure": "Gov score", "FP_Measure": "ROA", "Correlation_r": 0.17, "CI_Lower": 0.08, "CI_Upper": 0.26, "Sample_Size": 290},
            {"Title": "Water usage disclosure and financial risk", "Year": 2020, "Country": "Global", "CSR_Measure": "Env score", "FP_Measure": "Stock returns", "Correlation_r": 0.10, "CI_Lower": 0.01, "CI_Upper": 0.19, "Sample_Size": 740},
            {"Title": "Community engagement and market share", "Year": 2021, "Country": "Canada", "CSR_Measure": "Social score", "FP_Measure": "Tobin's Q", "Correlation_r": 0.14, "CI_Lower": 0.05, "CI_Upper": 0.23, "Sample_Size": 380},
        ]),
        "effect_col": "Correlation_r",
        "ci_lower_col": "CI_Lower",
        "ci_upper_col": "CI_Upper",
        "title_col": "Title",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def compute_forest(df, effect_col, ci_lower_col, ci_upper_col, effect_label, null_val):
    """Render forest plot to a PNG bytes buffer and return (buf, pooled, lo, hi, i2, p_val)."""
    n = len(df)
    fig_height = max(5, n * 0.45 + 2.8)
    fig, ax = plt.subplots(figsize=(11, fig_height))

    y_studies = list(range(n, 0, -1))
    effects = df[effect_col].tolist()
    lowers  = df[ci_lower_col].tolist()
    uppers  = df[ci_upper_col].tolist()
    labels  = [str(t)[:65] for t in df["Title"].tolist()]

    for y, eff, lo, hi, lbl in zip(y_studies, effects, lowers, uppers, labels):
        ax.plot([lo, hi], [y, y], color="#2c7bb6", linewidth=1.5, solid_capstyle="round")
        ax.plot(eff, y, "s", color="#d7191c", markersize=7, zorder=5)
        ax.text(-0.02, y, lbl, ha="right", va="center", fontsize=8.5,
                transform=ax.get_yaxis_transform())

    # Meta-analysis math: Inverse-variance weighting
    weights = []
    variances = []
    for lo, hi in zip(lowers, uppers):
        se = (hi - lo) / 3.92
        var = se**2
        variances.append(var)
        weights.append(1.0 / var if var > 0 else 0)
        
    total_w = sum(weights)
    pooled    = sum(w * e for w, e in zip(weights, effects)) / total_w if total_w > 0 else float(np.mean(effects))
    pooled_se = 1.0 / total_w**0.5 if total_w > 0 else 0
    pooled_lo = pooled - 1.96 * pooled_se
    pooled_hi = pooled + 1.96 * pooled_se

    # Heterogeneity (Cochran's Q and I^2)
    Q = sum(w * (e - pooled)**2 for w, e in zip(weights, effects))
    df_Q = n - 1
    p_val = 1 - stats.chi2.cdf(Q, df_Q)
    i2 = max(0.0, 100 * (Q - df_Q) / Q) if Q > 0 else 0.0

    pooled_y = -0.6
    ax.axhline(y=pooled_y + 0.55, color="lightgray", linestyle="--", linewidth=0.6)
    ax.plot([pooled_lo, pooled_hi], [pooled_y, pooled_y], color="#1a9641", linewidth=3.0)
    ax.plot(pooled, pooled_y, "D", color="#1a9641", markersize=11, zorder=6)
    
    label_text = f"Pooled ({effect_label})\nI² = {i2:.1f}%, p = {p_val:.3f}"
    ax.text(-0.02, pooled_y, label_text, ha="right", va="center",
            fontsize=9, fontweight="bold", transform=ax.get_yaxis_transform())

    nv = null_val if null_val is not None else 0.0
    ax.axvline(nv, color="black", linestyle="-", linewidth=0.9, zorder=3)

    ax.set_yticks([])
    ax.set_ylim(pooled_y - 1.2, n + 0.9)
    ax.set_xlabel(effect_label, fontsize=10)
    ax.set_title("Forest Plot with Heterogeneity Statistics", fontsize=13, fontweight="bold", pad=12)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    legend_elements = [
        mpatches.Patch(color="#d7191c", label="Individual study estimate"),
        mpatches.Patch(color="#1a9641",
                       label=f"Pooled: {pooled:.3f}  95% CI [{pooled_lo:.3f}, {pooled_hi:.3f}]"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8.5, framealpha=0.9)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read(), pooled, pooled_lo, pooled_hi, i2, p_val


def compute_concentration_chart(df):
    """Render concentration bar chart to PNG bytes."""
    fig, ax = plt.subplots(figsize=(9, 5))
    
    # Sort by environment type for better grouping
    df_sorted = df.sort_values("Environment_Type")
    
    colors = {"Marine": "#2c7bb6", "Freshwater": "#abd9e9", "Marine sediment": "#d7191c", "Freshwater sediment": "#fdae61"}
    bar_colors = [colors.get(et, "#cccccc") for et in df_sorted["Environment_Type"]]
    
    ax.bar(df_sorted["Title"].str[:25] + "...", df_sorted["Concentration_Mean"],
           color=bar_colors, edgecolor="white")
           
    unit = df["Concentration_Unit"].iloc[0] if "Concentration_Unit" in df.columns else ""
    ax.set_ylabel(f"Mean Concentration ({unit})")
    ax.set_title("Mean Microplastic Concentrations by Environment Type")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    
    # Add legend
    legend_handles = [mpatches.Patch(color=c, label=l) for l, c in colors.items()]
    ax.legend(handles=legend_handles, title="Environment Type")
    
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read()


def compute_prisma(n_id, n_dedup, n_screened, n_included):
    """Render PRISMA 2020 flow diagram to PNG bytes."""
    fig, ax = plt.subplots(figsize=(9, 11))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    BOX_W   = 0.38
    BOX_H   = 0.10
    EXC_W   = 0.30
    LEFT_X  = 0.21
    RIGHT_X = 0.78
    Y_TOPS  = [0.92, 0.74, 0.56, 0.38, 0.20]

    n_duplicates        = n_id - n_dedup
    n_excluded_screen   = n_screened - int(n_screened * 0.60)
    n_fulltext          = int(n_screened * 0.60)
    n_excluded_fulltext = n_fulltext - n_included

    main_boxes = [
        f"Records identified\nvia API search\n(n = {n_id})",
        f"Records after\ndeduplication\n(n = {n_dedup})",
        f"Records screened\n(title & abstract)\n(n = {n_screened})",
        f"Full-text articles\nassessed for eligibility\n(n = {n_fulltext})",
        f"Studies included\nin synthesis\n(n = {n_included})",
    ]
    excl_boxes = [
        (Y_TOPS[1], f"Duplicates removed\n(n = {n_duplicates})"),
        (Y_TOPS[2], f"Excluded on\ntitle/abstract\n(n = {n_excluded_screen})"),
        (Y_TOPS[3], f"Excluded on\nfull-text\n(n = {n_excluded_fulltext})"),
    ]

    for y_c, text in zip(Y_TOPS, main_boxes):
        ax.add_patch(FancyBboxPatch(
            (LEFT_X - BOX_W / 2, y_c - BOX_H / 2), BOX_W, BOX_H,
            boxstyle="round,pad=0.015",
            facecolor="#dbeafe", edgecolor="#2563eb", linewidth=1.8, zorder=3,
        ))
        ax.text(LEFT_X, y_c, text, ha="center", va="center",
                fontsize=8.5, zorder=4, linespacing=1.4)

    for y_c, text in excl_boxes:
        ax.add_patch(FancyBboxPatch(
            (RIGHT_X - EXC_W / 2, y_c - BOX_H / 2), EXC_W, BOX_H,
            boxstyle="round,pad=0.015",
            facecolor="#fee2e2", edgecolor="#dc2626", linewidth=1.5, zorder=3,
        ))
        ax.text(RIGHT_X, y_c, text, ha="center", va="center",
                fontsize=8, zorder=4, linespacing=1.4)

    for i in range(len(Y_TOPS) - 1):
        ax.annotate(
            "", xy=(LEFT_X, Y_TOPS[i + 1] + BOX_H / 2),
            xytext=(LEFT_X, Y_TOPS[i] - BOX_H / 2),
            arrowprops=dict(arrowstyle="-|>", color="#1e3a5f", lw=1.5, mutation_scale=14),
            zorder=5,
        )

    for (y_c, _) in excl_boxes:
        ax.annotate(
            "", xy=(RIGHT_X - EXC_W / 2, y_c),
            xytext=(LEFT_X + BOX_W / 2, y_c),
            arrowprops=dict(arrowstyle="-|>", color="#991b1b", lw=1.2, mutation_scale=12),
            zorder=5,
        )

    ax.set_title("PRISMA 2020 Flow Diagram", fontsize=13, fontweight="bold", pad=14)
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read()


# ══════════════════════════════════════════════════════════════════════════════
# RENDER ONE GUIDED EXAMPLE (called inside expander)
# ══════════════════════════════════════════════════════════════════════════════

def render_guided_example(ex):
    sk  = ex["session_key"]
    df  = ex["extraction_df"].copy()

    # ── Overview Section ───────────────────────────────────────────────────────
    st.markdown(ex["overview_text"])
    st.markdown("---")

    # ── Step 1: Extraction table ───────────────────────────────────────────────
    st.subheader("Step 1 — Structured Data Extraction")
    st.markdown("""
The table below shows the structured extraction output for this case study.
Each row corresponds to one included study; fields were extracted using a
discipline-specific LLM prompt schema. No coding required.
    """)
    st.success(f"✅ {len(df)} studies extracted.")
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "⬇️ Download extraction table as CSV",
        df.to_csv(index=False).encode("utf-8"),
        f"day3_{sk}_extraction.csv", "text/csv",
        key=f"dl_extract_{sk}",
    )

    st.markdown("---")

    # ── Step 2: Synthesis ──────────────────────────────────────────────────────
    st.subheader("Step 2 — Synthesis & Meta-Analysis")

    if ex["synthesis_type"] == "meta_analysis":
        st.markdown(f"""
This full meta-analysis pools the **{ex['effect_label']}** across the {len(df)} extracted studies
using inverse-variance weighting. The diamond on the forest plot represents the
pooled estimate with its 95% confidence interval. Heterogeneity statistics (I² and Cochran's Q p-value) 
are reported alongside the pooled estimate.
        """)

        forest_key = f"day3_{sk}_forest_png"

        if forest_key not in st.session_state:
            png, pooled, plo, phi, i2, p_val = compute_forest(
                df, ex["effect_col"], ex["ci_lower_col"], ex["ci_upper_col"],
                ex["effect_label"], ex["null_val"],
            )
            st.session_state[forest_key] = (png, pooled, plo, phi, i2, p_val)

        png, pooled, plo, phi, i2, p_val = st.session_state[forest_key]
        st.image(png, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Pooled {ex['effect_label']}", f"{pooled:.3f}", f"95% CI: [{plo:.3f}, {phi:.3f}]")
        col2.metric("Heterogeneity (I²)", f"{i2:.1f}%", "0% = none, >75% = high", delta_color="off")
        col3.metric("Cochran's Q (p-value)", f"{p_val:.3f}", "<0.05 indicates significant heterogeneity", delta_color="off")
        
        st.download_button(
            "⬇️ Download forest plot (PNG)", png,
            f"day3_{sk}_forest.png", "image/png",
            key=f"dl_forest_{sk}",
        )

    elif ex["synthesis_type"] == "narrative":
        st.markdown("""
The narrative synthesis organises the extracted data into a structured summary table
suitable for the Results section of a systematic review, categorizing findings across domains.
        """)
        cols_show = [c for c in ["Title", "Year", "Country", "Methodology",
                                  "Sample_Size", "Key_Finding_Employment",
                                  "Key_Finding_Wellbeing", "Key_Finding_Poverty"]
                     if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True)

    elif ex["synthesis_type"] == "quantitative_summary":
        st.markdown("""
The quantitative summary compares mean microplastic concentrations across environment
types and studies, highlighting the variance between marine, freshwater, and sediment sinks.
        """)
        if "Concentration_Mean" in df.columns and "Environment_Type" in df.columns:
            summary = (
                df.groupby("Environment_Type")["Concentration_Mean"]
                .agg(["mean", "min", "max", "count"])
                .rename(columns={"mean": "Mean", "min": "Min",
                                  "max": "Max", "count": "N Studies"})
            )
            st.dataframe(summary, use_container_width=True)

        chart_key = f"day3_{sk}_chart_png"
        if chart_key not in st.session_state:
            st.session_state[chart_key] = compute_concentration_chart(df)

        st.image(st.session_state[chart_key], use_container_width=True)
        st.download_button(
            "⬇️ Download chart (PNG)", st.session_state[chart_key],
            f"day3_{sk}_chart.png", "image/png",
            key=f"dl_chart_{sk}",
        )

    st.markdown("---")

    # ── Step 3: PRISMA ─────────────────────────────────────────────────────────
    st.subheader("Step 3 — PRISMA 2020 Flow Diagram")
    n_id, n_dedup, n_screened, n_included = ex["prisma_counts"]
    st.markdown(f"""
Record flow: **{n_id}** identified → **{n_dedup}** after deduplication →
**{n_screened}** screened → **{n_included}** included in synthesis.
    """)

    prisma_key = f"day3_{sk}_prisma_png"
    if prisma_key not in st.session_state:
        st.session_state[prisma_key] = compute_prisma(n_id, n_dedup, n_screened, n_included)

    st.image(st.session_state[prisma_key], use_container_width=True)
    st.download_button(
        "⬇️ Download PRISMA diagram (PNG)", st.session_state[prisma_key],
        f"day3_{sk}_prisma.png", "image/png",
        key=f"dl_prisma_{sk}",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

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
weighting and produces a forest plot with a pooled estimate, confidence interval, and heterogeneity statistics (I²).

**PRISMA 2020 flow diagram** is generated automatically from the record counts at each
stage of the pipeline.

### The Four Case Studies at a Glance

| # | Discipline | Topic | Synthesis Type |
|---|---|---|---|
| 1 | Health Sciences | Health Inequalities in Chronic Disease Care | Meta-analysis (Risk Ratio) |
| 2 | Social Sciences | Universal Basic Income (UBI) Policy Outcomes | Narrative synthesis |
| 3 | Science / Engineering | Microplastic Pollution in Aquatic Environments | Quantitative summary |
| 4 | Management / Business | CSR and Firm Financial Performance | Meta-analysis (Correlation r) |

### Session Structure

| Hour | Content |
|------|---------|
| **Hour 1** | Introduce structured data extraction. Explain narrative vs. quantitative synthesis. Present the four extraction schemas. |
| **Hour 2** | Demonstrate LLM-assisted extraction for the four case studies. Participants inspect the extraction table and download the CSV. |
| **Hour 3** | Produce synthesis outputs: narrative overview, forest plot (meta-analysis cases), and PRISMA flow diagram. |

Use the sidebar to go to **📌 Guided Examples** or **🔎 BYOD — Your Own Synthesis**.
    """)

# ══════════════════════════════════════════════════════════════════════════════
# GUIDED EXAMPLES — all four displayed simultaneously
# ══════════════════════════════════════════════════════════════════════════════

elif section == "📌 Guided Examples":
    st.title("📌 Day 3 — Guided Examples")
    st.markdown("""
Each example below walks through the full Day 3 pipeline for one case study:
**structured data extraction**, **synthesis** (meta-analysis, narrative, or quantitative
summary), and a **PRISMA 2020 flow diagram**. All outputs are pre-rendered and persist
on screen — no re-computation on page refresh. Expand any example to explore it.
    """)

    for ex in GUIDED_EXAMPLES:
        st.markdown("---")
        with st.expander(ex["label"], expanded=False):
            render_guided_example(ex)

# ══════════════════════════════════════════════════════════════════════════════
# BYOD
# ══════════════════════════════════════════════════════════════════════════════

elif section == "🔎 BYOD — Your Own Synthesis":
    st.title("🔎 Day 3 — Bring Your Own Data")
    st.markdown("""
Use this section to produce a synthesis from **your own included studies**.
Upload the CSV of included studies from Day 2 (or any CSV with Title, Year, and Abstract
columns) and define your extraction schema below. No coding required.
    """)

    uploaded = st.file_uploader("Upload included studies CSV", type=["csv"])

    if uploaded is None and "byod_included_df" in st.session_state:
        st.info("Using included studies carried over from Day 2 BYOD session.")
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

        template_df = pd.DataFrame([
            {f: row.get(f, "") for f in schema_fields}
            for _, row in df.head(20).iterrows()
        ])
        st.dataframe(template_df, use_container_width=True)
        st.download_button(
            "⬇️ Download extraction template", 
            template_df.to_csv(index=False).encode("utf-8"),
            "byod_extraction_template.csv", "text/csv",
            key="dl_byod_template",
        )

        st.markdown("---")
        st.subheader("Forest Plot (if you have effect size data)")
        extracted_upload = st.file_uploader(
            "Upload completed extraction CSV "
            "(must have Effect_Size, CI_Lower, CI_Upper, Title columns)",
            type=["csv"], key="byod_forest_upload",
        )
        if extracted_upload is not None:
            df_ext = pd.read_csv(extracted_upload)
            required = {"Effect_Size", "CI_Lower", "CI_Upper", "Title"}
            if required.issubset(df_ext.columns):
                effect_label = st.text_input("Effect size label", value="Effect Size")
                png, pooled, plo, phi, i2, p_val = compute_forest(
                    df_ext, "Effect_Size", "CI_Lower", "CI_Upper", effect_label, None
                )
                st.image(png, use_container_width=True)
                
                col1, col2, col3 = st.columns(3)
                col1.metric(f"Pooled {effect_label}", f"{pooled:.3f}", f"95% CI: [{plo:.3f}, {phi:.3f}]")
                col2.metric("Heterogeneity (I²)", f"{i2:.1f}%", "0% = none, >75% = high", delta_color="off")
                col3.metric("Cochran's Q (p-value)", f"{p_val:.3f}", "<0.05 indicates significant heterogeneity", delta_color="off")
                
                st.download_button("⬇️ Download forest plot (PNG)", png,
                                   "byod_forest.png", "image/png", key="dl_byod_forest")
            else:
                missing = required - set(df_ext.columns)
                st.error(f"Missing required columns: {missing}")

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
            n_included_byod = st.number_input("Studies included", min_value=1,
                                               value=max(1, len(df)))

        png_prisma = compute_prisma(int(n_id), int(n_dedup), int(n_screened), int(n_included_byod))
        st.image(png_prisma, use_container_width=True)
        st.download_button(
            "⬇️ Download PRISMA diagram (PNG)",
            png_prisma,
            "byod_prisma.png", "image/png", key="dl_byod_prisma",
        )
