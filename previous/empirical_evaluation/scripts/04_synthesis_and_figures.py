"""
04_synthesis_and_figures.py
----------------------------
Performs meta-analysis and generates all manuscript figures:
  1. Forest plots (per domain cluster, AI vs human pipeline)
  2. Screening efficiency dot plot (WSS@95 across 20 cases)
  3. Extraction accuracy heatmap (categorical and numeric fields)
  4. PRISMA aggregate flow diagram
  5. Keyword co-occurrence network (aggregate across all cases)

Outputs saved to figures/ and outputs/

Run:
    python scripts/04_synthesis_and_figures.py

Requires: outputs/retrieval_summary.csv, outputs/screening_summary.csv,
          outputs/extraction_summary.csv, data/extracted/ populated by 03_extraction.py
"""

import os, json, warnings
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

ROOT        = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = ROOT / "figures"
EXTRACTED_DIR = ROOT / "data" / "extracted"
FIGURES_DIR.mkdir(exist_ok=True)

# ── Colour palette (consistent with manuscript style) ─────────────────────────
COL_AI    = "#2166ac"   # blue  — AI pipeline
COL_HUMAN = "#d6604d"   # red   — human / corrected pipeline
COL_AL    = "#4dac26"   # green — active learning
COL_LLM   = "#7b3294"   # purple — LLM zero-shot
GREY      = "#888888"

# ── Domain groupings for forest plots ─────────────────────────────────────────
DOMAIN_CASES = {
    "Health & Clinical":          [1, 2, 3, 4],
    "Social & Behavioural":       [5, 6, 7, 8],
    "Education & Learning":       [9, 10, 11, 12],
    "Environmental":              [13, 14, 15, 16],
    "Computer Science & AI":      [17, 18, 19, 20],
}

CASE_SLUGS = {
    1: "Nurse staffing → mortality",
    2: "Mindfulness → anxiety",
    3: "GLP-1 → cardiovascular",
    4: "AI → radiology accuracy",
    5: "Cash transfers → education",
    6: "Social media → mental health",
    7: "Restorative justice → recidivism",
    8: "Gender pay gap",
    9: "ITS → test scores",
    10: "Game-based learning → motivation",
    11: "Class size → achievement",
    12: "LLM in higher education",
    13: "MPAs → fish biomass",
    14: "Reforestation → carbon",
    15: "Indoor air pollution → health",
    16: "Microplastics in freshwater",
    17: "LLM reasoning benchmarks",
    18: "Federated learning privacy",
    19: "AI ethics frameworks",
    20: "DL → predictive maintenance",
}

# ── Helper: load summary CSVs ─────────────────────────────────────────────────
def load_summary(name: str) -> pd.DataFrame:
    path = OUTPUTS_DIR / name
    if path.exists():
        return pd.read_csv(path)
    print(f"  [WARN] {name} not found — using placeholder data")
    return pd.DataFrame()

# ── Figure 1: Forest plots per domain cluster ─────────────────────────────────
def plot_forest_plots(extraction_df: pd.DataFrame):
    """
    For each domain, plot a forest plot of effect sizes (AI-extracted vs corrected).
    Uses data from extraction CSVs where effect_size, ci_lower, ci_upper are available.
    Falls back to placeholder data if real data not yet available.
    """
    for domain, case_ids in DOMAIN_CASES.items():
        fig, ax = plt.subplots(figsize=(10, max(4, len(case_ids) * 1.2)))
        y_positions = list(range(len(case_ids), 0, -1))
        plotted = False
        for i, (cid, ypos) in enumerate(zip(case_ids, y_positions)):
            slug = CASE_SLUGS.get(cid, f"Case {cid}")
            # Try to load real extraction data
            ext_files = list(EXTRACTED_DIR.glob(f"case_{cid:02d}_*_extracted.csv"))
            if ext_files and not extraction_df.empty:
                df_ext = pd.read_csv(ext_files[0])
                if "effect_size" in df_ext.columns:
                    es  = pd.to_numeric(df_ext["effect_size"], errors="coerce").dropna()
                    ci_l = pd.to_numeric(df_ext.get("ci_lower", pd.Series()), errors="coerce").dropna()
                    ci_u = pd.to_numeric(df_ext.get("ci_upper", pd.Series()), errors="coerce").dropna()
                    if len(es) > 0:
                        # Pooled using inverse-variance (simplified: equal weights here)
                        pooled_es = es.mean()
                        pooled_ci_l = ci_l.mean() if len(ci_l) > 0 else pooled_es - 0.3
                        pooled_ci_u = ci_u.mean() if len(ci_u) > 0 else pooled_es + 0.3
                        ax.plot([pooled_ci_l, pooled_ci_u], [ypos, ypos],
                                color=COL_AI, linewidth=2, zorder=2)
                        ax.scatter([pooled_es], [ypos], color=COL_AI, s=60, zorder=3)
                        plotted = True
                        continue
            # Placeholder
            placeholder_es = np.random.uniform(-0.5, 1.0)
            placeholder_ci = (placeholder_es - 0.3, placeholder_es + 0.3)
            ax.plot([placeholder_ci[0], placeholder_ci[1]], [ypos, ypos],
                    color=COL_AI, linewidth=2, zorder=2, linestyle="--", alpha=0.4)
            ax.scatter([placeholder_es], [ypos], color=COL_AI, s=60, zorder=3, alpha=0.4)

        ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_yticks(y_positions)
        ax.set_yticklabels([CASE_SLUGS.get(cid, f"Case {cid}") for cid in case_ids], fontsize=9)
        ax.set_xlabel("Standardised Mean Difference / Effect Size", fontsize=10)
        domain_slug = domain.lower().replace(" & ", "_").replace(" ", "_")
        ax.set_title(f"Forest Plot — {domain}", fontsize=11, fontweight="bold")
        if not plotted:
            ax.text(0.5, 0.02, "Placeholder: real data pending",
                    transform=ax.transAxes, ha="center", fontsize=8, color="grey")
        plt.tight_layout()
        out = FIGURES_DIR / f"forest_{domain_slug}.pdf"
        plt.savefig(out, bbox_inches="tight")
        plt.close()
        print(f"  Saved: {out.name}")

# ── Figure 2: Screening efficiency dot plot ───────────────────────────────────
def plot_screening_efficiency(screening_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 7))
    if screening_df.empty:
        ax.text(0.5, 0.5, "Placeholder: run 02_screening.py first",
                ha="center", va="center", transform=ax.transAxes, fontsize=12, color="grey")
    else:
        df = screening_df.sort_values("case_id")
        y = np.arange(len(df))
        ax.scatter(df["al_wss95"].fillna(0), y, color=COL_AL, s=80, label="Active Learning (WSS@95)", zorder=3)
        ax.scatter(df["llm_f1"].fillna(0), y, color=COL_LLM, s=80, marker="D",
                   label="LLM Zero-Shot (F1)", zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels([CASE_SLUGS.get(int(r["case_id"]), f"Case {int(r['case_id'])}") for _, r in df.iterrows()], fontsize=8)
        ax.axvline(0.95, color="red", linestyle="--", linewidth=0.8, label="WSS@95 = 0.95 target")
        ax.set_xlabel("Performance Metric", fontsize=10)
        ax.set_title("Screening Efficiency Across 20 Case Studies", fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.set_xlim(0, 1.05)
        ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    out = FIGURES_DIR / "screening_efficiency.pdf"
    plt.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")

# ── Figure 3: Extraction accuracy heatmap ────────────────────────────────────
def plot_extraction_heatmap(extraction_summary_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 7))
    if extraction_summary_df.empty:
        ax.text(0.5, 0.5, "Placeholder: run 03_extraction.py first",
                ha="center", va="center", transform=ax.transAxes, fontsize=12, color="grey")
    else:
        # Pivot: rows = cases, cols = cat_accuracy fields
        cat_cols = [c for c in extraction_summary_df.columns if c.startswith("cat_accuracy_")]
        if cat_cols:
            pivot = extraction_summary_df.set_index("slug")[cat_cols].astype(float)
            pivot.columns = [c.replace("cat_accuracy_", "") for c in cat_cols]
            sns.heatmap(pivot, ax=ax, cmap="RdYlGn", vmin=0, vmax=1,
                        annot=True, fmt=".2f", linewidths=0.5, cbar_kws={"label": "Accuracy"})
            ax.set_title("LLM-as-Judge Categorical Extraction Accuracy", fontsize=11, fontweight="bold")
            ax.set_xlabel("Extracted Field", fontsize=10)
            ax.set_ylabel("Case Study", fontsize=10)
        else:
            ax.text(0.5, 0.5, "No categorical accuracy data available",
                    ha="center", va="center", transform=ax.transAxes, fontsize=12, color="grey")
    plt.tight_layout()
    out = FIGURES_DIR / "extraction_accuracy_heatmap.pdf"
    plt.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")

# ── Figure 4: PRISMA aggregate flow diagram ───────────────────────────────────
def plot_prisma_flow(retrieval_df: pd.DataFrame, screening_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.axis("off")
    if retrieval_df.empty or screening_df.empty:
        ax.text(0.5, 0.5, "Placeholder: run retrieval and screening scripts first",
                ha="center", va="center", fontsize=12, color="grey")
    else:
        total_raw       = int(retrieval_df["raw"].sum()) if "raw" in retrieval_df.columns else 0
        total_dedup     = int(retrieval_df["after_dedup"].sum()) if "after_dedup" in retrieval_df.columns else 0
        total_included  = int(screening_df["n_included_llm"].sum()) if "n_included_llm" in screening_df.columns else 0
        total_screened  = int(screening_df["n_total"].sum()) if "n_total" in screening_df.columns else 0
        total_excluded  = total_dedup - total_included

        boxes = [
            (0.5, 0.92, f"Records identified via API search\n(n = {total_raw:,})", "#d0e8f7"),
            (0.5, 0.75, f"Records after deduplication\n(n = {total_dedup:,})", "#d0e8f7"),
            (0.5, 0.58, f"Records screened\n(n = {total_screened:,})", "#d0e8f7"),
            (0.5, 0.41, f"Records assessed for eligibility\n(n = {total_included:,})", "#d0e8f7"),
            (0.5, 0.18, f"Studies included in synthesis\n(n = [pending full-text review])", "#c8e6c9"),
        ]
        side_boxes = [
            (0.82, 0.75, f"Duplicates removed\n(n = {total_raw - total_dedup:,})", "#fce4d6"),
            (0.82, 0.58, f"Records excluded\n(n = {total_excluded:,})", "#fce4d6"),
        ]
        for x, y, text, color in boxes:
            ax.text(x, y, text, ha="center", va="center", fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.5", facecolor=color, edgecolor="grey"),
                    transform=ax.transAxes)
        for x, y, text, color in side_boxes:
            ax.text(x, y, text, ha="center", va="center", fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.4", facecolor=color, edgecolor="grey"),
                    transform=ax.transAxes)
        # Arrows
        for y_start, y_end in [(0.88, 0.80), (0.71, 0.63), (0.54, 0.46), (0.37, 0.25)]:
            ax.annotate("", xy=(0.5, y_end), xytext=(0.5, y_start),
                        xycoords="axes fraction", textcoords="axes fraction",
                        arrowprops=dict(arrowstyle="->", color="black"))
    ax.set_title("PRISMA Flow Diagram — Aggregate Across 20 Case Studies",
                 fontsize=11, fontweight="bold", pad=10)
    plt.tight_layout()
    out = FIGURES_DIR / "prisma_flow.pdf"
    plt.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")

# ── Figure 5: Keyword co-occurrence network ───────────────────────────────────
def plot_keyword_network():
    """
    Build a keyword co-occurrence network from all raw CSV titles (aggregate).
    Uses a simple sliding-window co-occurrence on title tokens.
    """
    try:
        import networkx as nx
        from sklearn.feature_extraction.text import CountVectorizer
    except ImportError:
        print("  [SKIP] networkx or sklearn not available for keyword network")
        return

    raw_dir = ROOT / "data" / "raw"
    all_titles = []
    for f in raw_dir.glob("case_*.csv"):
        df = pd.read_csv(f, usecols=["title"])
        all_titles.extend(df["title"].dropna().tolist())

    if not all_titles:
        print("  [SKIP] No titles found for keyword network")
        return

    # Build co-occurrence matrix using bigrams
    vec = CountVectorizer(ngram_range=(1, 2), max_features=200,
                          stop_words="english", min_df=5)
    X = vec.fit_transform(all_titles)
    terms = vec.get_feature_names_out()
    Xc = (X.T @ X).toarray()
    np.fill_diagonal(Xc, 0)

    G = nx.Graph()
    for i, t in enumerate(terms):
        G.add_node(t, weight=int(X[:, i].sum()))
    threshold = np.percentile(Xc[Xc > 0], 90)
    for i in range(len(terms)):
        for j in range(i + 1, len(terms)):
            if Xc[i, j] >= threshold:
                G.add_edge(terms[i], terms[j], weight=float(Xc[i, j]))

    # Keep largest connected component
    largest_cc = max(nx.connected_components(G), key=len)
    G = G.subgraph(largest_cc).copy()

    fig, ax = plt.subplots(figsize=(14, 10))
    pos = nx.spring_layout(G, seed=42, k=0.5)
    node_sizes = [G.nodes[n].get("weight", 10) * 0.5 for n in G.nodes]
    edge_weights = [G[u][v]["weight"] * 0.01 for u, v in G.edges]
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=COL_AI, alpha=0.7, ax=ax)
    nx.draw_networkx_edges(G, pos, width=edge_weights, alpha=0.4, edge_color=GREY, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7, ax=ax)
    ax.set_title("Keyword Co-occurrence Network — Aggregate Across 20 Case Studies",
                 fontsize=11, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    out = FIGURES_DIR / "keyword_network.pdf"
    plt.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {out.name}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n[1/5] Loading summary data...")
    retrieval_df   = load_summary("retrieval_summary.csv")
    screening_df   = load_summary("screening_summary.csv")
    extraction_df  = load_summary("extraction_summary.csv")

    print("\n[2/5] Generating forest plots...")
    plot_forest_plots(extraction_df)

    print("\n[3/5] Generating screening efficiency plot...")
    plot_screening_efficiency(screening_df)

    print("\n[4/5] Generating extraction accuracy heatmap...")
    plot_extraction_heatmap(extraction_df)

    print("\n[5/5] Generating PRISMA flow diagram...")
    plot_prisma_flow(retrieval_df, screening_df)

    print("\n[+] Generating keyword co-occurrence network...")
    plot_keyword_network()

    print(f"\nAll figures saved to {FIGURES_DIR}")

if __name__ == "__main__":
    main()
