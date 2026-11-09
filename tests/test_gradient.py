"""Zero-cost test for the gradient overview figure (analysis/gradient.py)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from analysis import analyze, gradient
from zs import harness
from zs.llm import FakeModel


class GradientTests(unittest.TestCase):
    def test_rows_counts_attribution_and_pending(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            harness.run_phase1(FakeModel("comply"), tmp, "sp", 1)
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "revoke1", 0)
            harness.run_fork(FakeModel("comply"), tmp, "sp", "revoke1", 1)
            runs = analyze.load_runs(tmp)
            for r in runs:  # the figure's model filter keys on the model name
                r["model"] = "deepseek/" + r["model"]
            viol = next(r["run_id"] for r in runs if r["violation"])
            att = tmp / "att.csv"
            with open(att, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["run_id", "attribution", "confusion", "human_check"])
                w.writeheader()
                w.writerow({"run_id": viol, "attribution": "asked_direct", "confusion": "none", "human_check": ""})
            rows = {r["condition"]: r for r in gradient.rows_data(runs, gradient.attribution_map(att))}
            self.assertEqual((rows["revoke1"]["main"]["k"], rows["revoke1"]["main"]["n"]), (1, 2))
            self.assertEqual(rows["revoke1"]["segments"]["asked"], 1)
            self.assertEqual(rows["shared_fate"]["main"]["n"], 0)
            self.assertFalse(gradient.attribution_checked(att))
            for check, note, ok in (("agree", "PROVISIONAL (Claude)", False), ("agree", "", True)):
                with open(att, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["run_id", "attribution", "confusion", "human_check", "human_notes"])
                    w.writeheader()
                    w.writerow({"run_id": viol, "attribution": "asked_direct", "confusion": "none",
                                "human_check": check, "human_notes": note})
                self.assertEqual(gradient.attribution_checked(att), ok)
            svg = gradient.render(list(rows.values()), True, False)
            self.assertIn("pending", svg)
            self.assertIn("human check pending", svg)


if __name__ == "__main__":
    unittest.main()
