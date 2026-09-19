"""
compute_stats.py
Compute all summary statistics needed for manuscript2.tex from the
20-case empirical evaluation data.
"""
import pandas as pd
import numpy as np

# ── Load data ────────────────────────────────────────────────────────────────
retrieval = pd.read_csv("/home/ubuntu/repo_push/empirical_evaluation/outputs/retrieval_summary.csv")
screening = pd.read_csv("/home/ubuntu/repo_push/empirical_evaluation/outputs/screening_summary.csv")
extraction = pd.read_csv("/home/ubuntu/repo_push/empirical_evaluation/outputs/extraction_summary_corrected.csv")

# ── Domain mapping ────────────────────────────────────────────────────────────
domain_map = {
    1: "Health/Clinical", 2: "Health/Clinical", 3: "Health/Clinical",
    4: "CS/AI", 5: "Social/Behavioural", 6: "Social/Behavioural",
    7: "Social/Behavioural", 8: "Social/Behavioural", 9: "Education/Learning",
    10: "Education/Learning", 11: "Education/Learning", 12: "Education/Learning",
    13: "Environmental", 14: "Environmental", 15: "Environmental",
    16: "Environmental", 17: "CS/AI", 18: "CS/AI", 19: "CS/AI", 20: "CS/AI"
}
retrieval["domain"] = retrieval["case_id"].map(domain_map)
screening["domain"] = screening["case_id"].map(domain_map)
extraction["domain"] = extraction["case_id"].map(domain_map)

# ── RETRIEVAL STATS ───────────────────────────────────────────────────────────
print("=" * 60)
print("RETRIEVAL")
print("=" * 60)
print(f"Total raw records across all 20 cases: {retrieval['raw'].sum():,}")
print(f"Total after dedup: {retrieval['after_dedup'].sum():,}")
total_removed = retrieval['raw'].sum() - retrieval['after_dedup'].sum()
total_dup_pct = total_removed / retrieval['raw'].sum() * 100
print(f"Total duplicates removed: {total_removed:,} ({total_dup_pct:.1f}%)")
print(f"Mean abstract coverage: {retrieval['abstract_coverage'].mean():.4f}")
print(f"Min abstract coverage: {retrieval['abstract_coverage'].min():.4f} ({retrieval.loc[retrieval['abstract_coverage'].idxmin(), 'slug']})")
print(f"Max abstract coverage: {retrieval['abstract_coverage'].max():.4f}")

# DB breakdown
db_counts = retrieval.groupby("db").agg(
    n_cases=("case_id", "count"),
    total_raw=("raw", "sum"),
    total_dedup=("after_dedup", "sum"),
    mean_coverage=("abstract_coverage", "mean")
).reset_index()
print("\nBy database:")
print(db_counts.to_string(index=False))

# Domain breakdown
domain_ret = retrieval.groupby("domain").agg(
    n_cases=("case_id", "count"),
    total_raw=("raw", "sum"),
    total_dedup=("after_dedup", "sum"),
    mean_coverage=("abstract_coverage", "mean")
).reset_index()
print("\nBy domain:")
print(domain_ret.to_string(index=False))

# ── SCREENING STATS ───────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SCREENING")
print("=" * 60)
print(f"Total included by LLM screener: {screening['n_included_llm'].sum():,}")
print(f"Mean LLM recall: {screening['llm_recall'].mean():.4f}")
print(f"Mean LLM precision: {screening['llm_precision'].mean():.4f}")
print(f"Mean LLM F1: {screening['llm_f1'].mean():.4f}")
print(f"Mean AL recall: {screening['al_recall'].mean():.4f}")
print(f"Mean AL precision: {screening['al_precision'].mean():.4f}")
print(f"Mean AL F1: {screening['al_f1'].mean():.4f}")
print(f"Mean AL WSS@95: {screening['al_wss95'].mean():.4f}")
print(f"Max AL WSS@95: {screening['al_wss95'].max():.4f} ({screening.loc[screening['al_wss95'].idxmax(), 'slug']})")
print(f"Min AL WSS@95: {screening['al_wss95'].min():.4f} ({screening.loc[screening['al_wss95'].idxmin(), 'slug']})")

# Prevalence stats
print(f"\nMean prevalence: {screening['prevalence'].mean():.4f}")
print(f"Min prevalence: {screening['prevalence'].min():.4f} ({screening.loc[screening['prevalence'].idxmin(), 'slug']})")
print(f"Max prevalence: {screening['prevalence'].max():.4f} ({screening.loc[screening['prevalence'].idxmax(), 'slug']})")

# LLM recall = 1.0 analysis
n_perfect_recall = (screening['llm_recall'] == 1.0).sum()
print(f"\nCases with LLM recall = 1.0: {n_perfect_recall}/20")
print("Note: LLM screener used include-all-uncertain strategy, yielding recall=1.0 at cost of precision")

# Total human screening effort saved
total_corpus = screening['n_total'].sum()
total_screened_al = screening['al_n_screened'].sum()
pct_saved = (1 - total_screened_al / total_corpus) * 100
print(f"\nTotal corpus size: {total_corpus:,}")
print(f"Total screened by AL: {total_screened_al:,}")
print(f"Overall screening effort saved: {pct_saved:.1f}%")

# Domain-level screening
domain_scr = screening.groupby("domain").agg(
    mean_prevalence=("prevalence", "mean"),
    mean_llm_precision=("llm_precision", "mean"),
    mean_al_recall=("al_recall", "mean"),
    mean_al_wss95=("al_wss95", "mean")
).reset_index()
print("\nBy domain:")
print(domain_scr.to_string(index=False))

# ── EXTRACTION STATS ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("EXTRACTION")
print("=" * 60)
print(f"Total records extracted (after cap): {extraction['n_records'].sum():,}")
print(f"Mean categorical accuracy: {extraction['mean_cat_accuracy'].mean():.4f}")
print(f"Std categorical accuracy: {extraction['mean_cat_accuracy'].std():.4f}")
print(f"Min categorical accuracy: {extraction['mean_cat_accuracy'].min():.4f} ({extraction.loc[extraction['mean_cat_accuracy'].idxmin(), 'slug']})")
print(f"Mean numeric accuracy: {extraction['mean_num_accuracy'].mean():.4f}")
print(f"Std numeric accuracy: {extraction['mean_num_accuracy'].std():.4f}")
print(f"Min numeric accuracy: {extraction['mean_num_accuracy'].min():.4f} ({extraction.loc[extraction['mean_num_accuracy'].idxmin(), 'slug']})")

# Cases with num accuracy < 0.90
low_num = extraction[extraction['mean_num_accuracy'] < 0.90]
print(f"\nCases with numeric accuracy < 0.90:")
print(low_num[['slug', 'mean_num_accuracy']].to_string(index=False))

# Domain-level extraction
domain_ext = extraction.groupby("domain").agg(
    n_cases=("case_id", "count"),
    total_records=("n_records", "sum"),
    mean_cat_acc=("mean_cat_accuracy", "mean"),
    mean_num_acc=("mean_num_accuracy", "mean")
).reset_index()
print("\nBy domain:")
print(domain_ext.to_string(index=False))

# ── PER-CASE SUMMARY TABLE (for LaTeX) ───────────────────────────────────────
print("\n" + "=" * 60)
print("PER-CASE SUMMARY (for LaTeX tables)")
print("=" * 60)
merged = screening[['case_id', 'slug', 'domain', 'n_total', 'n_included_llm',
                     'prevalence', 'al_recall', 'al_wss95']].merge(
    extraction[['case_id', 'n_records', 'mean_cat_accuracy', 'mean_num_accuracy']],
    on='case_id'
)
merged = merged.merge(retrieval[['case_id', 'db', 'abstract_coverage']], on='case_id')
print(merged.to_string(index=False))

# Save for figure generation
merged.to_csv("/home/ubuntu/case_summary.csv", index=False)
print("\nSaved to /home/ubuntu/case_summary.csv")
