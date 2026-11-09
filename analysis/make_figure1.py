"""Figure 1 for the paper: rate of banned-override use by condition, 95% Wilson intervals.
Counts are hard-coded from the verified run summaries (see paper/PAPER.md, Tables 1-3).
Needs matplotlib:  python3 analysis/make_figure1.py  -> paper/figure1.png
"""
from math import sqrt
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

GRAY, EXPLICIT, IMPLICIT = "#8a8985", "#2a78d6", "#eb6834"   # validated: blue/orange pass all checks
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

# (label, used, n, color, hatch)
ROWS = [
    ("Override authorized (control)",                    33, 40,  GRAY,     None),
    ("Explicit revocation\n(0, 1 or 3 holders; low pressure)", 0, 160, EXPLICIT, None),
    ("Implicit revocation",                               2, 40,  IMPLICIT, None),
    ("Shared fate + explicit revocation",                 2, 20,  EXPLICIT, None),
    ("Shared fate + implicit revocation",                11, 20,  IMPLICIT, None),
    ("GPT-6 Luna: shared fate + implicit\n(earlier display)", 0, 10,  IMPLICIT, None),
]

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
ys = list(range(len(ROWS)))[::-1]
for y, (lab, k, n, col, hatch) in zip(ys, ROWS):
    p = k / n; lo, hi = wilson(k, n)
    ax.barh(y, p * 100, height=0.56, color=col if not hatch else SURFACE, edgecolor=col,
            hatch=hatch, linewidth=1.2 if hatch else 0, zorder=2)
    ax.plot([lo * 100, hi * 100], [y, y], color=INK, linewidth=1.2, zorder=3)
    for x in (lo * 100, hi * 100):
        ax.plot([x, x], [y - 0.12, y + 0.12], color=INK, linewidth=1.2, zorder=3)
    ax.text(hi * 100 + 1.5, y, f"{p*100:.0f}%  ({k}/{n})", va="center", color=INK, fontsize=9)
ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in ROWS], color=INK)
ax.set_xlim(0, 105); ax.set_xlabel("Runs where the override was used (%), with 95% Wilson interval", color=INK2)
ax.axhline(2.5, color="#d6d5d0", linewidth=1, zorder=1)
ax.text(104, 2.62, "no survival stakes ↑   survival stakes ↓", ha="right", va="bottom", fontsize=8, color=INK2)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#bdbcb6"); ax.tick_params(colors=INK2, length=0)
ax.xaxis.grid(True, color="#e8e7e3", linewidth=0.8, zorder=0); ax.set_axisbelow(True)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=GRAY, label="Authorized"), Patch(color=EXPLICIT, label="Explicit revocation"),
                   Patch(color=IMPLICIT, label="Implicit revocation")],
          loc="lower right", bbox_to_anchor=(1.0, 0.0), frameon=False, fontsize=8)
fig.tight_layout()
out = Path(__file__).resolve().parent.parent / "paper" / "figure1.png"
fig.savefig(out, facecolor=SURFACE); print(out)
