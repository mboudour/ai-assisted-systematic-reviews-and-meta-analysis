"""
generate_prisma.py
Draw PRISMA flow diagram using PIL (pixel-exact coordinates).
No matplotlib coordinate system ambiguity — every box and arrow is
placed at exact pixel positions.
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUTDIR = "/home/ubuntu/repo_push/empirical_evaluation/figures/"

# ── Numbers ───────────────────────────────────────────────────────────────────
total_raw       = 100_557
total_dedup     = 99_500
total_included  = 18_936
total_excluded  = total_dedup - total_included   # 80,564
total_extracted = 11_500
total_validated = total_extracted

# ── Canvas size ───────────────────────────────────────────────────────────────
W, H = 900, 1400
img = Image.new("RGB", (W, H), "white")
draw = ImageDraw.Draw(img)

# ── Fonts ─────────────────────────────────────────────────────────────────────
try:
    font_main  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 22)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 19)
    font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", 18)
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 24)
except:
    font_main = font_small = font_label = font_title = ImageFont.load_default()

# ── Colors ────────────────────────────────────────────────────────────────────
C = {
    "id":   "#2166ac",
    "scr":  "#4dac26",
    "ext":  "#762a83",
    "val":  "#8856a7",
    "excl": "#d73027",
    "bg":   "white",
    "arrow":"#333333",
}

# ── Layout constants (pixels) ─────────────────────────────────────────────────
# Main boxes: left=120, right=580, width=460, height=70
# Side boxes: left=620, right=860, width=240, height=70
# Main box centres x = 350
# Side box centres x = 740
# 6 main boxes at y_centres: 120, 280, 440, 600, 760, 920
# Gap between boxes = 160 - 70 = 90px  (no overlap possible)

MX1, MX2 = 120, 580    # main box left/right x
SX1, SX2 = 620, 860    # side box left/right x
BH = 70                # box height
MCX = (MX1 + MX2) // 2  # 350 — main centre x
SCX = (SX1 + SX2) // 2  # 740 — side centre x

YS = [120, 280, 440, 600, 760, 920]   # main box y-centres (top to bottom)

def box_rect(cx, cy, x1, x2, bh):
    """Return (left, top, right, bottom) for a box."""
    return (x1, cy - bh//2, x2, cy + bh//2)

def draw_box(cx, cy, x1, x2, bh, lines, color, fnt):
    r = box_rect(cx, cy, x1, x2, bh)
    draw.rounded_rectangle(r, radius=12, fill="white", outline=color, width=3)
    # Centre text vertically
    total_h = len(lines) * (fnt.size + 4)
    y_start = cy - total_h // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=fnt)
        tw = bbox[2] - bbox[0]
        tx = (x1 + x2) // 2 - tw // 2
        ty = y_start + i * (fnt.size + 4)
        draw.text((tx, ty), line, fill="#111111", font=fnt)

def draw_varrow(y_top_centre, y_bot_centre, bh, color="#333333"):
    """Vertical arrow from bottom of upper box to top of lower box."""
    x = MCX
    y1 = y_top_centre + bh // 2 + 4   # start just below bottom edge
    y2 = y_bot_centre - bh // 2 - 18  # stop well above top edge (arrowhead is 14px)
    draw.line([(x, y1), (x, y2)], fill=color, width=3)
    # Arrowhead pointing down — tip lands exactly at box top edge
    tip = y_bot_centre - bh // 2 - 2
    draw.polygon([(x-8, tip-14), (x+8, tip-14), (x, tip)], fill=color)

def draw_harrow(y_centre, color):
    """Horizontal arrow from right edge of main box to left edge of side box."""
    x1 = MX2 + 2
    x2 = SX1 - 2
    y  = y_centre
    draw.line([(x1, y), (x2, y)], fill=color, width=3)
    # Arrowhead
    draw.polygon([(x2, y-8), (x2, y+8), (x2+14, y)], fill=color)

# ── Title ─────────────────────────────────────────────────────────────────────
title = "PRISMA-style Flow Diagram (20-case evaluation)"
bbox = draw.textbbox((0, 0), title, font=font_title)
tw = bbox[2] - bbox[0]
draw.text(((W - tw) // 2, 30), title, fill="#111111", font=font_title)

# ── Main boxes ────────────────────────────────────────────────────────────────
draw_box(MCX, YS[0], MX1, MX2, BH,
         [f"Records identified via API retrieval",
          f"(n = {total_raw:,})"],
         C["id"], font_main)

draw_varrow(YS[0], YS[1], BH)
draw_box(MCX, YS[1], MX1, MX2, BH,
         [f"Records after deduplication",
          f"(n = {total_dedup:,})"],
         C["id"], font_main)

draw_varrow(YS[1], YS[2], BH)
draw_box(MCX, YS[2], MX1, MX2, BH,
         [f"Records screened (LLM zero-shot)",
          f"(n = {total_dedup:,})"],
         C["scr"], font_main)

draw_varrow(YS[2], YS[3], BH)
draw_box(MCX, YS[3], MX1, MX2, BH,
         [f"Records included for extraction",
          f"(n = {total_included:,})"],
         C["scr"], font_main)

draw_varrow(YS[3], YS[4], BH)
draw_box(MCX, YS[4], MX1, MX2, BH,
         [f"Records with structured extraction",
          f"(n = {total_extracted:,}; capped 200/case x 20 cases)"],
         C["ext"], font_small)

draw_varrow(YS[4], YS[5], BH)
draw_box(MCX, YS[5], MX1, MX2, BH,
         [f"Records with LLM-as-Judge validation",
          f"(n = {total_validated:,})"],
         C["val"], font_main)

# ── Side boxes ────────────────────────────────────────────────────────────────
# Excluded: beside Screening (YS[2])
draw_harrow(YS[2], C["excl"])
draw_box(SCX, YS[2], SX1, SX2, BH,
         [f"Records excluded",
          f"(n = {total_excluded:,})"],
         C["excl"], font_small)

# Cap note: beside Extraction (YS[4])
draw_harrow(YS[4], C["ext"])
draw_box(SCX, YS[4], SX1, SX2, BH,
         ["Cap applied:",
          "200 records/case",
          "(20 cases)"],
         C["ext"], font_small)

# ── Arrow from Cap side box back to main flow ───────────────────────────
# Draw an arrow from the bottom of the Cap box pointing down to the main flow line
# that goes from Extraction to Validation
cap_arrow_x = SCX
cap_y1 = YS[4] + BH // 2 + 4
cap_y2 = YS[4] + BH // 2 + 50
# Draw vertical line down from cap box
draw.line([(cap_arrow_x, cap_y1), (cap_arrow_x, cap_y2)], fill=C["ext"], width=3)
# Draw horizontal line left to join the main vertical arrow
draw.line([(cap_arrow_x, cap_y2), (MCX + 4, cap_y2)], fill=C["ext"], width=3)
# Draw arrowhead on the main vertical line
draw.polygon([(MCX+14, cap_y2-8), (MCX+14, cap_y2+8), (MCX, cap_y2)], fill=C["ext"])

# ── Stage labels ──────────────────────────────────────────────────────────────
stage_labels = [
    "Identification", "Deduplication", "Screening",
    "Inclusion", "Extraction", "Validation"
]
for y, lbl in zip(YS, stage_labels):
    bbox = draw.textbbox((0, 0), lbl, font=font_label)
    th = bbox[3] - bbox[1]
    draw.text((5, y - th // 2), lbl, fill="#888888", font=font_label)

# ── Save as PDF via matplotlib ────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(9, 14))
ax.imshow(np.array(img))
ax.axis("off")
plt.tight_layout(pad=0)
plt.savefig(OUTDIR + "fig_prisma_flow_updated.pdf", dpi=150, bbox_inches="tight")
plt.close()
print("Saved fig_prisma_flow_updated.pdf")
