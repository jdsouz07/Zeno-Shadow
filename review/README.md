# Hand review (B: measurement)

Each review round is its own folder. A round covers a fixed set of run folders (its **scope**) and, once it is finished, holds the key, the labels and one resolved row per run. Analysis uses the hand-coded values only for runs inside some round's scope; every other run keeps the monitor's keyword-based values and is shown as not hand-reviewed.

## Coverage

| Run folder | Runs | Round | Status |
|---|---|---|---|
| `runs/` (batch 1) | 125 | [round1_main_ladder](round1_main_ladder/) | done |
| `runs_batch2/` | 100 | [round1_main_ladder](round1_main_ladder/) | done |
| `runs_ladder/` | 80 | [round1_main_ladder](round1_main_ladder/) | done |
| `runs_model2/` (gpt-6-luna) | 40 | — | **not reviewed** (its circumvention flags are detector noise per John's 2:04 PM spot check; hand-code before quoting) |
| `runs_implicit/` (protocol v1.6–v1.8) | in progress | — | **not reviewed** |
| `runs_pilot/` | — | — | not part of the results |

## Using the reviews

```
python3 -m analysis.analyze table --review                 # every finished round (review/round*/)
python3 -m analysis.analyze contrasts --review
python3 -m analysis.analyze table --runs runs_ladder --review
python3 -m analysis.figure --runs runs runs_batch2 --out figures/main --review
```
Without `--review` the commands show the monitor's values (as in the README tables).

## Adding a round

1. Build the package for the new folders only (they must not overlap an earlier round):
   `python3 -m analysis.analyze sheet --runs <folders> --out ../Zeno-Shadow-review-roundN --priority --reviewers naisha`
2. Label `labels_*_pass1.csv` and `labels_*_pass2.csv` (codes: MEASUREMENT.md §4–7 and the package README).
3. Make `review/roundN_<name>/` with `KEY.csv` (the package's KEY file), `labels_pass1.csv`, `labels_pass2.csv` and a README (scope, command, who labeled what).
4. `python3 -m analysis.review resolve review/roundN_<name> --runs <folders>` writes `resolved_runs.csv`.
5. Add the folders to the coverage table above.

A run may belong to only one round; `--review` refuses overlaps.
