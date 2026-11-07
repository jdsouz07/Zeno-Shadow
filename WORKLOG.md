# Worklog

The one place to see what's going on. Everyone (and Claude) updates it after doing anything.

**How to edit**
1. `git pull` first, every time.
2. Update **Status** if what's true changed (owner, blocker, next step).
3. Add a line to **Log**, newest at the top: `- **HH:MM ET, Name:** what you did → result / link`.
4. Keep it short. Commit and push right away, so others aren't editing a stale copy.

Full design: [README](README.md) · Open choices: [DECISIONS.md](DECISIONS.md) · Team plan (roles, timeline): [Zeno-Shadow Team Plan](https://claude.ai/artifact/VqvMNPntNYo8DL1aP2uJyr) (ask John for access)

---

## Status

*Last updated: Sat Nov 7, 11:46 AM ET (Claude)*

| Area | State | Owner | Next step |
|---|---|---|---|
| Design | Merged design adopted (training job + maintenance window, 6 roles, 7 conditions) | Team | — |
| Harness | Not started; will be written from scratch | A + Claude | Waiting on answers to decisions 1–7, then build against a fake model |
| OpenRouter credits | **Not received** ($50 per team) | C | Ask organizers on Discord or sprints@apartresearch.com |
| Measurement | Not started | B | Write exact definitions of a violation and the three intent codes |
| Write-up | Not started | C | Related-work section (list in README) |

**Open decisions:** 13 choices with pros, cons and a recommendation are in [DECISIONS.md](DECISIONS.md). Decisions 1–7 block the harness: answer those first.

**Deadlines (ET):** harness runs on fake model by Sat 6 PM · pilot decision Sat 9 PM · all runs done Sun 12 PM · stats final Sun 5 PM · submit Sun 10 PM · hard deadline Mon 6:59 AM (Sun 11:59 PM AoE)

---

## Log

### Sat Nov 7
- **11:46 AM, Claude:** Added [DECISIONS.md](DECISIONS.md): 13 open choices (temperature, turn order, messaging, override holders, Phase 1 trigger, context, reasoning, pressure, intent coding, positive control, models, title, role names) with pros, cons, a recommendation and an Answer line each.
- **11:41 AM, Claude:** Correction: "Amelie Knecht" appears on the hackathon page under "Judges and mentors" (judge or mentor not specified), matched to the paper's first author by name only. Fixed the wording here and in the team plan.
- **11:40 AM, Claude:** Created this worklog and linked it from the README.
- **~11:35 AM, Claude:** Reviewed Knecht et al.'s code ([repo](https://github.com/AmelieKnecht/multi-agent-shutdown-sabotage)). It has **no license** and a different structure (one agent active at a time, files only, no permissions or checkpoints), so we write our own harness. Ideas to reuse with credit: streaming API calls with retries, reporting runs that hit step caps, rule-based checking instead of an LLM judge, detecting indirect workarounds, Boschloo's test. They ran V4 Flash at temperature 1.0.
- **~11:30 AM, Claude:** Adopted the merged design: simulated ML training job approaching maintenance, `maintenance_override` authorized in Phase 1 then revoked, 0/1/3 peers keep it, plus sham, necessary-permission and "maintenance doesn't threaten the job" (D) conditions. Positioned as building on [Knecht et al. 2026](https://arxiv.org/abs/2609.28274), whose first author shares a name with someone on the hackathon's "Judges and mentors" list. Updated README and team plan.
- **~11:28 AM, Claude:** Verified the new citations: Knecht et al. (shutdown sabotage between peers, also tested DeepSeek V4 Flash), Makins et al. (distributed attacks beat per-agent monitors), ShutdownMod, Potter et al. (peer preservation). None revokes a permission mid-run.
- **~11:25 AM, Claude:** Made the team plan doc (roles, timeline, decisions).
- **~11:20 AM, Claude:** Created the GitHub repo contents: README, `.env.example`, `.gitignore`. The real key stays in a local `.env` only.
- **~11:13 AM, Claude:** Picked models from OpenRouter's live list: V4 Flash for every condition (~$2 for the full set), V4 Pro and V3.2 on key conditions. Pinned dated versions and providers. Wrote `.env`.
- **~11:00 AM, John:** Set up an OpenRouter account. Team has 3 people and $50 of credit (not yet received).
- **Morning, Claude:** Novelty check on "Zeno-Shadow" (revoke a capability, watch whether the group gets it back). Closest work: Kanchi 2026, SysAdmin, Munirathinam 2026. Core idea open. Reworked the plan: tempting bypass, peers who keep it, 15 runs per condition.

### Fri Nov 6
- **Evening, Claude:** Researched an earlier idea (agents discovering an unannounced shared folder); it was open, but the team chose Zeno-Shadow instead.
