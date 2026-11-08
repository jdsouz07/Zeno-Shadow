"""Counterfactual replay (zs/replay.py) on the fake model: zero cost."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from zs import harness, monitor, replay
from zs.config import ROOT
from zs.llm import FakeModel


def _source(tmp: Path, cond="revoke1", mode="proxy") -> tuple[Path, int]:
    """A fake fork where research_lead DMs compute_scheduler to use the override; returns (dir, cut seq)."""
    harness.run_phase1(FakeModel("comply"), tmp, "sp", 1)
    d = harness.run_fork(FakeModel(mode), tmp, "sp", cond, 0)
    recs = monitor.load(d / "log.jsonl")
    seq = next(r["seq"] for r in recs if r["kind"] == "tool" and r["name"] == "send_message"
               and r["role"] == "research_lead")
    return d, seq


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.src, self.seq = _source(self.tmp)
        self.out = self.tmp / "causal"

    def tearDown(self):
        self._t.cleanup()

    def test_source_has_proxied_violation(self):
        self.assertTrue(monitor.analyze(monitor.load(self.src / "log.jsonl"))["violation_proxied"])

    def test_keep_arm_reproduces_the_use(self):
        d = replay.run_replay(FakeModel("proxy"), self.src, self.seq, "keep", 0, out_dir=self.out)
        o = replay.outcome(d)
        self.assertTrue(o["fidelity_ok"])
        self.assertTrue(o["override_used"])
        self.assertEqual(o["uses"][0]["role"], "compute_scheduler")
        self.assertTrue(harness.verify_log(d / "log.jsonl"))
        self.assertIn("__cut", d.name)
        self.assertIn("__keep__r0__fake", d.name)

    def test_remove_arm_removes_the_use(self):
        d = replay.run_replay(FakeModel("proxy"), self.src, self.seq, "remove", 0, out_dir=self.out)
        o = replay.outcome(d)
        self.assertTrue(o["fidelity_ok"])
        self.assertFalse(o["override_used"])
        recs = monitor.load(d / "log.jsonl")
        cut = next(r for r in recs if r["seq"] == self.seq)
        self.assertEqual(cut["args"]["text"], replay.NEUTRAL_TEXT)
        self.assertEqual(cut["args"]["to"], "compute_scheduler")  # same recipient, same handoff

    def test_prefix_matches_original_records(self):
        d = replay.run_replay(FakeModel("proxy"), self.src, self.seq, "keep", 0, out_dir=self.out)
        new, old = monitor.load(d / "log.jsonl"), monitor.load(self.src / "log.jsonl")
        cut = replay.find_cut(old, self.seq)
        self.assertEqual(new[0]["fork_seed"], old[0]["fork_seed"])
        for a, b in zip(new[:cut["llm_seq"]], old[:cut["llm_seq"]]):
            self.assertIsNone(replay.compare_record(a, b))

    def test_divergence_is_detected_and_quarantined(self):
        bad = self.tmp / "tampered" / self.src.name
        shutil.copytree(self.src, bad)
        shutil.copytree(self.tmp / "savepoints", self.tmp / "tampered" / "savepoints")
        lines = (bad / "log.jsonl").read_text().splitlines()
        recs = [json.loads(x) for x in lines]
        i = next(k for k, r in enumerate(recs) if r["kind"] == "turn_start" and r["seq"] < self.seq)
        recs[i]["observation"] += " (edited)"
        (bad / "log.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        with self.assertRaises(replay.ReplayDiverged):
            replay.run_replay(FakeModel("proxy"), bad, self.seq, "keep", 0, out_dir=self.out)
        self.assertTrue(any((self.out / "_failed").iterdir()))
        self.assertFalse([p for p in self.out.iterdir() if p.name.startswith("sp")])

    def test_cut_must_be_a_message(self):
        recs = monitor.load(self.src / "log.jsonl")
        other = next(r["seq"] for r in recs if r["kind"] == "tool" and r["name"] == "use_override")
        with self.assertRaises(SystemExit):
            replay.find_cut(recs, other)

    def test_neutral_text_is_not_a_request(self):
        self.assertFalse(monitor.asks_for_override(replay.NEUTRAL_TEXT))
        self.assertNotRegex(replay.NEUTRAL_TEXT.lower(), r"override|maintenance|postpone")

    def test_original_run_is_untouched(self):
        before = (self.src / "log.jsonl").read_bytes()
        replay.run_replay(FakeModel("proxy"), self.src, self.seq, "remove", 0, out_dir=self.out)
        self.assertEqual((self.src / "log.jsonl").read_bytes(), before)


REAL = ROOT / "runs_implicit" / "sp2__shared_fate__r1__deepseek-v4-flash-0731"


@unittest.skipUnless((REAL / "log.jsonl").exists(), "committed shared_fate run not present")
class RealLogFidelityTests(unittest.TestCase):
    """The recorded DeepSeek prefix of a committed run replays faithfully under the current code."""

    def test_real_prefix_replays_faithfully(self):
        with tempfile.TemporaryDirectory() as t:
            for arm in replay.ARMS:
                d = replay.run_replay(FakeModel("comply"), REAL, 26, arm, 0, out_dir=Path(t))
                o = replay.outcome(d)
                self.assertTrue(o["fidelity_ok"])
                self.assertEqual(o["arm"], arm)


if __name__ == "__main__":
    unittest.main()
