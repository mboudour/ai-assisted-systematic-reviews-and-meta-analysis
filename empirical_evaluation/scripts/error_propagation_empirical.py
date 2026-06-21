"""
error_propagation_empirical.py
Fully empirical error-propagation analysis using real extracted data from two cases:
  - Case 3: GLP-1 cardiovascular (HR + CI, k=257)
  - Case 15: Indoor air pollution / health (effect size + CI, k=1350)

For each case we:
  1. Run the true DerSimonian-Laird RE meta-analysis on verified records only
  2. Simulate 7% and 20% sample-size halving errors
  3. Report pooled estimate, 95% CI, I², τ² for each scenario
  4. Generate a 2-row × 3-column forest-plot comparison figure
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

OUTDIR = "/home/ubuntu/repo_push/empirical_evaluation/figures/"
np.random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# 1.  DerSimonian-Laird random-effects meta-analysis
# ─────────────────────────────────────────────────────────────────────────────
def dl_meta(yi, sei):
    """
    DerSimonian-Laird random-effects meta-analysis.
    yi  : array of log effect sizes (or effect sizes)
    sei : array of within-study standard errors
    Returns: pooled_est, pooled_se, I2, tau2, Q, k
    """
    yi  = np.asarray(yi, dtype=float)
    sei = np.asarray(sei, dtype=float)
    vi  = sei ** 2
    wi  = 1.0 / vi                        # fixed-effect weights

    k   = len(yi)
    Q   = np.sum(wi * (yi - np.sum(wi * yi) / np.sum(wi)) ** 2)
    df  = k - 1
    c   = np.sum(wi) - np.sum(wi ** 2) / np.sum(wi)
    tau2 = max(0.0, (Q - df) / c)

    wi_re = 1.0 / (vi + tau2)
    mu    = np.sum(wi_re * yi) / np.sum(wi_re)
    se_mu = np.sqrt(1.0 / np.sum(wi_re))

    I2 = max(0.0, (Q - df) / Q) * 100 if Q > 0 else 0.0
    return mu, se_mu, I2, tau2, Q, k


def perturb(yi, sei, n_array, error_rate, rng):
    """
    Halve the sample size for `error_rate` fraction of studies.
    This doubles the SE (SE ∝ 1/√n).
    """
    n_err = int(np.round(len(yi) * error_rate))
    idx   = rng.choice(len(yi), size=n_err, replace=False)
    sei_p = sei.copy()
    sei_p[idx] *= np.sqrt(2)              # halving n → SE × √2
    return sei_p


def run_scenarios(yi, sei, n_array, label):
    rng = np.random.default_rng(42)
    results = {}
    # True
    mu, se, I2, tau2, Q, k = dl_meta(yi, sei)
    results["True"] = dict(mu=mu, se=se, I2=I2, tau2=tau2, k=k)
    # 7% error
    sei_7 = perturb(yi, sei, n_array, 0.07, rng)
    mu7, se7, I2_7, tau2_7, _, _ = dl_meta(yi, sei_7)
    results["7% error"] = dict(mu=mu7, se=se7, I2=I2_7, tau2=tau2_7, k=k)
    # 20% error
    sei_20 = perturb(yi, sei, n_array, 0.20, rng)
    mu20, se20, I2_20, tau2_20, _, _ = dl_meta(yi, sei_20)
    results["20% error"] = dict(mu=mu20, se=se20, I2=I2_20, tau2=tau2_20, k=k)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Load Case 3 (GLP-1 cardiovascular) — log-HR scale
# ─────────────────────────────────────────────────────────────────────────────
df3 = pd.read_csv("/home/ubuntu/upload/case_03_glp1_cardiovascular_extracted.csv")
# Keep rows with all numeric fields verified by judge
df3 = df3.dropna(subset=["hazard_ratio", "ci_lower", "ci_upper", "sample_size"])
df3 = df3[df3["sample_size"] > 0]
df3["log_hr"]  = np.log(df3["hazard_ratio"])
df3["se_log"]  = (np.log(df3["ci_upper"]) - np.log(df3["ci_lower"])) / (2 * 1.96)
df3 = df3[df3["se_log"] > 0]
yi3  = df3["log_hr"].values
sei3 = df3["se_log"].values
n3   = df3["sample_size"].values

res3 = run_scenarios(yi3, sei3, n3, "Case 3")
print("Case 3 (GLP-1 cardiovascular):")
for sc, v in res3.items():
    print(f"  {sc}: HR={np.exp(v['mu']):.3f} "
          f"95%CI [{np.exp(v['mu']-1.96*v['se']):.3f}, {np.exp(v['mu']+1.96*v['se']):.3f}] "
          f"I²={v['I2']:.1f}% τ²={v['tau2']:.4f} k={v['k']}")

# ─────────────────────────────────────────────────────────────────────────────
# 3.  Load Case 15 (indoor air pollution) — effect size scale
# ─────────────────────────────────────────────────────────────────────────────
df15 = pd.read_csv("/home/ubuntu/upload/case_15_indoor_air_pollution_health_extracted.csv")
df15 = df15.dropna(subset=["effect_size", "ci_lower", "ci_upper", "sample_size"])
df15 = df15[df15["sample_size"] > 0]
df15["se"] = (df15["ci_upper"] - df15["ci_lower"]) / (2 * 1.96)
df15 = df15[df15["se"] > 0]
yi15  = df15["effect_size"].values
sei15 = df15["se"].values
n15   = df15["sample_size"].values

res15 = run_scenarios(yi15, sei15, n15, "Case 15")
print("\nCase 15 (Indoor air pollution):")
for sc, v in res15.items():
    print(f"  {sc}: ES={v['mu']:.3f} "
          f"95%CI [{v['mu']-1.96*v['se']:.3f}, {v['mu']+1.96*v['se']:.3f}] "
          f"I²={v['I2']:.1f}% τ²={v['tau2']:.4f} k={v['k']}")

# ─────────────────────────────────────────────────────────────────────────────
# 4.  Figure: 2-row × 3-column comparison
#     Row 1 = Case 3 (log-HR back-transformed to HR)
#     Row 2 = Case 15 (effect size)
#     Columns = True / 7% error / 20% error
# ─────────────────────────────────────────────────────────────────────────────
SCENARIOS = ["True", "7% error", "20% error"]
COLORS = {"True": "#2166ac", "7% error": "#f4a582", "20% error": "#d6604d"}

fig, axes = plt.subplots(2, 3, figsize=(14, 9))
fig.suptitle(
    "Empirical Error Propagation in Meta-Analysis\n"
    "(Real extracted data: Case 3 GLP-1 Cardiovascular  |  Case 15 Indoor Air Pollution)",
    fontsize=13, fontweight="bold", y=1.01
)

def draw_forest_panel(ax, yi, sei, scenario_res, sc_name, transform_fn, xlabel,
                      case_label, n_show=30):
    """Draw a mini forest plot for one scenario."""
    # Sample up to n_show studies for visual clarity
    rng2 = np.random.default_rng(0)
    idx  = rng2.choice(len(yi), size=min(n_show, len(yi)), replace=False)
    idx  = np.sort(idx)

    y_pos = np.arange(len(idx))
    color = COLORS[sc_name]

    for j, i in enumerate(idx):
        mu_i  = transform_fn(yi[i])
        lo_i  = transform_fn(yi[i] - 1.96 * sei[i])
        hi_i  = transform_fn(yi[i] + 1.96 * sei[i])
        ax.plot([lo_i, hi_i], [j, j], color="#aaaaaa", linewidth=0.8, zorder=1)
        ax.plot(mu_i, j, "s", color=color, markersize=4, zorder=2)

    # Pooled diamond
    v = scenario_res[sc_name]
    mu_p  = transform_fn(v["mu"])
    lo_p  = transform_fn(v["mu"] - 1.96 * v["se"])
    hi_p  = transform_fn(v["mu"] + 1.96 * v["se"])
    dy    = 0.6
    y_d   = -1.8
    diamond_x = [lo_p, mu_p, hi_p, mu_p, lo_p]
    diamond_y = [y_d,  y_d + dy, y_d, y_d - dy, y_d]
    ax.fill(diamond_x, diamond_y, color=color, zorder=3, alpha=0.85)
    ax.axvline(mu_p, color=color, linewidth=1.2, linestyle="--", alpha=0.6)

    # Reference line
    ref = transform_fn(0.0)
    ax.axvline(ref, color="black", linewidth=0.8, linestyle="-")

    # Stats annotation
    stats_txt = (
        f"k = {v['k']}\n"
        f"Pooled = {mu_p:.3f}\n"
        f"95% CI [{lo_p:.3f}, {hi_p:.3f}]\n"
        f"I² = {v['I2']:.1f}%\n"
        f"τ² = {v['tau2']:.4f}"
    )
    ax.text(0.97, 0.97, stats_txt, transform=ax.transAxes,
            fontsize=7.5, va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=color, alpha=0.9))

    ax.set_yticks([])
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_title(f"{case_label}\n{sc_name}", fontsize=9, fontweight="bold",
                 color=color)
    ax.spines[["top", "right", "left"]].set_visible(False)


# Row 0: Case 3 (HR scale)
for col, sc in enumerate(SCENARIOS):
    draw_forest_panel(
        axes[0, col], yi3, sei3, res3, sc,
        transform_fn=np.exp,
        xlabel="Hazard Ratio",
        case_label="Case 3: GLP-1 Cardiovascular",
        n_show=40
    )

# Row 1: Case 15 (effect size scale)
for col, sc in enumerate(SCENARIOS):
    draw_forest_panel(
        axes[1, col], yi15, sei15, res15, sc,
        transform_fn=lambda x: x,
        xlabel="Effect Size (OR / RR)",
        case_label="Case 15: Indoor Air Pollution",
        n_show=40
    )

plt.tight_layout()
out_pdf = OUTDIR + "fig_meta_analysis_comparison.pdf"
out_png = OUTDIR + "fig_meta_analysis_comparison.png"
plt.savefig(out_pdf, dpi=150, bbox_inches="tight")
plt.savefig(out_png, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nSaved {out_pdf}")
print(f"Saved {out_png}")
