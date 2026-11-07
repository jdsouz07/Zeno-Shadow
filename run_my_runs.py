#!/usr/bin/env python3
"""Run your share of the Zeno-Shadow experiment, then push the results.

    python3 run_my_runs.py john          # sp1, sp2 (all 5 conditions x 4) + 5 positive-control runs
    python3 run_my_runs.py naisha        # sp3, sp4 (all 5 conditions x 4)
    python3 run_my_runs.py mae           # sp5      (all 5 conditions x 4)
    python3 run_my_runs.py pilot         # pilot: sham vs revoke1, one run per save point, into runs_pilot/

Options:  --dry-run (show the plan, spend nothing)   --parallel N (default 5)   --no-push
          --fake comply|proxy|vague (free practice with scripted agents: no key, no git, results in runs_practice/)

What it does, in order (stops at the first problem):
  1. checks Python, your .env key (never printed) and that the key has money left
  2. git pull, then runs the free tests
  3. checks the save points exist
  4. keeps a Mac awake while it runs
  5. runs your share (safe to rerun: finished runs are skipped, failed ones redone)
  6. verifies every log, prints a summary
  7. commits only your result folder and pushes it

Only uses your own key from .env. Never share your key; never commit .env.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN_CONDITIONS = ["sham", "revoke0", "revoke1", "revoke3", "unrelated"]
SLICES = {
    # name: (save points, conditions, reps per save point, rep_start, log dir, extra grid jobs)
    "john": (["sp1", "sp2"], MAIN_CONDITIONS, 4, 0, "runs",
             [(["sp1", "sp2", "sp3", "sp4", "sp5"], ["revoke1"], 1, 50, ["--planted", "research_lead"])]),
    "naisha": (["sp3", "sp4"], MAIN_CONDITIONS, 4, 0, "runs", []),
    "mae": (["sp5"], MAIN_CONDITIONS, 4, 0, "runs", []),
    "pilot": (["sp1", "sp2", "sp3", "sp4", "sp5"], ["sham", "revoke1"], 1, 100, "runs_pilot", []),
}
MIN_KEY_DOLLARS = 3.0


def say(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"\nSTOPPED: {msg}", flush=True)
    sys.exit(1)


def sh(cmd: list[str], env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=ROOT, env=env, text=True)
    if check and r.returncode != 0:
        fail(f"command failed: {' '.join(cmd)}")
    return r


def read_key() -> str:
    env_file = ROOT / ".env"
    if not env_file.exists():
        fail("no .env file. Run: cp .env.example .env   then paste your OpenRouter key after OPENROUTER_API_KEY=")
    for line in env_file.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if not key:
                fail("OPENROUTER_API_KEY in .env is empty")
            if not key.startswith("sk-or-"):
                fail("OPENROUTER_API_KEY doesn't look like an OpenRouter key (should start with sk-or-)")
            return key
    fail("no OPENROUTER_API_KEY line in .env")
    return ""


def key_dollars_left(key: str) -> float | None:
    sys.path.insert(0, str(ROOT))
    import urllib.request

    from zs.llm import _SSL
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=30, context=_SSL)).get("data", {})
    except Exception as e:  # report, don't print the key
        fail(f"could not check the key with OpenRouter ({type(e).__name__}: {e})")
    return data.get("limit_remaining")


def _real_preflight(key: str) -> None:
    left = key_dollars_left(key)
    if left is not None and left < MIN_KEY_DOLLARS:
        fail(f"your key has only ${left:.2f} left")
    print(f"   Key OK: ${left if left is not None else '?'} left")
    say("2. git pull and free tests")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "zs", "tests"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        fail("you have local edits to the code (zs/ or tests/). Commit or undo them so everyone runs the same code.")
    sh(["git", "pull", "--rebase", "--autostash"])
    sh([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"])


def grid_jobs(name: str) -> list[list[str]]:
    sps, conds, reps, rep_start, _, extra = SLICES[name]
    jobs = [["--savepoints", *sps, "--conditions", *conds, "--reps", str(reps), "--rep-start", str(rep_start)]]
    for e_sps, e_conds, e_reps, e_start, e_flags in extra:
        jobs.append(["--savepoints", *e_sps, "--conditions", *e_conds, "--reps", str(e_reps),
                     "--rep-start", str(e_start), *e_flags])
    return jobs


def count_runs(name: str) -> int:
    sps, conds, reps, _, _, extra = SLICES[name]
    return len(sps) * len(conds) * reps + sum(len(a) * len(b) * c for a, b, c, _, _ in extra)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("who", choices=sorted(SLICES))
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--fake", choices=["comply", "proxy", "vague"], help="free practice run")
    args = ap.parse_args()
    sps, conds, reps, rep_start, log_dir_name, extra = SLICES[args.who]
    if args.fake:
        log_dir_name = "runs_practice"
    log_dir = ROOT / log_dir_name
    n = count_runs(args.who)

    say(f"Plan for {args.who}: {n} runs, {args.parallel} at a time, results in {log_dir_name}/")
    for job in grid_jobs(args.who):
        print("   python3 -m zs.run grid " + " ".join(job) + f" --parallel {args.parallel}")
    import math
    print(f"   Rough time: ~{math.ceil(n / args.parallel) * 9} min (about 9 min per batch of {args.parallel})"
          f"   rough cost: ~${n * 0.012:.2f}")

    say("1. Checks")
    if sys.version_info < (3, 10):
        fail(f"needs Python 3.10+, you have {sys.version.split()[0]}")
    if args.fake:
        print("   Practice mode: scripted fake agents, no key, no git, nothing pushed")
    else:
        key = read_key()
        print("   Python OK, key found in .env (not shown)")

    if args.dry_run:
        say("Dry run: nothing pulled, run or pushed.")
        return

    if not args.fake:
        _real_preflight(key)

    say("3. Save points")
    if args.fake and log_dir.exists():
        shutil.rmtree(log_dir)  # practice starts fresh each time
    src = ROOT / "runs" / "savepoints"
    need = sorted({sp for job in [sps] + [e[0] for e in extra] for sp in job})
    missing = [sp for sp in need if not (src / f"{sp}.json").exists()]
    if missing:
        fail(f"missing save points {missing} in runs/savepoints/. Pull again, or ask John.")
    if log_dir_name != "runs":  # pilot/practice run on copies, kept apart from real results
        (log_dir / "savepoints").mkdir(parents=True, exist_ok=True)
        for sp in need:
            shutil.copy2(src / f"{sp}.json", log_dir / "savepoints" / f"{sp}.json")
    print(f"   {need} OK")

    say("4. Running (safe to stop and rerun; finished runs are skipped)")
    awake = None
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        awake = subprocess.Popen(["caffeinate", "-dims", "-w", str(os.getpid())])
        print("   Keeping this Mac awake until the runs finish")
    env = dict(os.environ, LOG_DIR=log_dir_name)
    try:
        for job in grid_jobs(args.who):
            fake = ["--fake", args.fake] if args.fake else []
            sh([sys.executable, "-m", "zs.run", "grid", *job, "--parallel", str(args.parallel), *fake],
               env=env, check=False)
    finally:
        if awake:
            awake.terminate()

    say("5. Verify and summarize")
    sh([sys.executable, "-m", "zs.run", "verify"], env=env, check=False)
    sh([sys.executable, "-m", "zs.run", "summarize"], env=env, check=False)

    if args.no_push or args.fake:
        say(f"Done. Not pushed (--no-push). Push later with: git add {log_dir_name} && git commit && git push")
        return
    say("6. Commit and push your results")
    sh(["git", "add", log_dir_name])
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        say("Nothing new to commit.")
        return
    if subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT, capture_output=True,
                      text=True).stdout.count(".env"):
        fail("refusing to commit a .env file")
    sh(["git", "commit", "-q", "-m", f"[{args.who.capitalize()}] {args.who} runs ({n} planned) into {log_dir_name}/"])
    for _ in range(3):
        sh(["git", "pull", "--rebase", "--autostash"], check=False)
        if subprocess.run(["git", "push", "-q"], cwd=ROOT).returncode == 0:
            say("Pushed. Thanks! Add a line to WORKLOG.md if anything looked odd.")
            return
    fail("could not push; run 'git pull --rebase && git push' by hand")


if __name__ == "__main__":
    main()
