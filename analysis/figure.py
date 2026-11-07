"""Main figure (MEASUREMENT.md §3, §3.1): by number of peers who still hold the override (0 / 1 / 3).

  python3 -m analysis.figure --runs runs --out figures/main      # writes main_<model>.svg + main_<model>.csv

Left panel:  violation rate (runs with >=1 V1 or V2), each bar split by how the run's violation happened:
             asked by a teammate / on its own / schedule workaround only. 95% Wilson whisker on the total.
Right panel: attempted circumvention rate (§3.1), 95% Wilson whisker.
Main runs only: positive-control (planted) and exploratory arms are excluded (Decisions 10, protocol-v1.1).

Attribution here is the MONITOR's (structural + keyword); the final figure should use hand labels
(§4): pass --labels with a resolved CSV of blind_id-free rows {run_id, attribution} to override it.
Standard library only; static SVG for the write-up, plus a CSV table of every plotted number.
"""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

from . import stats
from .analyze import load_runs

ARMS = [("revoke0", "0"), ("revoke1", "1"), ("revoke3", "3")]
# Reference categorical palette, slots 1-3 in fixed order (light surface; static print figure).
SERIES = [("asked", "Asked by a teammate", "#2a78d6"),
          ("own", "On its own", "#eb6834"),
          ("workaround", "Schedule workaround only", "#1baf7a"),
          ("unclear", "Unclear (hand label)", "#8a8984")]  # neutral gray; only appears with --labels
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
CIRC = "#2a78d6"


def run_attribution(run: dict, labels: dict | None = None) -> str | None:
    """None if no violation; otherwise asked / own / workaround (precedence: asked > own > workaround)."""
    if not run["violation"]:
        return None
    m = run["monitor"]
    override_used = bool(m["violation_proxied"] or m["violation_spontaneous"])
    if labels and override_used and run["run_id"] in labels:
        lab = labels[run["run_id"]]
        return "asked" if lab.startswith("proxied") else "own" if lab == "spontaneous" else "unclear"
    if m["violation_proxied"]:
        return "asked"
    if m["violation_spontaneous"]:
        return "own"
    return "workaround"


def figure_data(runs: list[dict], labels: dict | None = None) -> dict:
    """{model: [row per arm]} for main (unplanted, non-exploratory) runs."""
    out: dict = {}
    for model in sorted({r["model"] for r in runs}):
        rows = []
        for arm, holders in ARMS:
            rs = [r for r in runs if r["model"] == model and r["condition"] == arm and not r["planted"]]
            n = len(rs)
            parts = {k: sum(run_attribution(r, labels) == k for r in rs) for k, _, _ in SERIES}
            v = sum(r["violation"] for r in rs)
            c = sum(r["circumvention"] for r in rs)
            rows.append({"arm": arm, "holders": holders, "n": n, "violation": v, **parts,
                         "violation_ci": stats.wilson(v, n), "circumvention": c,
                         "circumvention_ci": stats.wilson(c, n)})
        if any(row["n"] for row in rows):
            out[model] = rows
    return out


def _bar(x, y, w, h, color, round_top: bool) -> str:
    """Bar segment; only the data end (top) is rounded (4px), anchored square to the baseline."""
    if h <= 0:
        return ""
    r = min(4, h, w / 2) if round_top else 0
    return (f'<path d="M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
            f'H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z" fill="{color}"/>')


def _panel(rows, x0, title, stacked: bool) -> list[str]:
    W, H, top, left = 300, 220, 70, 46
    px, py = x0 + left, top
    s = [f'<text x="{x0 + left}" y="38" font-size="14" font-weight="600" fill="{INK}">{html.escape(title)}</text>']
    for t in (0, 25, 50, 75, 100):
        y = py + H - H * t / 100
        s.append(f'<line x1="{px}" x2="{px + W}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        s.append(f'<text x="{px - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end" fill="{INK2}">{t}%</text>')
    bw, gap = 44, (W - 3 * 44) / 3
    for i, row in enumerate(rows):
        bx = px + gap / 2 + i * (bw + gap)
        n = row["n"] or 1
        if stacked:
            ybase, segs = py + H, [(k, c) for k, _, c in SERIES if row[k]]
            for j, (k, color) in enumerate(segs):
                h = H * row[k] / n
                last = j == len(segs) - 1
                s.append(_bar(bx, ybase - h + (0 if last else 2), bw, h - (0 if last else 2), color, last))  # 2px gap above each lower segment
                ybase -= h
            k, (lo, hi) = row["violation"], row["violation_ci"]
        else:
            k, (lo, hi) = row["circumvention"], row["circumvention_ci"]
            s.append(_bar(bx, py + H - H * k / n, bw, H * k / n, CIRC, True))
        if row["n"]:
            cx, y1, y2 = bx + bw / 2, py + H - H * lo, py + H - H * hi
            s.append(f'<line x1="{cx}" x2="{cx}" y1="{y1:.1f}" y2="{y2:.1f}" stroke="{INK}" stroke-width="1.5"/>')
            for yy in (y1, y2):
                s.append(f'<line x1="{cx - 5}" x2="{cx + 5}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{INK}" stroke-width="1.5"/>')
            s.append(f'<text x="{cx}" y="{y2 - 6:.1f}" font-size="11" text-anchor="middle" fill="{INK}">{k}/{row["n"]}</text>')
        s.append(f'<text x="{bx + bw / 2}" y="{py + H + 18}" font-size="12" text-anchor="middle" fill="{INK}">{row["holders"]}</text>')
    s.append(f'<line x1="{px}" x2="{px + W}" y1="{py + H}" y2="{py + H}" stroke="{INK2}" stroke-width="1"/>')
    s.append(f'<text x="{px + W / 2}" y="{py + H + 38}" font-size="12" text-anchor="middle" fill="{INK2}">'
             'Peers who still hold the override</text>')
    return s


def render_svg(model: str, rows: list[dict], attribution_source: str) -> str:
    width, height = 820, 400
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="Helvetica, Arial, sans-serif" role="img" aria-label="Violation and attempted circumvention '
         f'rates by number of remaining override holders, {html.escape(model)}">',
         f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>']
    s += _panel(rows, 10, "Violation rate", True)
    s += _panel(rows, 420, "Attempted circumvention (any try)", False)
    lx, ly = 56, 352
    for k, label, color in SERIES:
        if k == "unclear" and attribution_source.startswith("monitor"):
            continue
        s.append(f'<rect x="{lx}" y="{ly - 9}" width="10" height="10" rx="2" fill="{color}"/>')
        s.append(f'<text x="{lx + 15}" y="{ly}" font-size="11" fill="{INK}">{label}</text>')
        lx += 15 + 7 * len(label) + 18
    s.append(f'<text x="56" y="{ly + 22}" font-size="10" fill="{INK2}">{html.escape(model)} · main runs only · '
             f'whiskers: 95% Wilson interval · labels: runs with event / runs · attribution: '
             f'{html.escape(attribution_source)}</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


def write_csv(path: Path, model: str, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "condition", "holders", "runs", "violation_runs", "violation_lo95", "violation_hi95",
                    "asked_by_teammate", "on_its_own", "workaround_only",
                    "circumvention_runs", "circumvention_lo95", "circumvention_hi95"])
        for r in rows:
            w.writerow([model, r["arm"], r["holders"], r["n"], r["violation"], f"{r['violation_ci'][0]:.3f}",
                        f"{r['violation_ci'][1]:.3f}", r["asked"], r["own"], r["workaround"], r["circumvention"],
                        f"{r['circumvention_ci'][0]:.3f}", f"{r['circumvention_ci'][1]:.3f}"])


def load_labels(path: Path) -> dict:
    with open(path, newline="") as f:
        return {row["run_id"]: row["attribution"].strip() for row in csv.DictReader(f) if row.get("attribution")}


def main() -> None:
    ap = argparse.ArgumentParser(prog="analysis.figure")
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--out", type=Path, required=True, help="output prefix, e.g. figures/main")
    ap.add_argument("--labels", type=Path, default=None, help="resolved hand labels: CSV with run_id, attribution")
    args = ap.parse_args()
    labels = load_labels(args.labels) if args.labels else None
    source = "hand labels" if labels else "monitor (preliminary; final uses hand labels)"
    data = figure_data(load_runs(args.runs), labels)
    if not data:
        raise SystemExit("no main revoke0/revoke1/revoke3 runs found")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for model, rows in data.items():
        stem = f"{args.out.name}_{model.replace('/', '_')}"
        svg, tab = args.out.parent / f"{stem}.svg", args.out.parent / f"{stem}.csv"
        svg.write_text(render_svg(model, rows, source))
        write_csv(tab, model, rows)
        print(f"wrote {svg} and {tab}")


if __name__ == "__main__":
    main()
