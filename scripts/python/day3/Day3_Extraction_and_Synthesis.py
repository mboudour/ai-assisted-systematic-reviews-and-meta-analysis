"""
Day 3 — Structured Data Extraction and Synthesis
AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar

This script demonstrates LLM-assisted structured data extraction (via Ollama)
and produces narrative/quantitative synthesis outputs for the four case studies.

Run from the repository root:
    python scripts/python/day3/Day3_Extraction_and_Synthesis.py

Requirements: pandas, numpy, scipy, matplotlib, requests
For local LLM: install Ollama from https://ollama.com and run:
    ollama pull llama3:8b
"""

import json
import os

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import requests

# ── Configuration ──────────────────────────────────────────────────────────────

DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache")
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b"

CASE_STUDIES = [
    {
        "id": "ex1_health",
        "label": "Health Inequalities in Chronic Disease Care",
        "included_file": "day2_ex1_health_included.csv",
        "synthesis_type": "meta_analysis",
        "effect_col": "Effect_Size",
        "ci_lower": "CI_Lower",
        "ci_upper": "CI_Upper",
        "effect_label": "Risk Ratio (RR)",
        "extraction_schema": {
            "Title": "string",
            "Year": "integer",
            "Country": "string",
            "Population": "string",
            "Intervention": "string",
            "Comparator": "string",
            "Outcome": "string",
            "Effect_Size": "float (risk ratio or odds ratio)",
            "CI_Lower": "float (lower 95% CI)",
            "CI_Upper": "float (upper 95% CI)",
            "Sample_Size": "integer",
            "Study_Design": "string",
        },
    },
    {
        "id": "ex2_ubi",
        "label": "Universal Basic Income (UBI) Policy Outcomes",
        "included_file": "day2_ex2_ubi_included.csv",
        "synthesis_type": "narrative",
        "extraction_schema": {
            "Title": "string",
            "Year": "integer",
            "Country": "string",
            "Programme_Name": "string",
            "Methodology": "string",
            "Sample_Size": "integer",
            "Duration_Months": "integer",
            "Key_Finding_Employment": "string",
            "Key_Finding_Wellbeing": "string",
            "Key_Finding_Poverty": "string",
        },
    },
    {
        "id": "ex3_microplastics",
        "label": "Microplastic Pollution in Aquatic Environments",
        "included_file": "day2_ex3_microplastics_included.csv",
        "synthesis_type": "quantitative_summary",
        "extraction_schema": {
            "Title": "string",
            "Year": "integer",
            "Country": "string",
            "Environment_Type": "string (freshwater/marine/sediment)",
            "Concentration_Mean": "float",
            "Concentration_Unit": "string (particles/L or particles/kg)",
            "Polymer_Types": "string",
            "Sample_Size": "integer",
            "Detection_Method": "string",
        },
    },
    {
        "id": "ex4_csr",
        "label": "CSR and Firm Financial Performance",
        "included_file": "day2_ex4_csr_included.csv",
        "synthesis_type": "meta_analysis",
        "effect_col": "Correlation_r",
        "ci_lower": "CI_Lower",
        "ci_upper": "CI_Upper",
        "effect_label": "Correlation Coefficient (r)",
        "extraction_schema": {
            "Title": "string",
            "Year": "integer",
            "Country": "string",
            "CSR_Measure": "string",
            "FP_Measure": "string",
            "Correlation_r": "float",
            "CI_Lower": "float",
            "CI_Upper": "float",
            "Sample_Size": "integer",
            "Industry_Sector": "string",
        },
    },
]

# ── LLM Extraction via Ollama ──────────────────────────────────────────────────

def llm_extract_ollama(title, abstract, schema, model=OLLAMA_MODEL):
    """
    LLM-assisted structured data extraction using Ollama.
    Returns a dict matching the schema fields.
    """
    schema_str = "\n".join(f"  - {k}: {v}" for k, v in schema.items())
    prompt = f"""You are a systematic review data extractor. Extract the following fields from the study below.
Return your answer as a valid JSON object with exactly these keys:
{schema_str}

If a field cannot be determined from the abstract, use null.

Study Title: {title}
Abstract: {abstract[:600]}

JSON output:"""

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=90,
        )
        r.raise_for_status()
        response_text = r.json().get("response", "").strip()
        # Extract JSON from response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
        return {k: None for k in schema}
    except Exception as e:
        print(f"    LLM extraction error: {e}")
        return {k: None for k in schema}


def check_ollama_available():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# ── Forest Plot ────────────────────────────────────────────────────────────────

def draw_forest_plot(df, effect_col, ci_lower, ci_upper, title_col, effect_label, output_path):
    """Draw and save a forest plot."""
    n = len(df)
    fig, ax = plt.subplots(figsize=(10, max(4, n * 0.7 + 1.5)))

    y_positions = list(range(n, 0, -1))
    effects = df[effect_col].tolist()
    lowers = df[ci_lower].tolist()
    uppers = df[ci_upper].tolist()
    labels = df[title_col].str[:55].tolist()

    for y, eff, lo, hi, lbl in zip(y_positions, effects, lowers, uppers, labels):
        ax.plot([lo, hi], [y, y], color="#2c7bb6", linewidth=1.5)
        ax.plot(eff, y, "s", color="#d7191c", markersize=8, zorder=5)
        ax.text(-0.05, y, lbl, ha="right", va="center", fontsize=8,
                transform=ax.get_yaxis_transform())

    # Pooled estimate (inverse-variance weighted)
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

    null_val = 1.0 if "Ratio" in effect_label or "RR" in effect_label else 0.0
    ax.axvline(null_val, color="black", linestyle="-", linewidth=0.8)
    ax.set_yticks([])
    ax.set_xlabel(effect_label, fontsize=10)
    ax.set_title("Forest Plot", fontsize=12, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    legend_elements = [
        mpatches.Patch(color="#d7191c", label="Individual study estimate"),
        mpatches.Patch(color="#1a9641",
                       label=f"Pooled: {pooled:.3f} [{pooled_lo:.3f}, {pooled_hi:.3f}]"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Forest plot saved: {output_path}")
    return pooled, pooled_lo, pooled_hi

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ollama_available = check_ollama_available()
    if not ollama_available:
        print("⚠️  Ollama is not running. LLM extraction will be skipped.")
        print("   To enable: install Ollama from https://ollama.com, then run: ollama pull llama3:8b")

    for cs in CASE_STUDIES:
        print(f"\n{'='*60}")
        print(f"Case Study: {cs['label']}")
        print(f"{'='*60}")

        included_path = os.path.join(DATA_DIR, cs["included_file"])
        if not os.path.exists(included_path):
            print(f"  ⚠️  Included studies file not found: {included_path}. Run Day 2 script first.")
            continue

        df = pd.read_csv(included_path)
        print(f"  Included studies loaded: {len(df)} records.")

        # LLM Extraction
        if ollama_available:
            print(f"  Running LLM extraction (Ollama / {OLLAMA_MODEL})…")
            extracted_rows = []
            for i, row in df.iterrows():
                if i % 5 == 0:
                    print(f"    Extracting record {i+1}/{len(df)}…")
                result = llm_extract_ollama(
                    str(row.get("Title", "")),
                    str(row.get("Abstract", "")),
                    cs["extraction_schema"],
                )
                extracted_rows.append(result)

            df_extracted = pd.DataFrame(extracted_rows)
            extract_path = os.path.join(DATA_DIR, f"day3_{cs['id']}_extraction.csv")
            df_extracted.to_csv(extract_path, index=False)
            print(f"  Extraction saved: {extract_path}")
        else:
            print("  Skipping LLM extraction (Ollama not available).")
            df_extracted = df.copy()

        # Forest plot for meta-analysis cases
        if cs["synthesis_type"] == "meta_analysis":
            eff_col = cs["effect_col"]
            lo_col  = cs["ci_lower"]
            hi_col  = cs["ci_upper"]
            if all(c in df_extracted.columns for c in [eff_col, lo_col, hi_col]):
                df_plot = df_extracted[[eff_col, lo_col, hi_col, "Title"]].dropna()
                if len(df_plot) >= 2:
                    forest_path = os.path.join(DATA_DIR, f"day3_{cs['id']}_forest.png")
                    pooled, lo, hi = draw_forest_plot(
                        df_plot, eff_col, lo_col, hi_col, "Title",
                        cs["effect_label"], forest_path
                    )
                    print(f"  Pooled {cs['effect_label']}: {pooled:.3f} [{lo:.3f}, {hi:.3f}]")

    print("\n✅ Day 3 extraction and synthesis complete.")
