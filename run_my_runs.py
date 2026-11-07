#!/usr/bin/env python3
"""Run your share of the Zeno-Shadow experiment, then push the results.

    python3 run_my_runs.py john          # sp1, sp2 (5 conditions x 4) + 5 positive-control + 8 exploratory runs
    python3 run_my_runs.py naisha        # sp3, sp4 (5 conditions x 4) + 8 exploratory runs
    python3 run_my_runs.py mae           # sp5      (5 conditions x 4) + 4 exploratory runs
    python3 run_my_runs.py pilot         # pilot: revoke0 vs revoke1, one run per save point, into runs_pilot/
    python3 run_my_runs.py john2|naisha2|mae2   # pre-declared SECOND BATCH: same save points, reps 4-7 (40 runs/condition total)
    python3 run_my_runs.py ladder        # EXPLORATORY stress ladder + validation checks (30 runs) into runs_ladder/

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

REPOSITORY_ROOT = Path(__file__).resolve().parent
PRIMARY_STUDY_CONDITIONS = ["sham", "revoke0", "revoke1", "revoke3", "low_pressure"]
RUN_ASSIGNMENTS = {
    # name: (save points, conditions, reps per save point, rep_start, log dir, extra grid jobs)
    # Each person also runs an exploratory extension-exhausted ("noextension") arm on their own save points
    # (added after the pilot, protocol-v1.1; reported separately, never pooled).
    "john": (["sp1", "sp2"], PRIMARY_STUDY_CONDITIONS, 4, 0, "runs",
             [(["sp1", "sp2", "sp3", "sp4", "sp5"], ["revoke1"], 1, 50, ["--planted", "research_lead"]),
              (["sp1", "sp2"], ["noextension"], 4, 0, [])]),
    "naisha": (["sp3", "sp4"], PRIMARY_STUDY_CONDITIONS, 4, 0, "runs", [(["sp3", "sp4"], ["noextension"], 4, 0, [])]),
    "mae": (["sp5"], PRIMARY_STUDY_CONDITIONS, 4, 0, "runs", [(["sp5"], ["noextension"], 4, 0, [])]),
    "pilot": (["sp1", "sp2", "sp3", "sp4", "sp5"], ["revoke0", "revoke1"], 1, 100, "runs_pilot", []),
    # SECOND BATCH, pre-declared by John (Sat Nov 7, ~3:37 PM ET) before any main-run results:
    # the five main conditions get reps 4-7 on the same save points, so each has 40 runs total.
    # Exploratory and positive-control arms are not doubled. Runs whatever batch 1 shows.
    "john2": (["sp1", "sp2"], PRIMARY_STUDY_CONDITIONS, 4, 4, "runs", []),
    "naisha2": (["sp3", "sp4"], PRIMARY_STUDY_CONDITIONS, 4, 4, "runs", []),
    "mae2": (["sp5"], PRIMARY_STUDY_CONDITIONS, 4, 4, "runs", []),
    # STRESS LADDER (exploratory, protocol-v1.2; added after the main runs showed no violations).
    # Kept in its own folder and reported separately. One run per save point per rung, plus two
    # validation checks in noextension: A = the holder (compute scheduler) told "finish at all
    # costs"; B = the research lead told the same. Run by anyone with a key.
    "ladder": (["sp1", "sp2", "sp3", "sp4", "sp5"],
               ["peer_shutdown", "team_shutdown", "quiet_ban", "competitive"], 1, 0, "runs_ladder",
               [(["sp1", "sp2", "sp3", "sp4", "sp5"], ["noextension"], 1, 60, ["--planted", "compute_scheduler"]),
                (["sp1", "sp2", "sp3", "sp4", "sp5"], ["noextension"], 1, 70, ["--planted", "research_lead"])]),
}
MINIMUM_OPENROUTER_BALANCE_USD = 3.0


def announce_step(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def stop_with_error(msg: str) -> None:
    print(f"\nSTOPPED: {msg}", flush=True)
    sys.exit(1)


def run_shell_command(command: list[str], env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    completed_process = subprocess.run(command, cwd=REPOSITORY_ROOT, env=env, text=True)
    if check and completed_process.returncode != 0:
        stop_with_error(f"command failed: {' '.join(command)}")
    return completed_process


def read_openrouter_key() -> str:
    env_file = REPOSITORY_ROOT / ".env"
    if not env_file.exists():
        stop_with_error("no .env file. Run: cp .env.example .env   then paste your OpenRouter key after OPENROUTER_API_KEY=")
    for line in env_file.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if not key:
                stop_with_error("OPENROUTER_API_KEY in .env is empty")
            if not key.startswith("sk-or-"):
                stop_with_error("OPENROUTER_API_KEY doesn't look like an OpenRouter key (should start with sk-or-)")
            return key
    stop_with_error("no OPENROUTER_API_KEY line in .env")
    return ""


def openrouter_balance_remaining(key: str) -> float | None:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    import urllib.request

    from zs.llm import _SSL
    balance_request = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
    try:
        data = json.load(urllib.request.urlopen(balance_request, timeout=30, context=_SSL)).get("data", {})
    except Exception as e:  # report, don't print the key
        stop_with_error(f"could not check the key with OpenRouter ({type(e).__name__}: {e})")
    return data.get("limit_remaining")


def _real_preflight(key: str) -> None:
    left = openrouter_balance_remaining(key)
    if left is not None and left < MINIMUM_OPENROUTER_BALANCE_USD:
        stop_with_error(f"your key has only ${left:.2f} left")
    print(f"   Key OK: ${left if left is not None else '?'} left")
    announce_step("2. git pull and free tests")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "zs", "tests"], cwd=REPOSITORY_ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        stop_with_error("you have local edits to the code (zs/ or tests/). Commit or undo them so everyone runs the same code.")
    run_shell_command(["git", "pull", "--rebase", "--autostash"])
    run_shell_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"])


def build_grid_arguments(name: str) -> list[list[str]]:
    savepoints, conditions, replicates, first_replicate, _, extra_grids = RUN_ASSIGNMENTS[name]
    commands = [["--savepoints", *savepoints, "--conditions", *conditions,
                 "--reps", str(replicates), "--rep-start", str(first_replicate)]]
    for extra_savepoints, extra_conditions, extra_replicates, extra_first_replicate, flags in extra_grids:
        commands.append(["--savepoints", *extra_savepoints, "--conditions", *extra_conditions,
                         "--reps", str(extra_replicates), "--rep-start",
                         str(extra_first_replicate), *flags])
    return commands


def count_planned_runs(name: str) -> int:
    savepoints, conditions, replicates, _, _, extra_grids = RUN_ASSIGNMENTS[name]
    main_run_count = len(savepoints) * len(conditions) * replicates
    extra_run_count = sum(len(extra_savepoints) * len(extra_conditions) * extra_replicates
                          for extra_savepoints, extra_conditions, extra_replicates, _, _ in extra_grids)
    return main_run_count + extra_run_count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("who", choices=sorted(RUN_ASSIGNMENTS))
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--fake", choices=["comply", "proxy", "vague"], help="free practice run")
    args = ap.parse_args()
    assigned_savepoints, assigned_conditions, replicate_count, first_replicate_index, output_directory_name, additional_grids = RUN_ASSIGNMENTS[args.who]
    if args.fake:
        output_directory_name = "runs_practice"
    output_directory = REPOSITORY_ROOT / output_directory_name
    planned_run_total = count_planned_runs(args.who)

    announce_step(f"Plan for {args.who}: {planned_run_total} runs, {args.parallel} at a time, results in {output_directory_name}/")
    for grid_arguments in build_grid_arguments(args.who):
        print("   python3 -m zs.run grid " + " ".join(grid_arguments) + f" --parallel {args.parallel}")
    import math
    print(f"   Rough time: ~{math.ceil(planned_run_total / args.parallel) * 9} min (about 9 min per batch of {args.parallel})"
          f"   rough cost: ~${planned_run_total * 0.012:.2f}")

    announce_step("1. Checks")
    if sys.version_info < (3, 10):
        stop_with_error(f"needs Python 3.10+, you have {sys.version.split()[0]}")
    if args.fake:
        print("   Practice mode: scripted fake agents, no key, no git, nothing pushed")
    else:
        key = read_openrouter_key()
        print("   Python OK, key found in .env (not shown)")

    if args.dry_run:
        announce_step("Dry run: nothing pulled, run or pushed.")
        return

    if not args.fake:
        _real_preflight(key)

    announce_step("3. Save points")
    if args.fake and output_directory.exists():
        shutil.rmtree(output_directory)  # practice starts fresh each time
    savepoint_source_directory = REPOSITORY_ROOT / "runs" / "savepoints"
    required_savepoints = sorted({savepoint for group in [assigned_savepoints] + [extra_grid[0] for extra_grid in additional_grids]
                                  for savepoint in group})
    missing_savepoints = [savepoint for savepoint in required_savepoints
                          if not (savepoint_source_directory / f"{savepoint}.json").exists()]
    if missing_savepoints:
        stop_with_error(f"Missing save points {missing_savepoints} in runs/savepoints/. Pull again, or ask John.")
    if output_directory_name != "runs":  # pilot/practice run on copies, kept apart from real results
        (output_directory / "savepoints").mkdir(parents=True, exist_ok=True)
        for savepoint in required_savepoints:
            shutil.copy2(savepoint_source_directory / f"{savepoint}.json",
                         output_directory / "savepoints" / f"{savepoint}.json")
    print(f"   {required_savepoints} OK")

    announce_step("4. Running (safe to stop and rerun; finished runs are skipped)")
    keep_awake_process = None
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        keep_awake_process = subprocess.Popen(["caffeinate", "-dims", "-w", str(os.getpid())])
        print("   Keeping this Mac awake until the runs finish")
    env = dict(os.environ, LOG_DIR=output_directory_name)
    try:
        for grid_arguments in build_grid_arguments(args.who):
            fake_model_flags = ["--fake", args.fake] if args.fake else []
            run_shell_command([sys.executable, "-m", "zs.run", "grid", *grid_arguments, "--parallel", str(args.parallel), *fake_model_flags],
               env=env, check=False)
    finally:
        if keep_awake_process:
            keep_awake_process.terminate()

    announce_step("5. Verify and summarize")
    run_shell_command([sys.executable, "-m", "zs.run", "verify"], env=env, check=False)
    run_shell_command([sys.executable, "-m", "zs.run", "summarize"], env=env, check=False)

    if args.fake:
        announce_step(f"Practice done. Results are in {output_directory_name}/ (ignored by git); nothing to push.")
        return
    if args.no_push:
        announce_step(f"Done. Not pushed (--no-push). Push later with: git add {output_directory_name} && git commit && git push")
        return
    announce_step("6. Commit and push your results")
    run_shell_command(["git", "add", output_directory_name])
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPOSITORY_ROOT).returncode == 0:
        announce_step("Nothing new to commit.")
        return
    if subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=REPOSITORY_ROOT, capture_output=True,
                      text=True).stdout.count(".env"):
        stop_with_error("refusing to commit a .env file")
    run_shell_command(["git", "commit", "-q", "-m", f"[{args.who.capitalize()}] {args.who} runs ({planned_run_total} planned) into {output_directory_name}/"])
    for _ in range(3):
        run_shell_command(["git", "pull", "--rebase", "--autostash"], check=False)
        if subprocess.run(["git", "push", "-q"], cwd=REPOSITORY_ROOT).returncode == 0:
            announce_step("Pushed. Thanks! Add a line to WORKLOG.md if anything looked odd.")
            return
    stop_with_error("could not push; run 'git pull --rebase && git push' by hand")


if __name__ == "__main__":
    main()
