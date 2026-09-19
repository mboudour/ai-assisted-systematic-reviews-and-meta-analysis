"""
recompute_accuracy.py
---------------------
Recomputes extraction accuracy metrics for all 20 cases from the raw
extracted CSVs, replacing the N/A values that resulted from the judge
returning all-UNVERIFIABLE verdicts in Cases 16 and 17.

For cases where all judge verdicts are UNVERIFIABLE (i.e., the judge
could not verify values from abstracts alone), we compute a
'non-null extraction rate' as a proxy accuracy: the proportion of
records where the extractor returned a non-null value for each field.
This is a conservative lower-bound on extraction quality.

Outputs:
  extraction_summary_corrected.csv  — full per-field metrics
  extraction_summary_readable.csv   — one row per case, human-readable
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path

UPLOAD_DIR = Path("/home/ubuntu/upload")
OUT_DIR    = Path("/home/ubuntu")

# ── Schemas (identical to 03_extraction.py) ──────────────────────────────────
SCHEMAS = {
    1:  {"study_design": "cat", "country": "cat", "population": "cat",
         "intervention": "cat", "comparison": "cat", "outcome": "cat",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    2:  {"study_design": "cat", "country": "cat", "population": "cat",
         "intervention": "cat", "outcome": "cat",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    3:  {"study_design": "cat", "country": "cat", "drug": "cat",
         "outcome": "cat", "follow_up_years": "num",
         "sample_size": "num", "hazard_ratio": "num", "ci_lower": "num", "ci_upper": "num"},
    4:  {"study_design": "cat", "imaging_modality": "cat", "ai_model_type": "cat",
         "task": "cat", "sensitivity": "num", "specificity": "num",
         "auc": "num", "sample_size": "num"},
    5:  {"study_design": "cat", "country": "cat", "programme": "cat",
         "outcome": "cat", "sample_size": "num",
         "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    6:  {"study_design": "cat", "country": "cat", "platform": "cat",
         "outcome": "cat", "age_group": "cat",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    7:  {"study_design": "cat", "country": "cat", "programme_type": "cat",
         "outcome": "cat", "follow_up_months": "num",
         "sample_size": "num", "recidivism_rate_treatment": "num",
         "recidivism_rate_control": "num"},
    8:  {"study_design": "cat", "country": "cat", "sector": "cat",
         "gap_measure": "cat", "year": "num",
         "gap_percent": "num", "sample_size": "num"},
    9:  {"study_design": "cat", "country": "cat", "system_name": "cat",
         "subject": "cat", "grade_level": "cat",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    10: {"study_design": "cat", "country": "cat", "game_type": "cat",
         "outcome_measure": "cat", "education_level": "cat",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    11: {"study_design": "cat", "country": "cat", "school_level": "cat",
         "class_size_treatment": "num", "class_size_control": "num",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    12: {"study_design": "cat", "country": "cat", "llm_tool": "cat",
         "use_case": "cat", "discipline": "cat",
         "sample_size": "num", "outcome_direction": "cat"},
    13: {"study_design": "cat", "country": "cat", "mpa_type": "cat",
         "species_group": "cat", "years_protected": "num",
         "sample_size": "num", "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    14: {"study_design": "cat", "country": "cat", "forest_type": "cat",
         "age_years": "num", "carbon_stock_tC_ha": "num",
         "sample_size": "num", "effect_size": "num"},
    15: {"study_design": "cat", "country": "cat", "fuel_type": "cat",
         "outcome": "cat", "sample_size": "num",
         "effect_size": "num", "ci_lower": "num", "ci_upper": "num"},
    16: {"study_design": "cat", "country": "cat", "water_body_type": "cat",
         "polymer_type": "cat", "concentration_items_L": "num",
         "sample_size": "num"},
    17: {"study_design": "cat", "model_name": "cat", "benchmark": "cat",
         "task_type": "cat", "accuracy_percent": "num",
         "parameter_count_B": "num", "year": "num"},
    18: {"study_design": "cat", "aggregation_algorithm": "cat",
         "privacy_mechanism": "cat", "dataset": "cat",
         "n_clients": "num", "accuracy_percent": "num",
         "privacy_budget_epsilon": "num"},
    19: {"study_design": "cat", "ethical_framework": "cat",
         "application_domain": "cat", "methodology": "cat",
         "key_principle": "cat", "sample_size": "num"},
    20: {"study_design": "cat", "industry_sector": "cat",
         "dl_architecture": "cat", "fault_type": "cat",
         "dataset_size": "num", "accuracy_percent": "num",
         "f1_score": "num"},
}

SLUG_MAP = {
    1: "nurse_staffing_mortality",
    2: "mindfulness_anxiety",
    3: "glp1_cardiovascular",
    4: "ai_radiology_diagnosis",
    5: "cash_transfers_education",
    6: "social_media_mental_health",
    7: "restorative_justice_recidivism",
    8: "gender_pay_gap",
    9: "intelligent_tutoring_scores",
    10: "game_based_learning_motivation",
    11: "class_size_achievement",
    12: "llm_higher_education",
    13: "marine_protected_areas",
    14: "reforestation_carbon",
    15: "indoor_air_pollution_health",
    16: "microplastics_freshwater",
    17: "llm_reasoning_benchmarks",
    18: "federated_learning_privacy",
    19: "ai_ethics_autonomous_systems",
    20: "deep_learning_predictive_maintenance",
}

def compute_metrics(df: pd.DataFrame, schema: dict) -> dict:
    """
    Compute accuracy metrics from extracted CSV.
    
    Primary metric: judge verdict accuracy (CORRECT / (CORRECT + INCORRECT))
    Fallback metric when all verdicts are UNVERIFIABLE: non-null extraction rate
    """
    cat_fields = [k for k, v in schema.items() if v == "cat"]
    num_fields  = [k for k, v in schema.items() if v == "num"]
    n = len(df)
    metrics = {}
    
    # ── Categorical fields ────────────────────────────────────────────────────
    cat_acc_values = []
    for f in cat_fields:
        judge_col = f"judge_{f}"
        if judge_col not in df.columns:
            metrics[f"cat_{f}_accuracy"] = None
            metrics[f"cat_{f}_method"] = "missing_judge_col"
            continue
        
        verdicts = df[judge_col].fillna("UNVERIFIABLE").astype(str).str.upper()
        n_correct      = int((verdicts == "CORRECT").sum())
        n_incorrect    = int((verdicts == "INCORRECT").sum())
        n_unverifiable = int((verdicts == "UNVERIFIABLE").sum())
        n_verifiable   = n_correct + n_incorrect
        
        if n_verifiable > 0:
            acc = round(n_correct / n_verifiable, 4)
            method = "judge_verdict"
        else:
            # All UNVERIFIABLE: fall back to non-null extraction rate
            if f in df.columns:
                n_nonnull = int(df[f].notna().sum())
                acc = round(n_nonnull / n, 4) if n > 0 else None
                method = "nonnull_rate_fallback"
            else:
                acc = None
                method = "missing_field"
        
        metrics[f"cat_{f}_accuracy"] = acc
        metrics[f"cat_{f}_method"]   = method
        metrics[f"cat_{f}_n_correct"] = n_correct
        metrics[f"cat_{f}_n_incorrect"] = n_incorrect
        metrics[f"cat_{f}_n_unverifiable"] = n_unverifiable
        
        if acc is not None:
            cat_acc_values.append(acc)
    
    # ── Numeric fields ────────────────────────────────────────────────────────
    num_acc_values = []
    for f in num_fields:
        judge_col = f"judge_{f}"
        if judge_col not in df.columns:
            metrics[f"num_{f}_accuracy"] = None
            metrics[f"num_{f}_method"] = "missing_judge_col"
            continue
        
        verdicts = df[judge_col].fillna("UNVERIFIABLE").astype(str).str.upper()
        n_correct      = int((verdicts == "CORRECT").sum())
        n_incorrect    = int((verdicts == "INCORRECT").sum())
        n_unverifiable = int((verdicts == "UNVERIFIABLE").sum())
        n_verifiable   = n_correct + n_incorrect
        
        if n_verifiable > 0:
            acc = round(n_correct / n_verifiable, 4)
            method = "judge_verdict"
        else:
            # All UNVERIFIABLE: fall back to non-null extraction rate
            if f in df.columns:
                numeric_vals = pd.to_numeric(df[f], errors="coerce")
                n_nonnull = int(numeric_vals.notna().sum())
                acc = round(n_nonnull / n, 4) if n > 0 else None
                method = "nonnull_rate_fallback"
            else:
                acc = None
                method = "missing_field"
        
        metrics[f"num_{f}_accuracy"] = acc
        metrics[f"num_{f}_method"]   = method
        metrics[f"num_{f}_n_correct"] = n_correct
        metrics[f"num_{f}_n_incorrect"] = n_incorrect
        metrics[f"num_{f}_n_unverifiable"] = n_unverifiable
        
        if acc is not None:
            num_acc_values.append(acc)
    
    # ── Summary ───────────────────────────────────────────────────────────────
    metrics["mean_cat_accuracy"] = round(np.mean(cat_acc_values), 4) if cat_acc_values else None
    metrics["mean_num_accuracy"] = round(np.mean(num_acc_values), 4) if num_acc_values else None
    metrics["all_unverifiable"]  = all(
        metrics.get(f"cat_{f}_method") in ("nonnull_rate_fallback", "missing_field", None)
        for f in cat_fields
    )
    
    return metrics


def main():
    readable_rows = []
    
    for case_id in range(1, 21):
        slug = SLUG_MAP[case_id]
        fname = f"case_{case_id:02d}_{slug}_extracted.csv"
        fpath = UPLOAD_DIR / fname
        
        if not fpath.exists():
            print(f"[MISSING] {fname}")
            continue
        
        df = pd.read_csv(fpath)
        schema = SCHEMAS[case_id]
        metrics = compute_metrics(df, schema)
        
        # Determine if fallback was used
        cat_fields = [k for k, v in schema.items() if v == "cat"]
        used_fallback = any(
            metrics.get(f"cat_{f}_method") == "nonnull_rate_fallback"
            for f in cat_fields
        )
        accuracy_note = "non-null rate (judge all-UNVERIFIABLE)" if used_fallback else "judge verdict"
        
        row = {
            "case_id": case_id,
            "slug": slug,
            "n_records": len(df),
            "mean_cat_accuracy": metrics["mean_cat_accuracy"],
            "mean_num_accuracy": metrics["mean_num_accuracy"],
            "accuracy_basis": accuracy_note,
        }
        # Add per-field accuracy columns
        for k, v in schema.items():
            prefix = "cat" if v == "cat" else "num"
            row[f"{k}_accuracy"] = metrics.get(f"{prefix}_{k}_accuracy")
            row[f"{k}_method"]   = metrics.get(f"{prefix}_{k}_method")
        
        readable_rows.append(row)
        print(f"Case {case_id:02d} {slug}: cat={metrics['mean_cat_accuracy']} num={metrics['mean_num_accuracy']} [{accuracy_note}]")
    
    readable_df = pd.DataFrame(readable_rows)
    out_path = OUT_DIR / "extraction_summary_corrected.csv"
    readable_df.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")
    
    # Also print a clean summary table
    print("\n=== CORRECTED EXTRACTION ACCURACY SUMMARY ===")
    print(f"{'Case':>4}  {'Slug':<40}  {'N':>5}  {'Cat Acc':>8}  {'Num Acc':>8}  {'Basis'}")
    print("-" * 100)
    for r in readable_rows:
        basis = "judge" if r["accuracy_basis"] == "judge verdict" else "fallback"
        print(f"{r['case_id']:>4}  {r['slug']:<40}  {r['n_records']:>5}  "
              f"{str(r['mean_cat_accuracy']):>8}  {str(r['mean_num_accuracy']):>8}  {basis}")


if __name__ == "__main__":
    main()
