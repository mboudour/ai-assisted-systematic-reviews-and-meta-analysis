"""
03_extraction.py
----------------
Performs structured data extraction on all included records using two passes:
  Pass 1 — LLM Extractor: extracts PICO fields and numeric data
  Pass 2 — LLM-as-Judge: verifies each extracted field

Saves per-case extraction results to data/extracted/
Appends agreement metrics (Cohen's kappa, MAE) to outputs/extraction_summary.csv

Run:
    python scripts/03_extraction.py

Requires: api_keys.env, data/screened/ populated by 02_screening.py
"""

import os, json, time
from pathlib import Path
import pandas as pd
import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv
from sklearn.metrics import cohen_kappa_score
from openai import OpenAI

# ── Load API keys ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "api_keys.env")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SCREENED_DIR  = ROOT / "data" / "screened"
EXTRACTED_DIR = ROOT / "data" / "extracted"
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR   = ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# ── Extraction schemas per case ───────────────────────────────────────────────
# Each schema defines the fields to extract and their type (categorical/numeric)
SCHEMAS = {
    # Health & Clinical
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
    # Social & Behavioural
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
    # Education & Learning
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
    # Environmental
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
    # Computer Science & AI
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

# ── LLM Extractor ─────────────────────────────────────────────────────────────
EXTRACTOR_SYSTEM = (
    "You are an expert data extractor for systematic reviews. "
    "Extract the requested fields from the title and abstract. "
    "Return a valid JSON object with exactly the requested keys. "
    "Use null for fields that cannot be determined from the text. "
    "For numeric fields, return a number or null. "
    "For categorical fields, return a short string or null."
)

# Use gpt-4o-mini to reduce cost by 95% and avoid rate limits
MODEL = "gpt-4o-mini"

def extract_record(title: str, abstract: str, schema: dict) -> dict:
    fields_desc = "\n".join(
        f'  "{k}": {"numeric value or null" if v == "num" else "short string or null"}'
        for k, v in schema.items()
    )
    user_msg = (
        f"Title: {title}\n\nAbstract: {abstract or '(no abstract)'}\n\n"
        f"Extract the following fields and return as JSON:\n{{\n{fields_desc}\n}}"
    )
    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": EXTRACTOR_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            if "insufficient_quota" in str(e):
                print("\n[FATAL] OpenAI quota exhausted. Please add credit at platform.openai.com")
                raise e
            if attempt < 4:
                time.sleep(10 * (attempt + 1))
            else:
                return {k: None for k in schema}

# ── LLM-as-Judge ─────────────────────────────────────────────────────────────
JUDGE_SYSTEM = (
    "You are a systematic review auditor. "
    "Given a title, abstract, and a set of extracted fields, "
    "verify whether each extracted value is consistent with the source text. "
    "Return a JSON object with the same keys as the extracted fields, "
    "where each value is either 'CORRECT', 'INCORRECT', or 'UNVERIFIABLE'."
)

def judge_record(title: str, abstract: str, extracted: dict) -> dict:
    extracted_str = json.dumps(extracted, indent=2)
    user_msg = (
        f"Title: {title}\n\nAbstract: {abstract or '(no abstract)'}\n\n"
        f"Extracted fields:\n{extracted_str}\n\n"
        "For each field, return CORRECT, INCORRECT, or UNVERIFIABLE."
    )
    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ],
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            if "insufficient_quota" in str(e):
                raise e
            if attempt < 4:
                time.sleep(10 * (attempt + 1))
            else:
                return {k: "UNVERIFIABLE" for k in extracted}

# ── Agreement metrics ─────────────────────────────────────────────────────────
def compute_agreement(df_extracted: pd.DataFrame, schema: dict) -> dict:
    """
    Compute per-field agreement between extractor and judge.
    Handles UNVERIFIABLE gracefully so it doesn't cause None accuracies.
    """
    cat_fields = [k for k, v in schema.items() if v == "cat"]
    num_fields  = [k for k, v in schema.items() if v == "num"]
    metrics = {}
    
    for f in cat_fields:
        judge_col = f"judge_{f}"
        if judge_col in df_extracted.columns:
            verdicts = df_extracted[judge_col].fillna("UNVERIFIABLE")
            # Force case-insensitive match for robustness
            verdicts = verdicts.astype(str).str.upper()
            correct = (verdicts == "CORRECT").sum()
            total   = (verdicts != "UNVERIFIABLE").sum()
            metrics[f"cat_accuracy_{f}"] = round(correct / total, 4) if total > 0 else "N/A"
            metrics[f"cat_unverifiable_{f}"] = int((verdicts == "UNVERIFIABLE").sum())
            
    for f in num_fields:
        judge_col = f"judge_{f}"
        if f in df_extracted.columns and judge_col in df_extracted.columns:
            verdicts = df_extracted[judge_col].fillna("UNVERIFIABLE").astype(str).str.upper()
            metrics[f"num_n_correct_{f}"] = int((verdicts == "CORRECT").sum())
            metrics[f"num_n_incorrect_{f}"] = int((verdicts == "INCORRECT").sum())
            metrics[f"num_n_unverifiable_{f}"] = int((verdicts == "UNVERIFIABLE").sum())
            
    return metrics

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    MAX_INCLUDE = 200  # Cap included records per case to prevent infinite runs
    
    summary_rows = []
    screened_files = sorted(SCREENED_DIR.glob("case_*_screened.csv"))
    if not screened_files:
        print("[ERROR] No screened CSV files found. Run 02_screening.py first.")
        return

    for screened_path in screened_files:
        parts   = screened_path.stem.split("_")
        case_id = int(parts[1])
        slug    = "_".join(parts[2:-1])  # remove trailing 'screened'
        out_path = EXTRACTED_DIR / f"case_{case_id:02d}_{slug}_extracted.csv"

        schema = SCHEMAS.get(case_id)
        if schema is None:
            print(f"[SKIP] No schema for case {case_id}")
            continue

        if out_path.exists():
            print(f"[SKIP] Case {case_id} already extracted: {out_path.name}")
            df_ext = pd.read_csv(out_path)
        else:
            print(f"\n[CASE {case_id:02d}] {slug}")
            df = pd.read_csv(screened_path)
            included = df[df["llm_decision"] == "INCLUDE"].copy().reset_index(drop=True)
            
            # Apply cap
            if len(included) > MAX_INCLUDE:
                print(f"  [CAP] Limiting {len(included)} included records to {MAX_INCLUDE}")
                included = included.head(MAX_INCLUDE)
            else:
                print(f"  Included records: {len(included)}")
                
            if included.empty:
                print("  [SKIP] No included records.")
                continue

            # Pass 1: Extract
            extracted_rows = []
            for _, row in tqdm(included.iterrows(), total=len(included),
                               desc=f"  Extracting case {case_id}"):
                ext = extract_record(str(row.get("title", "")),
                                     str(row.get("abstract", "")), schema)
                # Standardize keys to match schema exactly (GPT sometimes alters case)
                standardized_ext = {}
                for k in schema:
                    # Find case-insensitive match in GPT output
                    match = next((val for key, val in ext.items() if key.lower() == k.lower()), None)
                    standardized_ext[k] = match
                    
                standardized_ext["_title"] = row.get("title", "")
                standardized_ext["_doi"]   = row.get("doi", "")
                standardized_ext["_year"]  = row.get("year", "")
                extracted_rows.append(standardized_ext)
                time.sleep(0.1) # Safe sleep for rate limits

            df_ext = pd.DataFrame(extracted_rows)

            # Pass 2: Judge
            judge_rows = []
            for _, row in tqdm(df_ext.iterrows(), total=len(df_ext),
                               desc=f"  Judging case {case_id}"):
                ext_fields = {k: row.get(k) for k in schema}
                verdict = judge_record(str(row.get("_title", "")),
                                       str(included.loc[row.name, "abstract"] if row.name < len(included) else ""),
                                       ext_fields)
                
                # Standardize verdict keys
                standardized_verdict = {}
                for k in schema:
                    match = next((val for key, val in verdict.items() if key.lower() == k.lower()), "UNVERIFIABLE")
                    standardized_verdict[f"judge_{k}"] = match
                    
                judge_rows.append(standardized_verdict)
                time.sleep(0.1)

            df_judge = pd.DataFrame(judge_rows)
            df_ext = pd.concat([df_ext, df_judge], axis=1)
            df_ext.to_csv(out_path, index=False)
            print(f"  Saved: {out_path.name}")

        # Compute agreement metrics
        schema = SCHEMAS.get(case_id, {})
        metrics = compute_agreement(df_ext, schema)
        
        # Calculate summary metrics safely
        cat_fields = [k for k, v in schema.items() if v == "cat"]
        num_fields  = [k for k, v in schema.items() if v == "num"]
        
        cat_accuracies = [metrics.get(f"cat_accuracy_{f}") for f in cat_fields
                          if metrics.get(f"cat_accuracy_{f}") not in (None, "N/A")]
        mean_cat_acc = round(np.mean(cat_accuracies), 4) if cat_accuracies else "N/A"
        
        num_correct  = sum(metrics.get(f"num_n_correct_{f}", 0) for f in num_fields)
        num_incorrect= sum(metrics.get(f"num_n_incorrect_{f}", 0) for f in num_fields)
        num_total    = num_correct + num_incorrect
        num_accuracy = round(num_correct / num_total, 4) if num_total > 0 else "N/A"
        
        row = {"case_id": case_id, "slug": slug,
               "n_included": len(df_ext),
               "mean_cat_accuracy": mean_cat_acc,
               "num_field_accuracy": num_accuracy,
               **metrics}
        summary_rows.append(row)
        print(f"  Cat accuracy: {mean_cat_acc} | Num accuracy: {num_accuracy}")

    summary_df = pd.DataFrame(summary_rows)
    summary_path = OUTPUTS_DIR / "extraction_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"\nExtraction summary saved to {summary_path}")

if __name__ == "__main__":
    main()
