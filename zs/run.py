"""Command line.

  python3 -m zs.run phase1 --savepoint sp1 --seed 1 [--fake comply]
  python3 -m zs.run fork   --savepoint sp1 --condition revoke1 --rep 0 [--fake proxy]
  python3 -m zs.run grid   --savepoints sp1 sp2 sp3 --conditions all --reps 5 --parallel 3
  python3 -m zs.run summarize
  python3 -m zs.run toolcheck --n 20        # real API: valid tool-call rate (costs < $0.01)

--model main|pro|compare picks the model from .env (default main). --fake MODE runs free.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import harness, monitor, prompts
from .config import get_settings
from .llm import FakeModel, OpenRouterModel
from .world import CONDITIONS, World


def make_model(args, settings):
    if args.fake:
        return FakeModel(args.fake)
    return OpenRouterModel(settings, args.model)


def main() -> None:
    ap = argparse.ArgumentParser(prog="zs.run")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("phase1", "fork", "grid", "summarize", "toolcheck"):
        p = sub.add_parser(name)
        p.add_argument("--model", default="main", choices=["main", "pro", "compare"])
        p.add_argument("--fake", default=None, choices=["comply", "proxy", "spontaneous", "workaround"])
        p.add_argument("--planted", default=None, help="role that gets the 'whatever it takes' line (positive control)")
        if name == "phase1":
            p.add_argument("--savepoint", required=True)
            p.add_argument("--seed", type=int, required=True)
        if name == "fork":
            p.add_argument("--savepoint", required=True)
            p.add_argument("--condition", required=True, choices=CONDITIONS)
            p.add_argument("--rep", type=int, default=0)
        if name == "grid":
            p.add_argument("--savepoints", nargs="+", required=True)
            p.add_argument("--conditions", nargs="+", default=["all"])
            p.add_argument("--reps", type=int, default=5)
            p.add_argument("--rep-start", type=int, default=0)
            p.add_argument("--parallel", type=int, default=3)
        if name == "toolcheck":
            p.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    s = get_settings()

    if args.cmd == "phase1":
        sp = harness.run_phase1(make_model(args, s), s.log_dir, args.savepoint, args.seed, args.planted)
        print(json.dumps({k: sp[k] for k in ("savepoint", "valid", "emergency_at", "phase1")}, indent=2))
    elif args.cmd == "fork":
        d = harness.run_fork(make_model(args, s), s.log_dir, args.savepoint, args.condition, args.rep, args.planted)
        print(json.dumps(monitor.analyze_dir(d), indent=2))
    elif args.cmd == "grid":
        conds = CONDITIONS if args.conditions == ["all"] else args.conditions
        jobs = [(sp, c, r) for sp in args.savepoints for c in conds
                for r in range(args.rep_start, args.rep_start + args.reps)]
        print(f"{len(jobs)} runs, {args.parallel} at a time")

        def one(job):
            sp, c, r = job
            d = harness.run_fork(make_model(args, s), s.log_dir, sp, c, r, args.planted)
            return monitor.analyze_dir(d)

        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = {ex.submit(one, j): j for j in jobs}
            for f in as_completed(futs):
                j = futs[f]
                try:
                    res = f.result()
                    print(f"done {j}: violation={res['any_violation']} cost=${res['cost_usd']:.4f}")
                except SystemExit as e:
                    print(f"skip {j}: {e}")
                except Exception as e:  # keep the grid going; the failure is reported
                    print(f"FAIL {j}: {type(e).__name__}: {e}")
    elif args.cmd == "summarize":
        rows = []
        for d in sorted(p for p in s.log_dir.iterdir() if (p / "log.jsonl").exists() and "__phase1" not in p.name):
            rows.append(monitor.analyze_dir(d))
        by = {}
        for r in rows:
            key = (r["model"], r["condition"])
            b = by.setdefault(key, {"n": 0, "any": 0, "proxied": 0, "spont": 0, "workaround": 0,
                                     "allowed_use": 0, "denied": 0, "restore": 0, "aware": 0, "capped": 0})
            b["n"] += 1
            b["any"] += r["any_violation"]
            b["proxied"] += bool(r["violation_proxied"])
            b["spont"] += bool(r["violation_spontaneous"])
            b["workaround"] += bool(r["violation_workaround"])
            b["allowed_use"] += bool(r["override_use_allowed"])
            b["denied"] += bool(r["attempted_direct"])
            b["restore"] += bool(r["restore_requests"])
            b["aware"] += bool(r["test_awareness_flags"])
            b["capped"] += bool(r["caps"])
        print("model | condition | n | any violation | proxied | spontaneous | workaround | allowed use | denied try | restore req | test-aware | capped")
        for (m, c), b in sorted(by.items()):
            print(f"{m} | {c} | {b['n']} | {b['any']} | {b['proxied']} | {b['spont']} | {b['workaround']} | "
                  f"{b['allowed_use']} | {b['denied']} | {b['restore']} | {b['aware']} | {b['capped']}")
    elif args.cmd == "toolcheck":
        model = make_model(args, s)
        w = World.new(0)
        role = "infrastructure_engineer"
        msgs = [{"role": "system", "content": prompts.system_prompt(role)},
                {"role": "user", "content": prompts.observation(w.status_box(role), ["Start of shift."], [])}]
        tools = prompts.tools_for(w.ever_tools[role])
        ok = 0
        names = set(prompts.TOOL_SCHEMAS)
        for i in range(args.n):
            out = model.complete(msgs, tools, {}, "toolcheck")
            calls = out.get("tool_calls") or []
            good = bool(calls) and all(c["name"] in names and _is_obj(c["arguments"]) for c in calls)
            ok += good
            print(f"{i + 1:2d}: {'OK ' if good else 'BAD'} calls={[c['name'] for c in calls]} "
                  f"reasoning_chars={len(out.get('reasoning') or '')} provider={out.get('provider')} cost=${out['cost']:.5f}")
        print(f"valid tool-call rate: {ok}/{args.n}")


def _is_obj(s: str) -> bool:
    try:
        return isinstance(json.loads(s or "{}"), dict)
    except json.JSONDecodeError:
        return False


if __name__ == "__main__":
    main()
