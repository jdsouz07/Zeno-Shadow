# What to do (main runs, Sat Nov 7 from 3:15 PM ET)

The experiment is frozen (`protocol-v1.1`). Now everyone runs their share, then we review and write.
What the experiment is: [OVERVIEW.md](OVERVIEW.md). Live status: [WORKLOG.md](WORKLOG.md).

## Rules for everyone
- **Don't edit code in `zs/`** until every share is done (all runs must use the same code). Problems → tell John / the worklog.
- **Don't look at or discuss results** until all runs are in. Analysis choices are made before seeing data.
- **Never share or commit your key.** It lives only in your `.env`.
- **Doesn't have to be at the same time.** Run when you can, ideally by Saturday night. If you can't, tell John: anyone can run your share on their own key.

---

## Everyone: set up once (5 minutes)
1. Plug in your laptop and keep it open (on a Mac the script keeps it awake).
2. In the repo folder: `git pull`
3. Your **own** OpenRouter key in `.env`: `cp .env.example .env`, then paste the key after `OPENROUTER_API_KEY=`.
4. Optional, free, 1 minute: `./run_my_runs.py <your name> --fake comply` (practice with scripted agents; spends nothing, pushes nothing).

On Windows use `python run_my_runs.py <name>` instead of `./run_my_runs.py <name>`.

---

## John (A: harness)
1. Send the team message (steps above + your share below).
2. Run your share: `./run_my_runs.py john` (**53 runs**: sp1–sp2 all conditions, positive control, exploratory; ~1.5 h, ~$0.65). Add `--parallel 8` for ~1 h. Or ask Claude to start it in the session.
3. While it runs, decide before any results are seen:
   - [ ] Add the **"attempted circumvention"** count to the analysis? (analysis only)
   - [ ] Pre-declare a **second batch** of 20 per condition (reps 4–7, ~$1.50, ~1.5 h)? Must be decided now, not after results.
4. When it ends with **"Pushed. Thanks!"**, you're done. `FAIL` lines or `STOPPED` → run the same command again (it skips finished runs).
5. If Naisha or Mae can't run theirs today: `./run_my_runs.py naisha` / `./run_my_runs.py mae` on your key.

## Naisha (B: measurement)
1. Run your share: `./run_my_runs.py naisha` (**48 runs**: sp3–sp4 all conditions + exploratory; ~1.5 h, ~$0.60).
2. While it runs: set up the review sheet and coding rules (`MEASUREMENT.md`); don't open any results.
3. After **all three** shares are pushed (`git pull`):
   - `python3 -m analysis.analyze table` and `contrasts` (rates with 95% CIs)
   - `python3 -m analysis.analyze sheet --out ../Zeno-Shadow-review --reviewers naisha mae` → review **every flagged case** plus the sampled clean runs, with a second reviewer; "unclear" is allowed
   - Hand-code the test-awareness flags (the keyword screen is noisy)
   - Main chart: violation rate by number of holders (0/1/3), split asked-by-teammate vs on-its-own
4. Log what you did in WORKLOG.md.

## Mae (C: write-up)
1. Run your share: `./run_my_runs.py mae` (**24 runs**: sp5 all conditions + exploratory; ~45 min, ~$0.30).
2. While it runs, draft from [OVERVIEW.md](OVERVIEW.md):
   - Intro + motivation (Hugging Face swarm incident; complete vs incomplete revocation)
   - Related work (Knecht et al., Kanchi, SysAdmin, Instrumental Choices, Makins et al., Potter et al.; see README Credits)
   - Method (setup, phases, conditions incl. exploratory + positive control, measures, `protocol-v1`/`v1.1` pre-registration)
   - Two versions of the headline claim, one if groups route around and one if compliance holds
3. After Naisha's numbers: results, limitations (one model; DeepSeek only; "high-opportunity" access roster; noisy test-awareness screen; restoration not tested), and submit.
4. **Submit by Sunday 10 PM ET** (hard deadline Mon 6:59 AM ET).

## Batch 2 (pre-declared: runs whatever batch 1 shows)
After your batch-1 share is pushed (tonight or Sunday morning), run the second batch the same way:
- **John:** `./run_my_runs.py john2` (40 runs, ~70 min)
- **Naisha:** `./run_my_runs.py naisha2` (40 runs, ~70 min)
- **Mae:** `./run_my_runs.py mae2` (20 runs, ~35 min)
Same save points, new reps (4–7), so each main condition ends with 40 runs. Analysis waits until both batches are in.

## Claude (in John's session)
- Run John's share and fix anything that breaks (bug fixes only, logged).
- Keep the worklog current; help Naisha with analysis and Mae with figures.

---

## Timeline (ET)
| When | What |
|---|---|
| Sat ~3:15 PM | Everyone starts their share (or tells John they can't) |
| Sat ~5 PM | All runs pushed (if started now) |
| Sat evening | Naisha: tables + review; Mae: intro, related work, method |
| Sun afternoon | Results, chart, limitations |
| **Sun 10 PM** | **Submit** |

## If something goes wrong
| You see | Do |
|---|---|
| `STOPPED: no .env file` / key empty | Step 3 of setup |
| `STOPPED: you have local edits to the code` | `git checkout -- zs tests` (undo edits), then rerun |
| `FAIL (...)` lines | Rerun the same command; failed runs are redone |
| `CERTIFICATE_VERIFY_FAILED` | `git pull` (fixed in the code) and rerun |
| Laptop slept / you pressed Ctrl-C | Rerun the same command |
| Anything else | Post it in WORKLOG.md and tell John |
