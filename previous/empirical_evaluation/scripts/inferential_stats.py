"""
inferential_stats.py
=====================
Issue 3 — Inferential Statistics for the AI-Assisted Systematic Review Pipeline

Computes and reports:
  1. 95% confidence intervals for WSS@95 and extraction accuracy metrics
     (per case and per domain), using Wilson score intervals for proportions
     and bootstrap CIs for means
  2. Domain-level comparisons of WSS@95 and numeric accuracy
     (Kruskal-Wallis H-test; post-hoc Mann-Whitney U with Bonferroni correction)
  3. Spearman correlation between retrieval volume and WSS@95
  4. Multiple linear regression explaining WSS@95 by domain, prevalence,
     and corpus size

Outputs:
  - fig_inferential_stats.pdf / .png   (4-panel figure)
  - inferential_stats_results.csv       (full numeric results)

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
from scipy import stats
from scipy.stats import kruskal, mannwhitneyu, spearmanr
import os, itertools, warnings
warnings.filterwarnings("ignore")

np.random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
OUT_DIR = "/home/ubuntu/repo_push/empirical_evaluation/figures"
os.makedirs(OUT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# DATA — from manuscript tables (screening_summary + extraction_summary)
# ══════════════════════════════════════════════════════════════════════════════
data = pd.DataFrame({
    "case_id": list(range(1, 21)),
    "slug": [
        "nurse_staffing_mortality", "mindfulness_anxiety", "glp1_cardiovascular",
        "ai_radiology_diagnosis", "cash_transfers_education", "social_media_mental_health",
        "restorative_justice_recidivism", "gender_pay_gap", "intelligent_tutoring_scores",
        "game_based_learning_motivation", "class_size_achievement", "llm_higher_education",
        "marine_protected_areas", "reforestation_carbon", "indoor_air_pollution_health",
        "microplastics_freshwater", "llm_reasoning_benchmarks", "federated_learning_privacy",
        "ai_ethics_autonomous_systems", "deep_learning_predictive_maintenance",
    ],
    "domain": [
        "Health/Clinical", "Health/Clinical", "Health/Clinical",
        "CS/AI", "Social/Behavioural", "Social/Behavioural",
        "Social/Behavioural", "Social/Behavioural", "Education/Learning",
        "Education/Learning", "Education/Learning", "Education/Learning",
        "Environmental", "Environmental", "Environmental",
        "Environmental", "CS/AI", "CS/AI",
        "CS/AI", "CS/AI",
    ],
    "corpus_size": [
        90, 2803, 5945, 9929, 4447, 3968, 4102, 7708, 3962, 993,
        4923, 8633, 3929, 3960, 5888, 7061, 999, 4886, 375, 9921,
    ],
    "prevalence_pct": [
        24.4, 2.6, 14.2, 24.6, 10.6, 14.7, 1.9, 4.0, 14.6, 35.7,
        5.1, 19.9, 8.7, 27.4, 22.9, 24.0, 39.4, 53.3, 83.7, 38.0,
    ],
    "wss95": [
        72.8, 10.5, 28.3, 53.6, 35.0, 30.5, 23.1, 7.8, 28.3, 52.7,
        8.2, 71.3, 32.5, 52.4, 47.4, 56.4, 56.3, 29.0, 11.5, 36.3,
    ],
    "al_recall": [
        1.000, 0.958, 0.950, 0.950, 0.951, 0.954, 0.961, 0.951, 0.952, 0.952,
        0.953, 0.950, 0.950, 0.950, 0.950, 0.952, 0.952, 0.951, 0.962, 0.950,
    ],
    "n_records": [
        22, 72, 841, 2444, 469, 584, 77, 308, 580, 354,
        253, 1720, 340, 1086, 1350, 200, 200, 200, 200, 200,
    ],
    "cat_acc": [
        96.85, 100.00, 99.12, 99.26, 99.49, 98.90, 98.96, 98.41, 99.55, 99.17,
        97.87, 99.43, 98.42, 99.17, 99.09, 100.00, 99.13, 99.42, 99.38, 99.87,
    ],
    "num_acc": [
        97.22, 97.96, 96.63, 94.17, 98.04, 99.03, 99.11, 95.40, 99.40, 86.47,
        78.99, 98.55, 97.67, 97.75, 98.85, 84.79, 84.94, 96.97, 100.00, 87.66,
    ],
})

DOMAIN_ORDER = ["Health/Clinical", "Social/Behavioural", "Education/Learning",
                "Environmental", "CS/AI"]
DOMAIN_COLORS = {
    "Health/Clinical":    "#2166ac",
    "Social/Behavioural": "#4dac26",
    "Education/Learning": "#d01c8b",
    "Environmental":      "#f1a340",
    "CS/AI":              "#998ec3",
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONFIDENCE INTERVALS
# ══════════════════════════════════════════════════════════════════════════════

def wilson_ci(p_pct, n, z=1.96):
    """Wilson score interval for a proportion given as percentage."""
    p = p_pct / 100.0
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2*n)) / denom
    half   = (z * np.sqrt(p*(1-p)/n + z**2/(4*n**2))) / denom
    return max(0, (centre - half)*100), min(100, (centre + half)*100)


def bootstrap_mean_ci(values, n_boot=5000, ci=95):
    """Bootstrap CI for the mean of a small sample."""
    boots = [np.mean(np.random.choice(values, size=len(values), replace=True))
             for _ in range(n_boot)]
    lo = np.percentile(boots, (100 - ci) / 2)
    hi = np.percentile(boots, 100 - (100 - ci) / 2)
    return lo, hi


# Per-case Wilson CIs for cat_acc and num_acc
ci_rows = []
for _, row in data.iterrows():
    n = int(row["n_records"])
    cat_lo, cat_hi = wilson_ci(row["cat_acc"], n)
    num_lo, num_hi = wilson_ci(row["num_acc"], n)
    ci_rows.append({
        "case_id": row["case_id"], "slug": row["slug"], "domain": row["domain"],
        "cat_acc": row["cat_acc"], "cat_ci_lo": cat_lo, "cat_ci_hi": cat_hi,
        "num_acc": row["num_acc"], "num_ci_lo": num_lo, "num_ci_hi": num_hi,
        "wss95": row["wss95"],
    })
ci_df = pd.DataFrame(ci_rows)

# Domain-level bootstrap CIs
domain_ci = {}
for dom in DOMAIN_ORDER:
    sub = data[data["domain"] == dom]
    wss_lo, wss_hi = bootstrap_mean_ci(sub["wss95"].values)
    cat_lo, cat_hi = bootstrap_mean_ci(sub["cat_acc"].values)
    num_lo, num_hi = bootstrap_mean_ci(sub["num_acc"].values)
    domain_ci[dom] = {
        "n": len(sub),
        "mean_wss": sub["wss95"].mean(),
        "wss_lo": wss_lo, "wss_hi": wss_hi,
        "mean_cat": sub["cat_acc"].mean(),
        "cat_lo": cat_lo, "cat_hi": cat_hi,
        "mean_num": sub["num_acc"].mean(),
        "num_lo": num_lo, "num_hi": num_hi,
    }

print("Domain-level statistics:")
for dom, d in domain_ci.items():
    print(f"  {dom:25s}  WSS@95={d['mean_wss']:.1f}% [{d['wss_lo']:.1f},{d['wss_hi']:.1f}]  "
          f"NumAcc={d['mean_num']:.1f}% [{d['num_lo']:.1f},{d['num_hi']:.1f}]")


# ══════════════════════════════════════════════════════════════════════════════
# 2. DOMAIN COMPARISONS — Kruskal-Wallis + post-hoc Mann-Whitney
# ══════════════════════════════════════════════════════════════════════════════

domain_groups_wss = [data[data["domain"]==d]["wss95"].values for d in DOMAIN_ORDER]
domain_groups_num = [data[data["domain"]==d]["num_acc"].values for d in DOMAIN_ORDER]

kw_wss = kruskal(*domain_groups_wss)
kw_num = kruskal(*domain_groups_num)
print(f"\nKruskal-Wallis WSS@95:   H={kw_wss.statistic:.3f}, p={kw_wss.pvalue:.4f}")
print(f"Kruskal-Wallis NumAcc:   H={kw_num.statistic:.3f}, p={kw_num.pvalue:.4f}")

# Post-hoc pairwise Mann-Whitney (Bonferroni correction)
pairs = list(itertools.combinations(range(len(DOMAIN_ORDER)), 2))
n_pairs = len(pairs)
posthoc_wss = []
for i, j in pairs:
    u, p = mannwhitneyu(domain_groups_wss[i], domain_groups_wss[j],
                        alternative="two-sided")
    posthoc_wss.append({
        "domain_1": DOMAIN_ORDER[i], "domain_2": DOMAIN_ORDER[j],
        "U": round(u, 1), "p_raw": round(p, 4),
        "p_bonferroni": round(min(1.0, p * n_pairs), 4),
    })
posthoc_df = pd.DataFrame(posthoc_wss)
print("\nPost-hoc pairwise WSS@95 (Bonferroni):")
print(posthoc_df.to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# 3. CORRELATION — corpus size vs WSS@95
# ══════════════════════════════════════════════════════════════════════════════

rho_size, p_size = spearmanr(data["corpus_size"], data["wss95"])
rho_prev, p_prev = spearmanr(data["prevalence_pct"], data["wss95"])
rho_num,  p_num  = spearmanr(data["num_acc"], data["wss95"])
print(f"\nSpearman rho (corpus_size vs WSS@95):   rho={rho_size:.3f}, p={p_size:.4f}")
print(f"Spearman rho (prevalence   vs WSS@95):   rho={rho_prev:.3f}, p={p_prev:.4f}")
print(f"Spearman rho (num_acc      vs WSS@95):   rho={rho_num:.3f},  p={p_num:.4f}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. REGRESSION — WSS@95 ~ prevalence + log(corpus_size) + domain dummies
# ══════════════════════════════════════════════════════════════════════════════
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# Build design matrix
X = data[["prevalence_pct", "corpus_size"]].copy()
X["log_corpus"] = np.log(X["corpus_size"])
X = X.drop(columns=["corpus_size"])

# Domain dummies (drop Health/Clinical as reference)
for dom in DOMAIN_ORDER[1:]:
    X[dom.replace("/", "_").replace(" ", "_")] = (data["domain"] == dom).astype(float)

y = data["wss95"].values
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

reg = LinearRegression().fit(X_scaled, y)
y_pred = reg.predict(X_scaled)
ss_res = np.sum((y - y_pred)**2)
ss_tot = np.sum((y - y.mean())**2)
r2 = 1 - ss_res / ss_tot

# Bootstrap CIs for coefficients
n_boot = 2000
coef_boots = np.zeros((n_boot, X_scaled.shape[1]))
for b in range(n_boot):
    idx = np.random.choice(len(y), size=len(y), replace=True)
    coef_boots[b] = LinearRegression().fit(X_scaled[idx], y[idx]).coef_

coef_ci_lo = np.percentile(coef_boots, 2.5, axis=0)
coef_ci_hi = np.percentile(coef_boots, 97.5, axis=0)

print(f"\nRegression R² = {r2:.3f}")
print("Coefficients (standardized):")
feature_names = list(X.columns)
for name, coef, lo, hi in zip(feature_names, reg.coef_, coef_ci_lo, coef_ci_hi):
    print(f"  {name:35s}  beta={coef:+.3f}  95%CI=[{lo:+.3f}, {hi:+.3f}]")


# ══════════════════════════════════════════════════════════════════════════════
# SAVE RESULTS CSV
# ══════════════════════════════════════════════════════════════════════════════
results_out = {
    "kw_wss_H": kw_wss.statistic, "kw_wss_p": kw_wss.pvalue,
    "kw_num_H": kw_num.statistic, "kw_num_p": kw_num.pvalue,
    "spearman_size_rho": rho_size, "spearman_size_p": p_size,
    "spearman_prev_rho": rho_prev, "spearman_prev_p": p_prev,
    "spearman_num_rho": rho_num,   "spearman_num_p": p_num,
    "regression_R2": r2,
}
pd.DataFrame([results_out]).to_csv("/home/ubuntu/inferential_stats_results.csv", index=False)
ci_df.to_csv("/home/ubuntu/per_case_ci.csv", index=False)
posthoc_df.to_csv("/home/ubuntu/posthoc_wss.csv", index=False)
print("\nResults CSVs saved.")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE — 4 panels
# ══════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(15, 11))
fig.patch.set_facecolor("white")
gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.48, wspace=0.38)

ax1 = fig.add_subplot(gs[0, 0])  # Domain WSS@95 with CIs
ax2 = fig.add_subplot(gs[0, 1])  # Domain NumAcc with CIs
ax3 = fig.add_subplot(gs[1, 0])  # Prevalence vs WSS@95 scatter
ax4 = fig.add_subplot(gs[1, 1])  # Regression coefficients

COLORS_D = [DOMAIN_COLORS[d] for d in DOMAIN_ORDER]

# ── Panel 1: Domain WSS@95 ────────────────────────────────────────────────────
means_wss = [domain_ci[d]["mean_wss"] for d in DOMAIN_ORDER]
lo_wss    = [domain_ci[d]["wss_lo"]   for d in DOMAIN_ORDER]
hi_wss    = [domain_ci[d]["wss_hi"]   for d in DOMAIN_ORDER]
err_lo    = [m - l for m, l in zip(means_wss, lo_wss)]
err_hi    = [h - m for m, h in zip(means_wss, hi_wss)]

x = np.arange(len(DOMAIN_ORDER))
bars = ax1.bar(x, means_wss, color=COLORS_D, width=0.55,
               edgecolor="white", linewidth=1.2, alpha=0.88)
ax1.errorbar(x, means_wss, yerr=[err_lo, err_hi],
             fmt="none", color="#333333", capsize=5, lw=1.5, capthick=1.5)
for bar, val in zip(bars, means_wss):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
             f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

ax1.set_xticks(x)
ax1.set_xticklabels([d.replace("/", "/\n") for d in DOMAIN_ORDER], fontsize=8.5)
ax1.set_ylabel("Mean WSS@95 (%)", fontsize=10)
ax1.set_ylim(0, 75)
ax1.set_title("(a) Domain-Level WSS@95\n(mean ± 95% bootstrap CI)", fontsize=10.5, fontweight="bold")
ax1.spines[["top", "right"]].set_visible(False)

# KW annotation
ax1.text(0.98, 0.97, f"Kruskal-Wallis\nH={kw_wss.statistic:.2f}, p={kw_wss.pvalue:.3f}",
         transform=ax1.transAxes, ha="right", va="top", fontsize=8.5,
         bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#cccccc"))

# ── Panel 2: Domain Numeric Accuracy ─────────────────────────────────────────
means_num = [domain_ci[d]["mean_num"] for d in DOMAIN_ORDER]
lo_num    = [domain_ci[d]["num_lo"]   for d in DOMAIN_ORDER]
hi_num    = [domain_ci[d]["num_hi"]   for d in DOMAIN_ORDER]
err_lo_n  = [m - l for m, l in zip(means_num, lo_num)]
err_hi_n  = [h - m for m, h in zip(means_num, hi_num)]

bars2 = ax2.bar(x, means_num, color=COLORS_D, width=0.55,
                edgecolor="white", linewidth=1.2, alpha=0.88)
ax2.errorbar(x, means_num, yerr=[err_lo_n, err_hi_n],
             fmt="none", color="#333333", capsize=5, lw=1.5, capthick=1.5)
for bar, val in zip(bars2, means_num):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
             f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

ax2.set_xticks(x)
ax2.set_xticklabels([d.replace("/", "/\n") for d in DOMAIN_ORDER], fontsize=8.5)
ax2.set_ylabel("Mean Numeric Accuracy (%)", fontsize=10)
ax2.set_ylim(75, 105)
ax2.set_title("(b) Domain-Level Numeric Accuracy\n(mean ± 95% bootstrap CI)", fontsize=10.5, fontweight="bold")
ax2.spines[["top", "right"]].set_visible(False)

ax2.text(0.98, 0.97, f"Kruskal-Wallis\nH={kw_num.statistic:.2f}, p={kw_num.pvalue:.3f}",
         transform=ax2.transAxes, ha="right", va="top", fontsize=8.5,
         bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#cccccc"))

# ── Panel 3: Prevalence vs WSS@95 scatter ────────────────────────────────────
for _, row in data.iterrows():
    ax3.scatter(row["prevalence_pct"], row["wss95"],
                color=DOMAIN_COLORS[row["domain"]], s=60, alpha=0.85, zorder=3,
                edgecolors="white", linewidths=0.5)

# Regression line
x_fit = np.linspace(data["prevalence_pct"].min() - 2, data["prevalence_pct"].max() + 2, 100)
slope, intercept, r_val, p_val, se_val = stats.linregress(data["prevalence_pct"], data["wss95"])
ax3.plot(x_fit, slope * x_fit + intercept, color="#555555", lw=1.5, ls="--", zorder=2)

ax3.set_xlabel("Corpus Prevalence (%)", fontsize=10)
ax3.set_ylabel("WSS@95 (%)", fontsize=10)
ax3.set_title(f"(c) Prevalence vs. WSS@95\n"
              f"Spearman rho={rho_prev:.3f}, p={p_prev:.3f}  |  "
              f"OLS R={r_val:.2f}, p={p_val:.3f}",
              fontsize=10.5, fontweight="bold")
ax3.spines[["top", "right"]].set_visible(False)

# Domain legend
legend_patches = [mpatches.Patch(color=DOMAIN_COLORS[d], label=d) for d in DOMAIN_ORDER]
ax3.legend(handles=legend_patches, fontsize=7.5, loc="upper right",
           frameon=True, framealpha=0.9)

# ── Panel 4: Regression coefficients ─────────────────────────────────────────
feat_labels = {
    "prevalence_pct":          "Prevalence (%)",
    "log_corpus":              "log(Corpus size)",
    "Social_Behavioural":      "Domain: Social/Behav.",
    "Education_Learning":      "Domain: Education",
    "Environmental":           "Domain: Environmental",
    "CS_AI":                   "Domain: CS/AI",
}
coef_colors = ["#888888" if c >= 0 else "#d6604d" for c in reg.coef_]
coef_colors_pos = ["#2166ac" if c >= 0 else "#d6604d" for c in reg.coef_]

y_pos = np.arange(len(feature_names))
labels_clean = [feat_labels.get(f, f) for f in feature_names]

ax4.barh(y_pos, reg.coef_, xerr=[reg.coef_ - coef_ci_lo, coef_ci_hi - reg.coef_],
         color=coef_colors_pos, alpha=0.82, height=0.55,
         error_kw=dict(ecolor="#333333", capsize=4, lw=1.3, capthick=1.3),
         edgecolor="white", linewidth=1.0)
ax4.axvline(0, color="#555555", lw=1.0, ls="-")
ax4.set_yticks(y_pos)
ax4.set_yticklabels(labels_clean, fontsize=9)
ax4.set_xlabel("Standardized Regression Coefficient (beta)", fontsize=10)
ax4.set_title(f"(d) Regression: WSS@95 ~ Prevalence + log(Size) + Domain\n"
              f"R\u00b2 = {r2:.3f}  (reference domain: Health/Clinical)",
              fontsize=10.5, fontweight="bold")
ax4.spines[["top", "right"]].set_visible(False)

fig.suptitle(
    "Inferential Statistics: Domain Comparisons, Correlations, and Regression for WSS@95",
    fontsize=13, fontweight="bold", y=1.01
)

out_pdf = os.path.join(OUT_DIR, "fig_inferential_stats.pdf")
out_png = os.path.join(OUT_DIR, "fig_inferential_stats.png")
fig.savefig(out_pdf, bbox_inches="tight", dpi=300)
fig.savefig(out_png, bbox_inches="tight", dpi=150)
plt.close(fig)
print(f"\nFigure saved: {out_pdf}")
print(f"PNG saved:    {out_png}")
print("\nDone — inferential_stats.py completed successfully.")
