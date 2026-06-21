"""
generate_prisma.py
Regenerate fig_prisma_flow_updated.pdf with correct non-overlapping layout
and properly directed arrows.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUTDIR = "/home/ubuntu/repo_push/empirical_evaluation/figures/"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

fig, ax = plt.subplots(figsize=(9, 12))
ax.axis("off")

# ── Numbers ───────────────────────────────────────────────────────────────────
total_raw         = 100_557
total_dedup       = 99_500
total_included    = 18_936
total_excluded    = total_dedup - total_included   # 80,564
total_extracted   = 4_000    # 20 cases × 200 cap
total_validated   = total_extracted

# ── Layout constants ──────────────────────────────────────────────────────────
# Main column: centre x = 0.40
# Side column: centre x = 0.83
# 6 main boxes at y = 0.90, 0.74, 0.58, 0.42, 0.26, 0.10
# Box full height = 0.08  →  half = 0.04
# Vertical gap between boxes = 0.16 - 0.08 = 0.08  (no overlap)

MX  = 0.40   # main column x
SX  = 0.83   # side column x
BW  = 0.58   # main box width
SW  = 0.24   # side box width
BH  = 0.08   # box full height
HBH = BH / 2 # half box height
FS  = 9      # main font size
SFS = 8      # side font size

YS = [0.90, 0.74, 0.58, 0.42, 0.26, 0.10]   # main box y-centres

COLORS = {
    "id":    "#2166ac",
    "scr":   "#4dac26",
    "ext":   "#762a83",
    "val":   "#8856a7",
    "excl":  "#d73027",
}

# ── Helper functions ──────────────────────────────────────────────────────────
def pbox(cx, cy, w, h, text, color, fs=9):
    rect = mpatches.FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.015",
        facecolor="white", edgecolor=color, linewidth=1.8)
    ax.add_patch(rect)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fs, multialignment="center")

def varrow(y_top_centre, y_bot_centre):
    """Vertical arrow from bottom edge of upper box to top edge of lower box."""
    ax.annotate("",
        xy=(MX, y_bot_centre + HBH),
        xytext=(MX, y_top_centre - HBH),
        arrowprops=dict(arrowstyle="->", color="black", lw=1.3))

def harrow(y_centre, color):
    """Horizontal arrow from right edge of main box to left edge of side box."""
    ax.annotate("",
        xy=(SX - SW/2, y_centre),
        xytext=(MX + BW/2, y_centre),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.3))

# ── Main boxes ────────────────────────────────────────────────────────────────
pbox(MX, YS[0], BW, BH,
     f"Records identified via API retrieval\n(n = {total_raw:,})",
     COLORS["id"])

varrow(YS[0], YS[1])
pbox(MX, YS[1], BW, BH,
     f"Records after deduplication\n(n = {total_dedup:,})",
     COLORS["id"])

varrow(YS[1], YS[2])
pbox(MX, YS[2], BW, BH,
     f"Records screened (LLM zero-shot)\n(n = {total_dedup:,})",
     COLORS["scr"])

varrow(YS[2], YS[3])
pbox(MX, YS[3], BW, BH,
     f"Records included for extraction\n(n = {total_included:,})",
     COLORS["scr"])

varrow(YS[3], YS[4])
pbox(MX, YS[4], BW, BH,
     f"Records with structured extraction\n(n = {total_extracted:,}; capped 200/case × 20 cases)",
     COLORS["ext"])

varrow(YS[4], YS[5])
pbox(MX, YS[5], BW, BH,
     f"Records with LLM-as-Judge validation\n(n = {total_validated:,})",
     COLORS["val"])

# ── Side boxes ────────────────────────────────────────────────────────────────
# Excluded: beside Screening box (YS[2])
pbox(SX, YS[2], SW, BH,
     f"Records excluded\n(n = {total_excluded:,})",
     COLORS["excl"], fs=SFS)
harrow(YS[2], COLORS["excl"])

# Cap note: beside Extraction box (YS[4])
pbox(SX, YS[4], SW, BH,
     f"Cap applied:\n200 records/case\n(20 cases)",
     COLORS["ext"], fs=SFS)
harrow(YS[4], COLORS["ext"])

# ── Stage labels ──────────────────────────────────────────────────────────────
stage_labels = [
    "Identification", "Deduplication", "Screening",
    "Inclusion", "Extraction", "Validation"
]
for y, lbl in zip(YS, stage_labels):
    ax.text(0.01, y, lbl, fontsize=8.5, color="gray",
            style="italic", va="center")

ax.set_xlim(0, 1.05)
ax.set_ylim(0.02, 1.0)
ax.set_title("PRISMA-style flow diagram (20-case evaluation)",
             fontsize=11, pad=10)
plt.tight_layout()
plt.savefig(OUTDIR + "fig_prisma_flow_updated.pdf")
plt.close()
print("Saved fig_prisma_flow_updated.pdf")
