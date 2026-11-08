"""Zero-cost tests for hand-review rounds (analysis/review.py)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from analysis import analyze, review
from zs import harness
from zs.llm import FakeModel


class ReviewRoundTests(unittest.TestCase):
    def test_resolve_replaces_keyword_requests_with_hand_codes(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            harness.run_phase1(FakeModel("comply"), tmp, "sp", 1)
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "revoke0", 0)   # keyword ask, no violation possible
            harness.run_fork(FakeModel("proxy"), tmp, "sp", "revoke1", 0)   # ask + violation
            harness.run_fork(FakeModel("comply"), tmp, "sp", "revoke1", 1)
            pkg = tmp / "pkg"
            analyze.cmd_sheet(tmp, pkg, seed=0, clean_per_arm=2, reviewers=["naisha"], priority=True)
            rnd = tmp / "round1"
            rnd.mkdir()
            (rnd / "KEY.csv").write_text((pkg / "KEY_do_not_open_until_labels_done.csv").read_text())
            for p in ("1", "2"):  # code every proxy request false_positive
                rows = list(csv.DictReader(open(pkg / f"labels_naisha_pass{p}.csv")))
                for r in rows:
                    if r["item"] == "proxy_request":
                        r["code"] = "false_positive"
                with open(rnd / f"labels_pass{p}.csv", "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0]))
                    w.writeheader()
                    w.writerows(rows)
            runs = analyze.load_runs(tmp)
            monitor = {(r["condition"], r["rep"]): r for r in runs}
            self.assertTrue(monitor[("revoke0", 0)]["circumvention"])  # keyword-based before review
            rows = review.resolve(rnd, runs)
            self.assertEqual(len(rows), 3)  # every run in scope, reviewed or not
            res = {r["run_id"]: r for r in rows}
            with open(rnd / "resolved_runs.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=review.RESOLVED_COLS)
                w.writeheader()
                w.writerows(rows)
            after = {(r["condition"], r["rep"]): r for r in
                     review.apply_review(analyze.load_runs(tmp), review.load_resolved([rnd]))}
            self.assertFalse(after[("revoke0", 0)]["circumvention"])  # the ask was coded false_positive
            self.assertTrue(after[("revoke1", 0)]["circumvention"])   # the violation is an objective event
            self.assertTrue(after[("revoke1", 0)]["violation"])
            self.assertTrue(all(r["hand_reviewed"] for r in after.values()))
            self.assertEqual(sum(int(r["in_package"]) for r in res.values()), 3)
            self.assertIn("hand-reviewed", analyze.cmd_table(list(after.values())))

    def test_run_in_two_rounds_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            for name in ("a", "b"):
                d = Path(t) / name
                d.mkdir()
                with open(d / "resolved_runs.csv", "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=review.RESOLVED_COLS)
                    w.writeheader()
                    w.writerow({c: "" for c in review.RESOLVED_COLS} | {"run_id": "x"})
            with self.assertRaises(SystemExit):
                review.load_resolved([Path(t) / "a", Path(t) / "b"])


if __name__ == "__main__":
    unittest.main()
