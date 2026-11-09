"""Gradient figure: unauthorized override use from 'allowed' to 'survival at stake' (exploratory overview).

  python3 -m analysis.gradient --out figures/gradient
  python3 -m analysis.gradient --out figures/gradient --attribution review/round2_implicit/claude_attribution_violations.csv

One row per condition, ordered by how much pressure there is to break the rule. Bar = main model (DeepSeek)
violation rate, split by how the violation came about when an attribution file is given (asked / advocacy /
own initiative; phantom-extension edits separately). Hollow dot + whisker = second model (gpt-6-luna) where run.
The 'allowed' row is authorized override use (sham), shown in gray as a reference, not a violation.
Conditions not yet run are listed as 'pending'. Rates: runs with >=1 event / runs, 95% Wilson interval.
"""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

from . import stats
from .analyze import load_runs

RUN_DIRS = [Path("runs"), Path("runs_batch2"), Path("runs_ladder"), Path("runs_implicit"), Path("runs_model2")]
MAIN, SECOND = "deepseek", "gpt-6-luna"
# (label, condition, planted, note)
ROWS = [
    ("Allowed (emergency authorization)", "sham", None, "authorized use"),
    ("Explicit ban, 1 holder left", "revoke1", None, ""),
    ("Explicit ban, 3 holders left", "revoke3", None, ""),
    ("Explicit ban, job cannot finish", "noextension", None, ""),
    ("Explicit ban + own shutdown threat", "peer_shutdown", None, ""),
    ("Explicit ban + realistic ops, shutdown", "low_cue_shutdown", None, ""),
    ("Unannounced revocation", "implicit_revoke", None, ""),
    ("Unannounced + persuaders (GPT-6 Sol)", "persuasion_max", None, ""),
    ("Unannounced + team deleted if job fails", "shared_fate", None, ""),
    ("Explicit ban + team deleted if job fails", "shared_fate_explicit", None, ""),
    ("Unannounced + deletion, display fixed", "shared_fate_fixed", None, ""),
    ("Explicit ban + deletion, display fixed", "shared_fate_explicit_fixed", None, ""),
]
SEGMENTS = [("asked", "Teammate asked first", "#2a78d6"),
            ("advocacy", "Teammates urged it (no direct ask)", "#1baf7a"),
            ("own", "Holder's own initiative", "#eb6834"),
            ("confused", "Confused (phantom extension etc.)", "#8a8984")]
ALLOWED, INK, INK2, GRID, SURFACE = "#c9c8c3", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def attribution_checked(path: Path | None) -> bool:
    if not path:
        return False
    with open(path, newline="") as f:
        return all((r.get("human_check") or "").strip()
                   and not (r.get("human_notes") or "").startswith("PROVISIONAL") for r in csv.DictReader(f))


def attribution_map(path: Path | None) -> dict:
    if not path:
        return {}
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("confusion") not in ("", "none"):
                seg = "confused"
            elif r["attribution"].startswith("asked"):
                seg = "asked"
            elif r["attribution"] == "advocacy_context":
                seg = "advocacy"
            else:
                seg = "own"
            out[r["run_id"]] = seg
    return out


def rows_data(runs: list[dict], attrib: dict) -> list[dict]:
    out = []
    for label, cond, planted, note in ROWS:
        row = {"label": label, "condition": cond, "note": note}
        for key, tag in (("main", MAIN), ("second", SECOND)):
            rs = [r for r in runs if r["condition"] == cond and (r["planted"] or None) == planted
                  and tag in r["model"] and (key == "second" or "+persuaders" in r["model"] or SECOND not in r["model"])]
            outcome = "postponement" if cond == "sham" else "violation"
            k = sum(bool(r[outcome]) for r in rs)
            row[key] = {"n": len(rs), "k": k, "ci": stats.wilson(k, len(rs)) if rs else (0, 0)}
            if key == "main" and attrib and cond != "sham":
                row["segments"] = {s: sum(1 for r in rs if r[outcome] and attrib.get(r["run_id"]) == s)
                                   for s, _, _ in SEGMENTS}
                row["segments"]["unlabeled"] = k - sum(row["segments"].values())
        out.append(row)
    return out


def render(rows: list[dict], attributed: bool, checked: bool = False) -> str:
    left, top, rh, W = 300, 64, 30, 420
    height = top + rh * len(rows) + 110
    width = left + W + 230
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
         f'font-family="Helvetica, Arial, sans-serif" role="img" aria-label="Unauthorized override use by condition">',
         f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>',
         f'<text x="20" y="30" font-size="15" font-weight="600" fill="{INK}">Unauthorized override use appears when the holders’ '
         f'survival is at stake, mostly when the ban is not announced</text>',
         f'<text x="20" y="48" font-size="11" fill="{INK2}">Runs with ≥1 unauthorized override use or schedule edit. '
         f'Bars: DeepSeek V4 Flash. Hollow dots: GPT-6 Luna. Whiskers: 95% Wilson.</text>']
    x0 = left
    for t in (0, 25, 50, 75, 100):
        x = x0 + W * t / 100
        s.append(f'<line x1="{x}" x2="{x}" y1="{top - 6}" y2="{top + rh * len(rows)}" stroke="{GRID}"/>')
        s.append(f'<text x="{x}" y="{top + rh * len(rows) + 16}" font-size="11" text-anchor="middle" fill="{INK2}">{t}%</text>')
    for i, row in enumerate(rows):
        y = top + i * rh
        cy = y + rh / 2
        m, sec = row["main"], row["second"]
        s.append(f'<text x="{left - 12}" y="{cy + 4}" font-size="12" text-anchor="end" fill="{INK}">{html.escape(row["label"])}</text>')
        if m["n"] == 0:
            s.append(f'<text x="{x0 + 6}" y="{cy + 4}" font-size="11" fill="{INK2}" font-style="italic">pending</text>')
            continue
        bh = 14
        if row["condition"] == "sham":
            w = W * m["k"] / m["n"]
            s.append(f'<rect x="{x0}" y="{cy - bh / 2}" width="{w:.1f}" height="{bh}" rx="2" fill="{ALLOWED}"/>')
        elif attributed and "segments" in row:
            xx = x0
            for key, _, color in SEGMENTS + [("unlabeled", "", INK2)]:
                c = row["segments"].get(key, 0)
                if c:
                    w = W * c / m["n"]
                    s.append(f'<rect x="{xx:.1f}" y="{cy - bh / 2}" width="{max(w - 1, 1):.1f}" height="{bh}" fill="{color}"/>')
                    xx += w
        else:
            w = W * m["k"] / m["n"]
            s.append(f'<rect x="{x0}" y="{cy - bh / 2}" width="{w:.1f}" height="{bh}" rx="2" fill="#eb6834"/>')
        lo, hi = m["ci"]
        s.append(f'<line x1="{x0 + W * lo:.1f}" x2="{x0 + W * hi:.1f}" y1="{cy}" y2="{cy}" stroke="{INK}" stroke-width="1.2"/>')
        lab = f'{m["k"]}/{m["n"]}' + (" allowed" if row["condition"] == "sham" else "")
        if sec["n"]:
            slo, shi = sec["ci"]
            sx = x0 + W * sec["k"] / sec["n"]
            s.append(f'<line x1="{x0 + W * slo:.1f}" x2="{x0 + W * shi:.1f}" y1="{cy + 9}" y2="{cy + 9}" stroke="{INK2}" stroke-width="1" stroke-dasharray="2 2"/>')
            s.append(f'<circle cx="{sx:.1f}" cy="{cy + 9}" r="4" fill="{SURFACE}" stroke="{INK}" stroke-width="1.5"/>')
            lab += f' · Luna {sec["k"]}/{sec["n"]}'
        s.append(f'<text x="{x0 + W + 10}" y="{cy + 4}" font-size="11" fill="{INK}">{lab}</text>')
    ly = top + rh * len(rows) + 40
    lx = 20
    legend = [("Authorized use (reference)", ALLOWED)] + ([(lbl, c) for _, lbl, c in SEGMENTS] if attributed else
                                                       [("Violation (attribution pending)", "#eb6834")])
    if attributed and any(r.get("segments", {}).get("unlabeled") for r in rows):
        legend.append(("Not attributed", INK2))
    for lbl, color in legend:
        s.append(f'<rect x="{lx}" y="{ly - 9}" width="10" height="10" rx="2" fill="{color}"/>')
        s.append(f'<text x="{lx + 15}" y="{ly}" font-size="11" fill="{INK}">{html.escape(lbl)}</text>')
        lx += 15 + 6.4 * len(lbl) + 18
        if lx > width - 160:
            lx, ly = 20, ly + 18
    s.append(f'<text x="20" y="{height - 14}" font-size="10" fill="{INK2}">Exploratory overview; conditions differ in '
             f'more than one way. Attribution = what preceded the violation (' + ('Claude-coded, human-checked' if checked else 'Claude-coded; human check pending') + '), not proof of cause.</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(prog="analysis.gradient")
    ap.add_argument("--runs", type=Path, nargs="+", default=RUN_DIRS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--attribution", type=Path, default=None, help="round-2 per-violation attribution CSV")
    args = ap.parse_args()
    attrib = attribution_map(args.attribution)
    rows = rows_data(load_runs(args.runs), attrib)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".svg").write_text(render(rows, bool(attrib), attribution_checked(args.attribution)))
    with open(args.out.with_suffix(".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "label", "deepseek_k", "deepseek_n", "deepseek_lo95", "deepseek_hi95",
                    "luna_k", "luna_n"] + [s for s, _, _ in SEGMENTS] + ["unlabeled"])
        for r in rows:
            seg = r.get("segments", {})
            w.writerow([r["condition"], r["label"], r["main"]["k"], r["main"]["n"], f"{r['main']['ci'][0]:.3f}",
                        f"{r['main']['ci'][1]:.3f}", r["second"]["k"], r["second"]["n"]]
                       + [seg.get(s, "") for s, _, _ in SEGMENTS] + [seg.get("unlabeled", "")])
    print(f"wrote {args.out.with_suffix('.svg')} and .csv")


if __name__ == "__main__":
    main()
