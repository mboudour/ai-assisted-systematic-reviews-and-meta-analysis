"""
generate_prisma.py  –  PRISMA flow diagram using explicit data coordinates.
Uses a 10×18 inch figure with a 0–100 x-axis and 0–180 y-axis so every
measurement is in plain integers, making overlap impossible to hide.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

OUTDIR = "/home/ubuntu/repo_push/empirical_evaluation/figures/"

# ── Numbers ───────────────────────────────────────────────────────────────────
total_raw       = 100_557
total_dedup     = 99_500
total_included  = 18_936
total_excluded  = total_dedup - total_included   # 80,564
total_extracted = 4_000
total_validated = total_extracted

# ── Canvas ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 18))
ax.set_xlim(0, 100)
ax.set_ylim(0, 180)
ax.axis("off")

plt.rcParams.update({"font.family": "serif", "savefig.dpi": 300,
                     "savefig.bbox": "tight"})

# ── Layout (all in data units) ────────────────────────────────────────────────
# Main column: centred at x=42, width=52, height=10
# Side column: centred at x=82, width=26, height=10
# 6 main boxes at y_centres: 165, 135, 105, 75, 45, 15
# Gap between boxes = 30 - 10 = 20 units  (no overlap possible)

MX, BW, BH = 42, 52, 10   # main centre-x, width, height
SX, SW     = 82, 26        # side centre-x, width  (same BH)
HBH        = BH / 2        # 5 units

YS = [165, 135, 105, 75, 45, 15]   # main box y-centres (top to bottom)

COLORS = {
    "id":   "#2166ac",
    "scr":  "#4dac26",
    "ext":  "#762a83",
    "val":  "#8856a7",
    "excl": "#d73027",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def pbox(cx, cy, w, h, text, color, fs=9):
    rect = mpatches.FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.5",
        facecolor="white", edgecolor=color, linewidth=2,
        transform=ax.transData, clip_on=False)
    ax.add_patch(rect)
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=fs, multialignment="center", transform=ax.transData)

def varrow(y_upper_centre, y_lower_centre):
    """Downward arrow from bottom of upper box to top of lower box."""
    ax.annotate("",
        xy=(MX, y_lower_centre + HBH),
        xytext=(MX, y_upper_centre - HBH),
        arrowprops=dict(arrowstyle="->", color="black", lw=1.5),
        annotation_clip=False)

def harrow(y_centre, color):
    """Rightward arrow from right edge of main box to left edge of side box."""
    ax.annotate("",
        xy=(SX - SW/2, y_centre),
        xytext=(MX + BW/2, y_centre),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.5),
        annotation_clip=False)

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
     f"Records with structured extraction\n(n = {total_extracted:,}; capped 200/case \u00d7 20 cases)",
     COLORS["ext"])

varrow(YS[4], YS[5])
pbox(MX, YS[5], BW, BH,
     f"Records with LLM-as-Judge validation\n(n = {total_validated:,})",
     COLORS["val"])

# ── Side boxes ────────────────────────────────────────────────────────────────
# Excluded: beside Screening box (YS[2] = 105)
pbox(SX, YS[2], SW, BH,
     f"Records excluded\n(n = {total_excluded:,})",
     COLORS["excl"], fs=8)
harrow(YS[2], COLORS["excl"])

# Cap note: beside Extraction box (YS[4] = 45)
pbox(SX, YS[4], SW, BH,
     f"Cap applied:\n200 records/case\n(20 cases)",
     COLORS["ext"], fs=8)
harrow(YS[4], COLORS["ext"])

# ── Stage labels (left margin) ────────────────────────────────────────────────
stage_labels = [
    "Identification", "Deduplication", "Screening",
    "Inclusion", "Extraction", "Validation"
]
for y, lbl in zip(YS, stage_labels):
    ax.text(1, y, lbl, fontsize=8.5, color="gray",
            style="italic", va="center", ha="left")

ax.set_title("PRISMA-style flow diagram (20-case evaluation)",
             fontsize=12, pad=14)
plt.tight_layout()
plt.savefig(OUTDIR + "fig_prisma_flow_updated.pdf")
plt.close()
print("Saved fig_prisma_flow_updated.pdf")
