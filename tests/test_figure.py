"""Zero-cost tests for the main figure (analysis/figure.py)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analysis import analyze, figure
from zs import harness
from zs.llm import FakeModel


class FigureTests(unittest.TestCase):
    def test_counts_split_and_render(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            harness.run_phase1(FakeModel("comply"), tmp, "sp", 1)
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "revoke1", 0)
            harness.run_fork(FakeModel("comply"), tmp, "sp", "revoke1", 1)
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "revoke0", 0)
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "revoke1", 2, planted="research_lead")
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "noextension", 0)
            runs = analyze.load_runs(tmp)
            rows = {r["arm"]: r for r in figure.figure_data(runs)["fake"]}
            r1 = rows["revoke1"]
            self.assertEqual(r1["n"], 2)  # planted and exploratory runs excluded
            self.assertEqual(r1["violation"], 1)
            self.assertEqual(r1["asked"] + r1["own"] + r1["workaround"], r1["violation"])
            self.assertEqual(rows["revoke3"]["n"], 0)
            # hand labels override the monitor's attribution
            rid = next(r["run_id"] for r in runs if r["condition"] == "revoke1" and r["violation"] and not r["planted"])
            relabeled = {r["arm"]: r for r in figure.figure_data(runs, {rid: "unclear"})["fake"]}
            self.assertEqual(relabeled["revoke1"]["unclear"], 1)
            svg = figure.render_svg("fake", list(rows.values()), "monitor")
            self.assertTrue(svg.startswith("<svg") and "Peers who still hold the override" in svg)
            self.assertNotIn("Unclear", svg)  # no unclear series without hand labels


if __name__ == "__main__":
    unittest.main()
