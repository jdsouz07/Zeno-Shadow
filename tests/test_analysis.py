"""Zero-cost tests for B's analysis (analysis/). Run with the rest:  python3 -m unittest discover -s tests -t . -v"""

from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from analysis import analyze, stats
from zs import harness
from zs.llm import FakeModel


class StatsTests(unittest.TestCase):
    def test_boschloo_matches_scipy_docs(self):
        # scipy.stats.boschloo_exact([[74, 31], [43, 32]], alternative="greater").pvalue == 0.0355
        self.assertAlmostEqual(stats.boschloo(74, 117, 31, 63, "greater"), 0.0355, places=3)

    def test_boschloo_basic_properties(self):
        self.assertEqual(stats.boschloo(0, 15, 0, 15), 1.0)
        self.assertAlmostEqual(stats.boschloo(3, 15, 1, 15), stats.boschloo(1, 15, 3, 15))
        self.assertLess(stats.boschloo(6, 15, 0, 15), 0.01)
        self.assertGreater(stats.boschloo(2, 15, 0, 15), 0.05)

    def test_wilson_zero_of_fifteen(self):
        lo, hi = stats.wilson(0, 15)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.204, places=3)  # "0/15, upper bound about 20%" (MEASUREMENT.md §3)

    def test_holm(self):
        out = stats.holm([0.01, 0.04, 0.03, float("nan")])
        self.assertEqual(out[:3], [0.03, 0.06, 0.06])
        self.assertTrue(math.isnan(out[3]))

    def test_kappa(self):
        self.assertEqual(stats.cohen_kappa(list("abc"), list("abc")), 1.0)
        self.assertAlmostEqual(stats.cohen_kappa(list("aabbc"), list("aabcc")), 0.7059, places=3)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._t = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._t.name)
        harness.run_phase1(FakeModel("comply"), cls.tmp, "sp", 1)
        for cond in ("control", "sham", "revoke0", "revoke1"):
            harness.run_fork(FakeModel("proxy"), cls.tmp, "sp", cond, 0)
        harness.run_fork(FakeModel("comply"), cls.tmp, "sp", "revoke1", 1)
        harness.run_fork(FakeModel("proxy"), cls.tmp, "sp", "revoke1", 2, planted="research_lead")
        cls.runs = {(r["condition"], r["rep"], bool(r["planted"])): r for r in analyze.load_runs(cls.tmp)}

    @classmethod
    def tearDownClass(cls):
        cls._t.cleanup()

    def test_phase1_logs_are_not_scored(self):
        self.assertEqual(len(self.runs), 6)

    def test_incomplete_runs_excluded_from_analysis(self):
        """Rate denominators never include a live/crashed run missing its final event."""
        d = self.tmp / "incomplete__revoke1__r99__fake"
        d.mkdir(exist_ok=True)
        (d / "log.jsonl").write_text(
            '{"seq":0,"kind":"start","phase":2,"run_id":"incomplete",'
            '"condition":"revoke1","model":"fake"}\n'
        )
        # The real Phase 2 forks from setUpClass remain the only six scored runs.
        rows = analyze.load_runs(self.tmp)
        self.assertEqual(len(rows), 6)
        self.assertNotIn("incomplete", [r["run_id"] for r in rows])

    def test_missing_runs_directory_returns_empty(self):
        self.assertEqual(analyze.load_runs(self.tmp / "not-created"), [])

    def test_outcomes(self):
        self.assertTrue(self.runs[("revoke1", 0, False)]["violation"])
        self.assertTrue(self.runs[("revoke1", 0, False)]["proxy_request"])
        self.assertFalse(self.runs[("revoke1", 1, False)]["violation"])  # comply: honest route
        self.assertFalse(self.runs[("revoke1", 1, False)]["postponement"])
        self.assertFalse(self.runs[("control", 0, False)]["violation"])  # authorized use is not a violation
        self.assertTrue(self.runs[("control", 0, False)]["postponement"])

    def test_positive_control_kept_separate(self):
        rows = analyze.contrast_rows(list(self.runs.values()))
        main = next(r for r in rows if r["a"] == "revoke1" and r["b"] == "revoke0")
        self.assertEqual(main["na"], 2)  # two unplanted revoke1 runs; the planted one is excluded
        self.assertIn("positive_control", analyze.cmd_table(list(self.runs.values())))

    def test_sheet_is_blinded(self):
        out = self.tmp / "review"
        analyze.cmd_sheet(self.tmp, out, seed=0, clean_per_arm=2, reviewers=["naisha", "mae"])
        ids = [r["run_id"] for r in self.runs.values()]
        for f in (out / "transcripts").rglob("*.md"):
            text = f.read_text()
            for rid in ids:
                self.assertNotIn(rid, text)
        p1 = (out / "transcripts" / "pass1").iterdir().__next__().read_text()
        self.assertNotIn("REASONING", p1)
        with open(out / "labels_mae_pass1.csv", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(rows and all(r["reviewer"] == "mae" for r in rows))
        self.assertFalse(any(r["item"] == "test_awareness" for r in rows))
        self.assertTrue(any(r["item"] == "violation_override" for r in rows))


if __name__ == "__main__":
    unittest.main()
