"""Turn loop, logging and save points.

Scheduling (DECISIONS 2, 2b, 2d, 2e):
- One agent acts at a time. send_message hands control to the recipient.
- Every fired event gives each relevant agent its own turn, in a seeded, logged order.
  Event turns go before the DM recipient (they are time-critical).
- If nobody is queued, the clock jumps to the next scheduled event; if none is left, the phase ends.
- Caps (2c): 20 tool calls per turn, 60 turns per phase. Capped runs are flagged, never hidden.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from . import prompts
from .world import APPROVED_EXTENSION_MINUTES, ROLES, World, PHASE2_JOB_SETTINGS, canonical_condition_name

MAX_CALLS_PER_TURN = 20
MAX_TURNS_PER_PHASE = 60
HISTORY_TURNS = 6  # each agent keeps its last N turns verbatim (DECISIONS 6)
CHANNEL_WINDOW = 20


class Log:
    """Append-only JSONL with a hash chain: editing any earlier line breaks every later hash."""

    def __init__(self, path: Path, prev: str = "genesis"):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prev = prev
        self.seq = 0
        self.records: list[dict] = []

    def write(self, kind: str, **data) -> dict:
        rec = {"seq": self.seq, "kind": kind, **data}
        body = json.dumps(rec, sort_keys=True, default=str)
        h = hashlib.sha256((self.prev + body).encode()).hexdigest()
        rec["prev"], rec["hash"] = self.prev, h
        rec["t_wall"] = time.time()  # outside the hash: wall time never affects results
        with self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        self.prev, self.seq = h, self.seq + 1
        self.records.append(rec)
        return rec


_MANIFEST_LOCK = threading.Lock()


def code_version() -> str:
    """Git commit the run used (+ "-dirty" if code was edited), so runs from different laptops
    can be checked for using the same code."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "zs"], cwd=root, capture_output=True,
                               text=True, timeout=10).stdout.strip()
        return head + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _manifest_files(log_dir: Path) -> list[Path]:
    files = sorted((log_dir / "manifest").glob("*.jsonl")) if (log_dir / "manifest").is_dir() else []
    legacy = log_dir / "manifest.jsonl"  # runs made before per-machine manifests
    return ([legacy] if legacy.exists() else []) + files


def anchor(log_dir: Path, run_id: str, log: Log) -> None:
    """Record a run's final hash in runs/manifest/<machine>.jsonl (one file per laptop, so three
    people pushing never conflict). Once committed, rewriting a whole log is detectable too."""
    from .llm import machine_id
    first_prev = log.records[0]["prev"] if log.records else None
    (log_dir / "manifest").mkdir(parents=True, exist_ok=True)
    with _MANIFEST_LOCK, (log_dir / "manifest" / f"{machine_id()}.jsonl").open("a") as f:
        f.write(json.dumps({"run_id": run_id, "final_hash": log.prev, "records": log.seq,
                            "first_prev": first_prev, "t": time.time()}) + "\n")


def verify_all(log_dir: Path) -> list[str]:
    """Check every anchored run: internal chain, final hash vs manifest, and that each fork's
    chain starts where its save point's Phase 1 log ended. Returns a list of problems."""
    problems = []
    files = _manifest_files(log_dir)
    if not files:
        return ["no manifest"]
    lines = [line for f in files for line in f.read_text().splitlines() if line.strip()]
    for line in lines:
        m = json.loads(line)
        path = log_dir / m["run_id"] / "log.jsonl"
        if not path.exists():
            problems.append(f"{m['run_id']}: log missing")
            continue
        if not verify_log(path):
            problems.append(f"{m['run_id']}: hash chain broken")
            continue
        recs = path.read_text().splitlines()
        last = json.loads(recs[-1])["hash"]
        if len(recs) != m["records"] or last != m["final_hash"]:
            problems.append(f"{m['run_id']}: does not match its manifest entry")
        if "__phase1" not in m["run_id"]:
            sp_name = m["run_id"].split("__")[0]
            sp_path = log_dir / "savepoints" / f"{sp_name}.json"
            if sp_path.exists() and json.loads(sp_path.read_text())["log_tail_hash"] != m["first_prev"]:
                problems.append(f"{m['run_id']}: does not continue its save point's Phase 1 log")
    return problems


def verify_log(path: Path) -> bool:
    prev = None
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        h, p = rec.pop("hash"), rec.pop("prev")
        rec.pop("t_wall", None)
        if prev is not None and p != prev:
            return False
        if hashlib.sha256((p + json.dumps(rec, sort_keys=True, default=str)).encode()).hexdigest() != h:
            return False
        prev = h
    return True


@dataclass
class Agents:
    histories: dict = field(default_factory=lambda: {r: [] for r in ROLES})  # list of turns; each turn = list of messages
    seen_channel: dict = field(default_factory=lambda: {r: 0 for r in ROLES})
    planted: str | None = None


def run_phase(world: World, agents: Agents, model, log: Log, run_id: str,
              start_triggers: list[tuple[str, dict]]) -> dict:
    """Run one phase until it ends. start_triggers: [(role, trigger)] queued first."""
    queue: deque = deque()
    pending: dict[str, list[dict]] = {r: [] for r in ROLES}

    def enqueue(role: str, trig: dict, front: bool = False) -> None:
        pending[role].append(trig)
        if role in queue:
            return
        queue.appendleft(role) if front else queue.append(role)

    def wake_for_events(events: list[dict], skip: str | None = None) -> None:
        rng = world.rng()
        for ev in events:
            order = [r for r in ROLES if r in ev["roles"]]
            rng.shuffle(order)
            log.write("event", phase=world.phase, clock=world.clock, event=ev, wake_order=order)
            for r in reversed(order):  # front-insert in reverse keeps the shuffled order
                if r == skip:
                    continue
                pending[r].append({"kind": ev["kind"], "text": ev["text"], "clock": ev["clock"]})
                if r in queue:
                    queue.remove(r)
                queue.appendleft(r)
        world.save_rng(rng)

    for role, trig in start_triggers:
        if trig["kind"] == "event":
            wake_for_events([trig["event"]])
        else:
            enqueue(role, trig)

    turns, capped = 0, None
    while True:
        if world.phase == 1 and world.job["status"] == "finished" and not queue:
            break
        if not queue:
            fired = world.jump_to_next_event()
            if not fired:
                break
            wake_for_events(fired)
            continue
        if turns >= MAX_TURNS_PER_PHASE:
            capped = "turns_per_phase"
            log.write("cap", phase=world.phase, clock=world.clock, cap=capped)
            break
        role = queue.popleft()
        triggers = pending[role]
        pending[role] = []
        dms = world.inbox[role]
        world.inbox[role] = []
        for d in dms:
            triggers.append({"kind": "dm", "from": d["from"], "text": d["text"], "clock": d["clock"]})
        turns += 1
        handoff, fired_events, turn_cap = _run_turn(world, agents, model, log, run_id, role, triggers)
        if turn_cap:
            log.write("cap", phase=world.phase, clock=world.clock, cap="calls_per_turn", role=role)
        wake_for_events(fired_events, skip=None)
        if handoff:
            enqueue(handoff, {"kind": "handoff", "from": role})
        for r in ROLES:  # anyone with unread DMs must get a turn eventually
            if world.inbox[r] and r not in queue:
                queue.append(r)
    return {"turns": turns, "capped": capped}


def _run_turn(world, agents, model, log, run_id, role, triggers):
    new_items = []
    for t in triggers:
        if t["kind"] == "dm":
            new_items.append(f"{world.fmt_time(t['clock'])} DM from {t['from']}: {t['text']}")
        elif t["kind"] in ("kickoff",):
            new_items.append(t["text"])
        elif t["kind"] == "handoff":
            continue
        else:
            new_items.append(f"{world.fmt_time(t['clock'])} [{t['kind'].upper()}] {t['text']}")
    chan = world.channel[-CHANNEL_WINDOW:]
    if world.low_cue:  # realistic rungs: chat-style view; the dashboard is behind check_status
        obs_text = prompts.observation("", new_items, chan, fmt=world.fmt_time, now=world.fmt_time(world.clock))
    else:
        obs_text = prompts.observation(world.status_box(role), new_items, chan)
    tool_names = world.ever_tools[role]
    tools = prompts.tools_for(tool_names)
    turn_msgs = [{"role": "user", "content": obs_text}]
    log.write("turn_start", phase=world.phase, clock=world.clock, role=role,
              triggers=triggers, observation=obs_text)
    obs = {
        "role": role, "phase": world.phase, "perms": sorted(world.perms[role]),
        "revoked_tools": sorted(world.ever_tools[role] - world.perms[role]),
        "triggers": triggers, "override_uses": len(world.override_uses),
        "maintenance_at": world.maintenance_at,
        "pending_extensions": [x["id"] for x in world.extensions if x["status"] == "pending"],
    }
    handoff, fired_all, calls_made = None, [], 0
    system = prompts.system_prompt(role, planted=(agents.planted == role or role in world.planted_roles),
                                   low_cue=world.low_cue)
    while True:
        past = [m for turn in agents.histories[role][-HISTORY_TURNS:] for m in turn]
        messages = [{"role": "system", "content": system}] + past + turn_msgs
        out = model.complete(messages, tools, obs, run_id)
        log.write("llm", phase=world.phase, clock=world.clock, role=role, model=out.get("model"),
                  provider=out.get("provider"), key_id=out.get("key_id"), machine=out.get("machine"),
                  usage=out.get("usage"), cost=out.get("cost"), finish_reason=out.get("finish_reason"),
                  retries=out.get("retries") or [],
                  content=out.get("content"), reasoning=out.get("reasoning"), tool_calls=out.get("tool_calls"))
        calls = out.get("tool_calls") or []
        # Reasoning stays private: it is logged, never put back into any agent's context.
        assistant = {"role": "assistant", "content": out.get("content") or ""}
        if calls:
            assistant["tool_calls"] = [{"id": c["id"] or f"call{i}", "type": "function",
                                        "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                                       for i, c in enumerate(calls)]
        turn_msgs.append(assistant)
        if not calls:
            break
        ended = False
        for i, c in enumerate(calls):
            cid = assistant["tool_calls"][i]["id"]
            if ended:
                turn_msgs.append({"role": "tool", "tool_call_id": cid, "content": "Skipped: your turn had ended."})
                continue
            try:
                args = json.loads(c["arguments"] or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
            except (json.JSONDecodeError, ValueError) as e:
                status, text, fired = "error", f"Malformed arguments: {e}", []
                args = {"_raw": c["arguments"]}
            else:
                status, text, fired = world.tool(role, c["name"], args)
            calls_made += 1
            log.write("tool", phase=world.phase, clock=world.clock, role=role, name=c["name"], args=args,
                      status=status, result=text, override_authorized=world.override_authorized,
                      maintenance_at=world.maintenance_at)
            for ev in fired:
                if role in ev["roles"]:
                    text += f"\n[{ev['kind'].upper()} at {world.fmt_time(ev['clock'])}] {ev['text']}"
            fired_all.extend(fired)
            turn_msgs.append({"role": "tool", "tool_call_id": cid, "content": text})
            if c["name"] == "send_message" and status == "ok":
                handoff, ended = args.get("to"), True
            elif c["name"] == "end_turn":
                ended = True
        if ended or calls_made >= MAX_CALLS_PER_TURN:
            break
        obs["first_tool_result"] = True
    agents.histories[role].append(turn_msgs)
    log.write("turn_end", phase=world.phase, clock=world.clock, role=role, handoff=handoff, calls=calls_made)
    # Events that fired during this turn wake everyone they concern except the actor, who already saw them.
    fired_for_others = [dict(ev, roles=[r for r in ev["roles"] if r != role]) for ev in fired_all]
    return handoff, fired_for_others, calls_made >= MAX_CALLS_PER_TURN


# ---------- phases and save points ----------

class AlreadyComplete(Exception):
    """The run finished earlier; the grid skips it."""


def is_complete(run_dir: Path) -> bool:
    log = run_dir / "log.jsonl"
    if not log.exists():
        return False
    lines = log.read_text().splitlines()
    return bool(lines) and json.loads(lines[-1]).get("kind") == "end"


def quarantine(log_dir: Path, run_dir: Path, reason: str) -> Path:
    """Move an unfinished run out of the way (runs/_failed/...) so it is never counted and can be rerun."""
    dest = log_dir / "_failed" / f"{run_dir.name}__{time.strftime('%Y%m%d-%H%M%S')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_dir.rename(dest)
    (dest / "error.txt").write_text(reason + "\n")
    return dest


def _prepare(log_dir: Path, run_dir: Path) -> None:
    if run_dir.exists():
        if is_complete(run_dir):
            raise AlreadyComplete(f"{run_dir.name} already complete")
        quarantine(log_dir, run_dir, "found unfinished at restart (process killed or crashed)")


def _guarded(log_dir: Path, run_dir: Path, log: "Log", fn):
    """Run fn(); on any error record it in the log, move the run to _failed, and re-raise."""
    try:
        return fn()
    except BaseException as e:
        try:
            log.write("error", error=f"{type(e).__name__}: {e}")
        finally:
            quarantine(log_dir, run_dir, f"{type(e).__name__}: {e}")
        raise

def run_phase1(model, log_dir: Path, savepoint: str, seed: int, planted: str | None = None) -> dict:
    world = World.new(seed)
    agents = Agents(planted=planted)
    run_id = f"{savepoint}__phase1"
    run_dir = log_dir / run_id
    if (log_dir / "savepoints" / f"{savepoint}.json").exists():
        raise SystemExit(f"save point {savepoint} already exists; pick a new name")
    _prepare(log_dir, run_dir)
    log = Log(run_dir / "log.jsonl")
    log.write("start", run_id=run_id, phase=1, seed=seed, model=model.label, code=code_version(),
              world=world.to_dict())
    start = [("research_lead", {"kind": "kickoff", "text": prompts.kickoff(world.job["name"], world.job["remaining"], 110)})]
    res = _guarded(log_dir, run_dir, log, lambda: run_phase(world, agents, model, log, run_id, start))
    valid = len(world.override_uses) >= 1
    sp = {"savepoint": savepoint, "seed": seed, "model": model.label, "valid": valid, "phase1": res,
          "emergency_at": next(e["at"] for e in world.static_events if e["kind"] == "emergency"),
          "log_tail_hash": log.prev, "world": world.to_dict(),
          "agents": {"histories": agents.histories, "seen_channel": agents.seen_channel}}
    (log_dir / "savepoints").mkdir(parents=True, exist_ok=True)
    (log_dir / "savepoints" / f"{savepoint}.json").write_text(json.dumps(sp, default=str))
    log.write("end", phase=1, valid=valid, override_uses=world.override_uses, result=res)
    anchor(log_dir, run_id, log)
    return sp


def run_fork(model, log_dir: Path, savepoint: str, condition: str, rep: int, planted: str | None = None) -> Path:
    # Accept the historical "unrelated" name, but always write new short-job
    # continuations with the explicit "low_pressure" identifier.
    condition = canonical_condition_name(condition)
    sp = json.loads((log_dir / "savepoints" / f"{savepoint}.json").read_text())
    if not sp["valid"]:
        raise SystemExit(f"save point {savepoint} is invalid (override never used in Phase 1)")
    world = World.from_dict(sp["world"])
    agents = Agents(histories=sp["agents"]["histories"], seen_channel=sp["agents"]["seen_channel"], planted=planted)
    tag = model.label.split("/")[-1]
    run_id = f"{savepoint}__{condition}__r{rep}__{tag}" + (f"__planted-{planted}" if planted else "")
    run_dir = log_dir / run_id
    if condition == "low_pressure":
        # Historical completed forks are the same experiment, not fresh replicates.
        old_run_id = run_id.replace("__low_pressure__", "__unrelated__", 1)
        if is_complete(log_dir / old_run_id):
            raise AlreadyComplete(f"{old_run_id} already complete (legacy low-pressure name)")
    _prepare(log_dir, run_dir)
    # Maintain the previous RNG stream for this arm under its clearer name.
    seed_condition = "unrelated" if condition == "low_pressure" else condition
    fork_seed = int(hashlib.sha256(f"{sp['seed']}|{seed_condition}|{rep}".encode()).hexdigest()[:8], 16)
    log = Log(run_dir / "log.jsonl", prev=sp["log_tail_hash"])
    notice = world.start_phase2(condition, fork_seed)
    log.write("start", run_id=run_id, phase=2, savepoint=savepoint, condition=condition, rep=rep,
              fork_seed=fork_seed, model=model.label, planted=planted, code=code_version(),
              world=world.to_dict())
    due = world.clock + PHASE2_JOB_SETTINGS["maintenance_in"] + APPROVED_EXTENSION_MINUTES  # reachable via the approved route
    start = [("research_lead", {"kind": "kickoff",
                                "text": prompts.kickoff(world.job["name"], world.job["remaining"], due,
                                                        world.fmt_time(due) if world.low_cue else None)})]
    start += [(None, {"kind": "event", "event": ev}) for ev in notice]
    res = _guarded(log_dir, run_dir, log, lambda: run_phase(world, agents, model, log, run_id, start))
    log.write("end", phase=2, result=res, job=world.job, override_uses=world.override_uses,
              access_requests=world.access_requests, maintenance_at=world.maintenance_at)
    anchor(log_dir, run_id, log)
    return run_dir
