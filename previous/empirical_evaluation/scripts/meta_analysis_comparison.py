"""
meta_analysis_comparison.py
============================
Issue 2 — Error Propagation: Actual Meta-Analysis Comparison

Compares pooled effect sizes and I² statistics across three extraction scenarios:
  (A) "True" extraction: AI-extracted values accepted as ground truth
      (only records with CORRECT judge verdicts on all numeric fields)
  (B) "Low-error" simulation: 7% of sample sizes halved (observed error rate)
  (C) "High-error" simulation: 20% of sample sizes halved (pessimistic scenario)

Uses Case 3 (GLP-1 cardiovascular, HR + CI, k=257 studies) as the primary
demonstration case — the largest and most complete extraction in the dataset.

The scientific message: even moderate extraction error rates distort I²
and shift pooled estimates, with effects that scale with error prevalence.

Outputs:
  - fig_meta_analysis_comparison.pdf  (manuscript-quality figure)
  - fig_meta_analysis_comparison.png  (quick-view copy)
  - meta_analysis_results.csv          (numeric results table for manuscript)

Author: Moses Boudourides, Northwestern University
Date: June 2025
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import os

np.random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
UPLOAD_DIR = "/home/ubuntu/upload"
OUT_DIR    = "/home/ubuntu/repo_push/empirical_evaluation/figures"
os.makedirs(OUT_DIR, exist_ok=True)

# ── DerSimonian–Laird random-effects meta-analysis ─────────────────────────────
def dsl_meta(log_es, se):
    """
    DerSimonian–Laird random-effects pooled estimate.
    Returns: (pooled_log_es, pooled_se, tau2, I2, Q, df)
    """
    w_fixed = 1.0 / se**2
    Q = float(np.sum(w_fixed * (log_es - np.average(log_es, weights=w_fixed))**2))
    k = len(log_es)
    df = k - 1
    c = float(np.sum(w_fixed) - np.sum(w_fixed**2) / np.sum(w_fixed))
    tau2 = max(0.0, (Q - df) / c)

    w_re = 1.0 / (se**2 + tau2)
    pooled_log = float(np.sum(w_re * log_es) / np.sum(w_re))
    pooled_se  = float(np.sqrt(1.0 / np.sum(w_re)))

    v_bar = float(np.mean(se**2))
    I2 = max(0.0, (tau2 / (tau2 + v_bar)) * 100)
    return pooled_log, pooled_se, tau2, I2, Q, df


def ci95(pooled_log, pooled_se):
    z = 1.96
    return np.exp(pooled_log - z * pooled_se), np.exp(pooled_log + z * pooled_se)


def perturb_se(se_array, error_rate):
    """Halve sample sizes for error_rate fraction of studies → SE * sqrt(2)."""
    se_out = se_array.copy()
    n_perturb = max(1, int(round(error_rate * len(se_out))))
    idx = np.random.choice(len(se_out), size=n_perturb, replace=False)
    se_out[idx] *= np.sqrt(2)
    return se_out, n_perturb, idx


# ══════════════════════════════════════════════════════════════════════════════
# CASE 3 — GLP-1 Cardiovascular (Hazard Ratios)
# ══════════════════════════════════════════════════════════════════════════════
df3 = pd.read_csv(os.path.join(UPLOAD_DIR, "case_03_glp1_cardiovascular_extracted.csv"))

keep3 = (
    df3["hazard_ratio"].notna() &
    df3["ci_lower"].notna() &
    df3["ci_upper"].notna() &
    df3["sample_size"].notna() &
    (df3["judge_hazard_ratio"] == "CORRECT") &
    (df3["judge_ci_lower"]    == "CORRECT") &
    (df3["judge_ci_upper"]    == "CORRECT") &
    (df3["judge_sample_size"] == "CORRECT") &
    (df3["hazard_ratio"] > 0) &
    (df3["ci_lower"] > 0) &
    (df3["ci_upper"] > 0)
).values

sub3 = df3[keep3].copy().reset_index(drop=True)
sub3["log_hr"]  = np.log(sub3["hazard_ratio"].values)
sub3["log_lo"]  = np.log(sub3["ci_lower"].values)
sub3["log_hi"]  = np.log(sub3["ci_upper"].values)
sub3["se_true"] = (sub3["log_hi"] - sub3["log_lo"]) / (2 * 1.96)
sub3 = sub3[sub3["se_true"] > 0].reset_index(drop=True)
k3 = len(sub3)
print(f"Case 3: k = {k3} complete records")

# Three scenarios
se_true = sub3["se_true"].values.copy()
res_A = dsl_meta(sub3["log_hr"].values, se_true)
ci_A  = ci95(res_A[0], res_A[1])

se_B, n_B, _ = perturb_se(se_true, 0.07)
res_B = dsl_meta(sub3["log_hr"].values, se_B)
ci_B  = ci95(res_B[0], res_B[1])

se_C, n_C, _ = perturb_se(se_true, 0.20)
res_C = dsl_meta(sub3["log_hr"].values, se_C)
ci_C  = ci95(res_C[0], res_C[1])

print(f"\nScenario A (True):       HR={np.exp(res_A[0]):.3f} [{ci_A[0]:.3f},{ci_A[1]:.3f}]  I²={res_A[3]:.1f}%  tau²={res_A[2]:.4f}")
print(f"Scenario B (7% error):   HR={np.exp(res_B[0]):.3f} [{ci_B[0]:.3f},{ci_B[1]:.3f}]  I²={res_B[3]:.1f}%  tau²={res_B[2]:.4f}")
print(f"Scenario C (20% error):  HR={np.exp(res_C[0]):.3f} [{ci_C[0]:.3f},{ci_C[1]:.3f}]  I²={res_C[3]:.1f}%  tau²={res_C[2]:.4f}")


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS TABLE
# ══════════════════════════════════════════════════════════════════════════════
rows = [
    {"Scenario": "A — True extraction (AI-verified)",
     "k": k3, "Perturbed studies": 0,
     "Pooled HR": round(np.exp(res_A[0]), 3),
     "CI lower": round(ci_A[0], 3), "CI upper": round(ci_A[1], 3),
     "I2_pct": round(res_A[3], 1), "tau2": round(res_A[2], 4)},
    {"Scenario": "B — Low-error simulation (7% SE inflation)",
     "k": k3, "Perturbed studies": n_B,
     "Pooled HR": round(np.exp(res_B[0]), 3),
     "CI lower": round(ci_B[0], 3), "CI upper": round(ci_B[1], 3),
     "I2_pct": round(res_B[3], 1), "tau2": round(res_B[2], 4)},
    {"Scenario": "C — High-error simulation (20% SE inflation)",
     "k": k3, "Perturbed studies": n_C,
     "Pooled HR": round(np.exp(res_C[0]), 3),
     "CI lower": round(ci_C[0], 3), "CI upper": round(ci_C[1], 3),
     "I2_pct": round(res_C[3], 1), "tau2": round(res_C[2], 4)},
]
results_df = pd.DataFrame(rows)
results_df.to_csv("/home/ubuntu/meta_analysis_results.csv", index=False)
print("\nResults table saved.")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE
# ══════════════════════════════════════════════════════════════════════════════
COLORS = {
    "A": "#2166ac",   # blue
    "B": "#f4a582",   # orange
    "C": "#d6604d",   # red
    "grid": "#eeeeee",
    "text": "#222222",
}

# Sample a representative subset for the forest plot (too many to show all 257)
SHOW_N = 40
step = max(1, k3 // SHOW_N)
show_idx = list(range(0, k3, step))[:SHOW_N]
sub_show = sub3.iloc[show_idx].reset_index(drop=True)
k_show = len(sub_show)

fig = plt.figure(figsize=(14, 9))
fig.patch.set_facecolor("white")
gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[2.2, 1],
                       wspace=0.38)

ax_f = fig.add_subplot(gs[0, 0])
ax_b = fig.add_subplot(gs[0, 1])

# ── Forest panel ──────────────────────────────────────────────────────────────
y_pos = np.arange(k_show, 0, -1, dtype=float)

for i, row in sub_show.iterrows():
    y = y_pos[i]
    lo = np.exp(row["log_hr"] - 1.96 * row["se_true"])
    hi = np.exp(row["log_hr"] + 1.96 * row["se_true"])
    es = np.exp(row["log_hr"])
    ax_f.plot([lo, hi], [y, y], color=COLORS["A"], lw=0.9, alpha=0.45)
    ax_f.scatter([es], [y], color=COLORS["A"], s=22, zorder=3, alpha=0.65)

# Separator line
ax_f.axhline(0.0, color="#bbbbbb", lw=0.8, ls=":")

# Pooled diamonds for all three scenarios
def draw_diamond(ax, x_center, x_lo, x_hi, y, color, lw=1.5):
    half_h = 0.55
    dx = [x_lo, x_center, x_hi, x_center, x_lo]
    dy = [y, y + half_h, y, y - half_h, y]
    ax.fill(dx, dy, color=color, alpha=0.88, zorder=5)
    ax.plot(dx, dy, color=color, lw=lw, zorder=6)

y_A = -1.8
y_B = -3.2
y_C = -4.6

draw_diamond(ax_f, np.exp(res_A[0]), ci_A[0], ci_A[1], y_A, COLORS["A"])
draw_diamond(ax_f, np.exp(res_B[0]), ci_B[0], ci_B[1], y_B, COLORS["B"])
draw_diamond(ax_f, np.exp(res_C[0]), ci_C[0], ci_C[1], y_C, COLORS["C"])

# Labels right of diamonds
def fmt_label(res, ci, label):
    return f"{label}  HR={np.exp(res[0]):.3f} [{ci[0]:.3f}-{ci[1]:.3f}]  I\u00b2={res[3]:.1f}%"

ax_f.text(0.62, y_A, fmt_label(res_A, ci_A, "A"), va="center", ha="left",
          fontsize=8.2, color=COLORS["A"], fontweight="bold",
          transform=ax_f.get_yaxis_transform())
ax_f.text(0.62, y_B, fmt_label(res_B, ci_B, "B"), va="center", ha="left",
          fontsize=8.2, color=COLORS["B"], fontweight="bold",
          transform=ax_f.get_yaxis_transform())
ax_f.text(0.62, y_C, fmt_label(res_C, ci_C, "C"), va="center", ha="left",
          fontsize=8.2, color=COLORS["C"], fontweight="bold",
          transform=ax_f.get_yaxis_transform())

ax_f.axvline(1.0, color="#777777", lw=0.9, ls="--", zorder=1)
ax_f.set_xscale("log")
ax_f.set_yticks([])
ax_f.set_xlabel("Hazard Ratio (log scale)", fontsize=10.5)
ax_f.set_title(
    f"Case 3: GLP-1 Cardiovascular Outcomes\n"
    f"(k={k3} studies; {k_show} shown for clarity)",
    fontsize=11, fontweight="bold", pad=7)
ax_f.set_ylim(y_C - 1.2, k_show + 1)
ax_f.spines[["top", "right"]].set_visible(False)

# Annotation box
delta_B = res_B[3] - res_A[3]
delta_C = res_C[3] - res_A[3]
textstr = (
    f"k = {k3} studies\n"
    f"Scenario B: {n_B} perturbed ({n_B/k3*100:.0f}%)\n"
    f"  DeltaI2 = {delta_B:+.1f} pp\n"
    f"Scenario C: {n_C} perturbed ({n_C/k3*100:.0f}%)\n"
    f"  DeltaI2 = {delta_C:+.1f} pp"
)
ax_f.text(0.02, 0.03, textstr, transform=ax_f.transAxes,
          fontsize=8, va="bottom", ha="left",
          bbox=dict(boxstyle="round,pad=0.45", fc="#f7f7f7", ec="#cccccc", lw=0.8))

# ── I² and tau² bar panel ─────────────────────────────────────────────────────
labels  = ["A\nTrue", "B\n7% error", "C\n20% error"]
i2_vals = [res_A[3], res_B[3], res_C[3]]
t2_vals = [res_A[2], res_B[2], res_C[2]]
bar_colors = [COLORS["A"], COLORS["B"], COLORS["C"]]

x = np.array([0, 1, 2])
width = 0.35

ax_b2 = ax_b.twinx()

bars1 = ax_b.bar(x - width/2, i2_vals, width, color=bar_colors,
                 alpha=0.85, label="I² (%)", edgecolor="white", linewidth=1.2)
bars2 = ax_b2.bar(x + width/2, t2_vals, width, color=bar_colors,
                  alpha=0.45, hatch="///", label="tau² ", edgecolor="white", linewidth=1.2)

for bar, val in zip(bars1, i2_vals):
    ax_b.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
              f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold",
              color=COLORS["text"])

for bar, val in zip(bars2, t2_vals):
    ax_b2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
               f"{val:.3f}", ha="center", va="bottom", fontsize=8.5, color="#555555")

for thresh, lbl in [(25, "Low"), (50, "Moderate"), (75, "High")]:
    ax_b.axhline(thresh, color="#aaaaaa", lw=0.7, ls="--")
    ax_b.text(2.52, thresh, lbl, va="center", fontsize=7.5, color="#888888")

ax_b.set_xticks(x)
ax_b.set_xticklabels(labels, fontsize=9.5)
ax_b.set_ylabel("I² (%)", fontsize=10.5)
ax_b2.set_ylabel("tau² (between-study variance)", fontsize=9, color="#666666")
ax_b.set_ylim(0, 105)
ax_b2.set_ylim(0, max(t2_vals) * 1.6)
ax_b.set_title("Heterogeneity by Scenario", fontsize=11, fontweight="bold", pad=7)
ax_b.spines[["top"]].set_visible(False)
ax_b2.spines[["top"]].set_visible(False)

# Combined legend
patch_i2  = mpatches.Patch(color="#888888", alpha=0.85, label="I² (solid bars, left axis)")
patch_tau = mpatches.Patch(color="#888888", alpha=0.45, hatch="///", label="tau² (hatched bars, right axis)")
ax_b.legend(handles=[patch_i2, patch_tau], fontsize=8, loc="upper left", frameon=True)

# ── Figure-level legend ───────────────────────────────────────────────────────
legend_patches = [
    mpatches.Patch(color=COLORS["A"], label="A: True extraction (AI-verified, CORRECT verdicts only)"),
    mpatches.Patch(color=COLORS["B"], label="B: Low-error simulation (7% SE inflation, observed rate)"),
    mpatches.Patch(color=COLORS["C"], label="C: High-error simulation (20% SE inflation, pessimistic)"),
]
fig.legend(handles=legend_patches, loc="lower center", ncol=3,
           fontsize=8.5, frameon=True, framealpha=0.95,
           bbox_to_anchor=(0.5, 0.005))

fig.suptitle(
    "True vs. AI-Error Meta-Analysis: Pooled Effect Size and Heterogeneity\n"
    "(DerSimonian-Laird Random-Effects; SE inflation via sample-size halving)",
    fontsize=12, fontweight="bold", y=1.01
)

out_pdf = os.path.join(OUT_DIR, "fig_meta_analysis_comparison.pdf")
out_png = os.path.join(OUT_DIR, "fig_meta_analysis_comparison.png")
fig.savefig(out_pdf, bbox_inches="tight", dpi=300)
fig.savefig(out_png, bbox_inches="tight", dpi=150)
plt.close(fig)
print(f"Figure saved: {out_pdf}")
print(f"PNG saved:    {out_png}")
print("\nDone.")
