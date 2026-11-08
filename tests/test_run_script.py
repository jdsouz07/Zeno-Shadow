"""The run script's share plans (no model calls)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("run_my_runs", Path(__file__).resolve().parent.parent / "run_my_runs.py")
run_my_runs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_my_runs)


class RunScriptTests(unittest.TestCase):
    def test_second_model_share(self):
        self.assertEqual(run_my_runs.count_planned_runs("model2"), 40)
        self.assertEqual(run_my_runs.RUN_ASSIGNMENTS["model2"][4], "runs_model2")
        for command in run_my_runs.build_grid_arguments("model2"):
            self.assertEqual(command[-2:], ["--model", "compare"])
        self.assertNotIn("deepseek", run_my_runs.SECOND_MODEL["MODEL_COMPARE"])

    def test_implicit_extension_shares(self):
        self.assertEqual(run_my_runs.count_planned_runs("implicit_more"), 40)
        self.assertEqual(run_my_runs.count_planned_runs("implicit_luna"), 20)
        for command in run_my_runs.build_grid_arguments("implicit_more"):
            self.assertNotIn("--model", command)
            self.assertEqual(command[command.index("--rep-start") + 1], "4")  # no overlap with reps 0-3
        for command in run_my_runs.build_grid_arguments("implicit_luna"):
            self.assertEqual(command[-2:], ["--model", "compare"])

    def test_deepseek_shares_unchanged(self):
        for name in ("john", "naisha", "mae", "john2", "naisha2", "mae2", "john_ladder", "naisha_ladder", "mae_ladder"):
            for command in run_my_runs.build_grid_arguments(name):
                self.assertNotIn("--model", command)
        self.assertEqual([run_my_runs.count_planned_runs(n) for n in ("john_ladder", "naisha_ladder", "mae_ladder")], [32, 32, 16])


if __name__ == "__main__":
    unittest.main()
