"""
case_selection_rationale.py
============================
Issue 4 — Case Selection Rationale Figure

Produces a 3-panel figure demonstrating that the 20 case studies were selected
to achieve structured coverage across:
  (a) Five disciplinary domains (balanced representation)
  (b) A wide range of corpus prevalence rates (sparse → dense)
  (c) A wide range of corpus sizes (small → very large)

Also produces a bubble chart (panel d) showing the joint distribution of
prevalence × corpus size, coloured by domain, to demonstrate that the selection
is not clustered in any corner of the design space.

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
import matplotlib.ticker as mticker
import os

np.random.seed(42)

OUT_DIR = "/home/ubuntu/repo_push/empirical_evaluation/figures"
os.makedirs(OUT_DIR, exist_ok=True)

# ── Data ──────────────────────────────────────────────────────────────────────
data = pd.DataFrame({
    "case_id": list(range(1, 21)),
    "label": [
        "Nurse Staffing", "Mindfulness/Anxiety", "GLP-1 Cardio",
        "AI Radiology", "Cash Transfers", "Social Media MH",
        "Restorative Justice", "Gender Pay Gap", "Intelligent Tutoring",
        "Game-Based Learning", "Class Size", "LLM Higher Ed",
        "Marine Protected Areas", "Reforestation Carbon", "Indoor Air Pollution",
        "Microplastics", "LLM Reasoning", "Federated Learning",
        "AI Ethics", "DL Predictive Maint.",
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
    "api": [
        "PubMed", "EuropePMC", "OpenAlex", "OpenAlex", "OpenAlex",
        "OpenAlex", "CORE", "OpenAlex", "OpenAlex", "Semantic Scholar",
        "OpenAlex", "CORE", "OpenAlex", "OpenAlex", "OpenAlex",
        "EuropePMC", "Semantic Scholar", "OpenAlex", "Semantic Scholar", "OpenAlex",
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
API_COLORS = {
    "OpenAlex":        "#1f78b4",
    "EuropePMC":       "#33a02c",
    "CORE":            "#e31a1c",
    "PubMed":          "#ff7f00",
    "Semantic Scholar":"#6a3d9a",
}

# ── Figure ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 12))
fig.patch.set_facecolor("white")
gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.44, wspace=0.36)

ax_a = fig.add_subplot(gs[0, 0])  # Domain distribution (bar)
ax_b = fig.add_subplot(gs[0, 1])  # Prevalence histogram
ax_c = fig.add_subplot(gs[1, 0])  # Corpus size histogram
ax_d = fig.add_subplot(gs[1, 1])  # Bubble chart: prevalence × corpus size

# ── Panel (a): Domain distribution ───────────────────────────────────────────
domain_counts = data["domain"].value_counts().reindex(DOMAIN_ORDER)
colors_a = [DOMAIN_COLORS[d] for d in DOMAIN_ORDER]
bars = ax_a.bar(range(len(DOMAIN_ORDER)), domain_counts.values,
                color=colors_a, width=0.6, edgecolor="white", linewidth=1.2, alpha=0.88)
for bar, val in zip(bars, domain_counts.values):
    ax_a.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
              str(val), ha="center", va="bottom", fontsize=11, fontweight="bold")
ax_a.set_xticks(range(len(DOMAIN_ORDER)))
ax_a.set_xticklabels([d.replace("/", "/\n") for d in DOMAIN_ORDER], fontsize=9)
ax_a.set_ylabel("Number of Case Studies", fontsize=10)
ax_a.set_ylim(0, 7)
ax_a.set_title("(a) Domain Distribution\n(balanced across 5 disciplines)", fontsize=11, fontweight="bold")
ax_a.spines[["top", "right"]].set_visible(False)
ax_a.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

# ── Panel (b): Prevalence histogram ──────────────────────────────────────────
bins_prev = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
ax_b.hist(data["prevalence_pct"], bins=bins_prev, color="#5b8db8", edgecolor="white",
          linewidth=1.2, alpha=0.88)
ax_b.axvline(data["prevalence_pct"].mean(), color="#d62728", lw=1.8, ls="--",
             label=f"Mean = {data['prevalence_pct'].mean():.1f}%")
ax_b.axvline(data["prevalence_pct"].median(), color="#2ca02c", lw=1.8, ls=":",
             label=f"Median = {data['prevalence_pct'].median():.1f}%")
ax_b.set_xlabel("Corpus Prevalence (%)", fontsize=10)
ax_b.set_ylabel("Number of Case Studies", fontsize=10)
ax_b.set_title("(b) Prevalence Distribution\n(sparse to dense, full range covered)",
               fontsize=11, fontweight="bold")
ax_b.legend(fontsize=9, frameon=True, framealpha=0.9)
ax_b.spines[["top", "right"]].set_visible(False)
ax_b.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

# Annotate range
ax_b.text(0.97, 0.97,
          f"Range: {data['prevalence_pct'].min():.1f}% – {data['prevalence_pct'].max():.1f}%\nSD = {data['prevalence_pct'].std():.1f}%",
          transform=ax_b.transAxes, ha="right", va="top", fontsize=8.5,
          bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#cccccc"))

# ── Panel (c): Corpus size histogram ─────────────────────────────────────────
bins_corp = [0, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10500]
ax_c.hist(data["corpus_size"], bins=bins_corp, color="#7b9e6b", edgecolor="white",
          linewidth=1.2, alpha=0.88)
ax_c.axvline(data["corpus_size"].mean(), color="#d62728", lw=1.8, ls="--",
             label=f"Mean = {data['corpus_size'].mean():,.0f}")
ax_c.axvline(data["corpus_size"].median(), color="#2ca02c", lw=1.8, ls=":",
             label=f"Median = {data['corpus_size'].median():,.0f}")
ax_c.set_xlabel("Deduplicated Corpus Size (records)", fontsize=10)
ax_c.set_ylabel("Number of Case Studies", fontsize=10)
ax_c.set_title("(c) Corpus Size Distribution\n(small niche topics to large interdisciplinary fields)",
               fontsize=11, fontweight="bold")
ax_c.legend(fontsize=9, frameon=True, framealpha=0.9)
ax_c.spines[["top", "right"]].set_visible(False)
ax_c.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax_c.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

ax_c.text(0.97, 0.97,
          f"Range: {data['corpus_size'].min():,} – {data['corpus_size'].max():,}\nSD = {data['corpus_size'].std():,.0f}",
          transform=ax_c.transAxes, ha="right", va="top", fontsize=8.5,
          bbox=dict(boxstyle="round,pad=0.4", fc="#f5f5f5", ec="#cccccc"))

# ── Panel (d): Bubble chart ───────────────────────────────────────────────────
for _, row in data.iterrows():
    ax_d.scatter(row["prevalence_pct"], row["corpus_size"],
                 color=DOMAIN_COLORS[row["domain"]],
                 s=80, alpha=0.88, zorder=3,
                 edgecolors="white", linewidths=0.8)
    ax_d.annotate(str(row["case_id"]),
                  (row["prevalence_pct"], row["corpus_size"]),
                  textcoords="offset points", xytext=(5, 3),
                  fontsize=7.5, color="#333333")

ax_d.set_xlabel("Corpus Prevalence (%)", fontsize=10)
ax_d.set_ylabel("Deduplicated Corpus Size (records)", fontsize=10)
ax_d.set_title("(d) Joint Design Space Coverage\n(prevalence × corpus size, coloured by domain)",
               fontsize=11, fontweight="bold")
ax_d.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
ax_d.spines[["top", "right"]].set_visible(False)

# Domain legend
legend_patches = [mpatches.Patch(color=DOMAIN_COLORS[d], label=d) for d in DOMAIN_ORDER]
ax_d.legend(handles=legend_patches, fontsize=8, loc="upper right",
            frameon=True, framealpha=0.9)

# ── Suptitle ──────────────────────────────────────────────────────────────────
fig.suptitle(
    "Case Selection Rationale: Structured Coverage Across Domain, Prevalence, and Corpus Size\n"
    "(20 case studies spanning 5 disciplines, prevalence 1.9%–83.7%, corpus size 90–9,929 records)",
    fontsize=12, fontweight="bold", y=1.01
)

out_pdf = os.path.join(OUT_DIR, "fig_case_selection_rationale.pdf")
out_png = os.path.join(OUT_DIR, "fig_case_selection_rationale.png")
fig.savefig(out_pdf, bbox_inches="tight", dpi=300)
fig.savefig(out_png, bbox_inches="tight", dpi=150)
plt.close(fig)
print(f"Figure saved: {out_pdf}")
print(f"PNG saved:    {out_png}")
print("Done — case_selection_rationale.py completed successfully.")
