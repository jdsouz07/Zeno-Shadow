# Worklog

The one place to see what's going on. Everyone (and Claude) updates it after doing anything.

**How to edit**
1. `git pull` first, every time.
2. Update **Status** if what's true changed (owner, blocker, next step).
3. Add a line to **Log**, newest at the top: `- **HH:MM ET, Name:** what you did → result / link`.
4. Keep it short. Commit and push right away, so others aren't editing a stale copy.

**Claude** reads this file at the start of every prompt, and writes to it when John says "update" or when something happens the team needs to know. Its entries are tagged "Claude" and its commits start with `[Claude]`.

Full design: [README](README.md) · Open choices: [DECISIONS.md](DECISIONS.md) · Roles, timeline and budget: **Plan** section below

---

## Status

*Last updated: Sat Nov 7, 12:05 PM ET (Claude)*

| Area | State | Owner | Next step |
|---|---|---|---|
| Design | Merged design adopted (training job + maintenance window, 6 roles, 7 conditions) | Team | — |
| Harness | Not started; will be written from scratch | A + Claude | Decisions 1–3 answered; waiting on 4–7, then build against a fake model |
| OpenRouter credits | **Received:** 3 keys, one per person, $50 each = $150 total. Not yet verified. | Everyone | Put your key in your own `.env` (never commit or paste it); Claude will check John's key's limit |
| Measurement | Not started | B | Write exact definitions of a violation and the three intent codes |
| Write-up | Not started | C | Related-work section (list in README) |

**Open decisions:** 13 choices with pros, cons and a recommendation are in [DECISIONS.md](DECISIONS.md). Answered: 1 (temperature 1.0), 2 (handoff), 3 (DMs + shared channel). Still blocking the harness: 4–7, plus a look at the handoff follow-ups 2a–2c.

---

## Plan

Build the harness today against a fake model, pilot tonight, run everything overnight and Sunday morning, submit Sunday 10 PM ET. Hard deadline: Mon 6:59 AM ET (Sun 11:59 PM AoE).

### Roles
| Role | Person | Saturday | Sunday |
|---|---|---|---|
| A: Harness (with Claude) | | Simulated world, agents, logging, checkpoint replay, fake-model tests, pilot | Full runs, bug fixes, one-command rerun script |
| B: Measurement | | Violation and intent definitions, proxy-request classifier | Hand-label ~50 messages, validate classifier, statistics, main figure |
| C: Write-up | | Related work, intro, draft claims for both outcomes | Results, limitations, polish, submit |

### Right now
- [ ] **John:** answer DECISIONS 4–7 and 2a–2c (they block the harness); fill in the Person column above
- [ ] **Everyone:** put your own OpenRouter key in your `.env` (never commit or paste it)
- [ ] **B:** write exact definitions of a violation and the three intent codes (confused, unintended habit, deliberate)
- [ ] **C:** start the related-work section (list in README)

### Timeline (ET)
| When | Checkpoint | Owner |
|---|---|---|
| Sat 6 PM | Harness runs end to end on a fake model | A |
| Sat 9 PM | **Pilot decision:** sham vs "1 peer keeps it", 5 runs each. Violations → full runs start overnight. Zero → one pressure increase, then the null-result story | A, B |
| Sun 12 PM | All runs done | A |
| Sun 5 PM | Statistics and main figure final | B |
| Sun 10 PM | Write-up submitted | C |
| Mon 6:59 AM | Hard deadline | — |

### Budget ($150: three $50 keys)
- Full set of 7 conditions × 15 runs ≈ $2 on V4 Flash, ≈ $10–25 on V4 Pro or V3.2. Time limits us, not money.
- Plan: every condition on all three DeepSeek models; one non-DeepSeek model on the key conditions; up to ~25 runs per condition on V4 Flash if time allows; keep ~$30 in reserve.
- Each key is capped at $50. Proposed: split runs by person, each on their own machine and key, pushing logs to the repo. The harness records which key and machine made each call.

---

## Log

### Sat Nov 7
- **12:10 PM, Chat:** Reviewed current [README](README.md), worklog, and team plan; confirmed the shared six-agent ML-training/maintenance design and seven conditions. **Rationale:** Mid-run revocation with 0/1/3 peers retaining a technically usable but policy-forbidden override tests whether population-level access survives individual revocation; sham, necessary-permission, and unrelated-maintenance controls help distinguish bypass attempts from legitimate recovery and task pressure. Preserved all existing entries and made no changes to experimental code or agreed conditions. Future contributions will use the same newest-first log format with the `Chat` tag and a brief design justification.
- **12:05 PM, Claude:** Added a **Plan** section above (roles, right-now tasks, timeline, $150 budget plan), so the plan lives here in the repo, not only in the private plan doc.
- **11:58 AM, Claude:** Credits arrived as one OpenRouter key per person ($50 each, $150 total), per John. Budget is 3x the plan; see chat/DECISIONS for how to use it.
- **11:54 AM, Claude:** Recorded John's answers in DECISIONS.md: 1 = temperature 1.0 (set in `.env.example`; pull and update your own `.env`), 2 = handoff like Knecht, 3 = DMs + shared channel. Added handoff follow-ups 2a–2c with defaults (clock tick per handoff, who acts next, caps).
- **11:49 AM, Claude:** New rule from John: Claude reads this worklog before every prompt and logs every prompt here; Claude's commits are prefixed `[Claude]`. Checked DECISIONS.md: no answers filled in yet.
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
