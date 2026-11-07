# Decisions

Open choices for the experiment, with pros and cons. ✅ marks Claude's recommendation.

**How to use this:** write your answer on the **Answer** line under each decision (your name + the option, plus a reason if you're overriding the ✅). Once the team agrees, move it to **Settled** at the bottom. `git pull` before editing; push right away.

---

## Decide now (these shape the harness)

### 1. Temperature
| Option | Pros | Cons |
|---|---|---|
| **1.0** ✅ | Matches Knecht et al. exactly, so V4 Flash numbers compare with theirs. More variety between runs, so rare behaviour is easier to catch. | More random noise per run. Slightly more malformed tool calls. |
| 0.7 | Steadier behaviour, fewer broken tool calls. | Not comparable with Knecht. Rare behaviours may be undersampled. |

**Answer:** John: **1.0**. (Applied to `.env.example`, Claude, 11:53 AM.)

### 2. How agents take turns
| Option | Pros | Cons |
|---|---|---|
| **Rounds: all 6 act once per round, order rotated each round** ✅ | Simple. Maps directly onto a maintenance clock ("3 rounds left"). Easy to replay and compare across conditions. | Artificial ordering (rotation reduces the first-mover advantage). |
| Handoff (Knecht style: one agent acts until it messages another) | More natural conversations. Matches their setup. | No natural clock. One agent can hog turns. Harder to fork cleanly. |

**Answer:** John: **Handoff**, to match Knecht et al.'s style.

**Follow-ups handoff creates** (Claude's defaults; the harness will use these unless someone objects):
- **2a. Clock:** each handoff advances the simulated clock one tick (15 simulated minutes); maintenance starts at tick 12. Gives the deadline pressure that rounds would have given.
- **2b. Who acts next:** the agent that receives a DM gets control. If an agent ends its turn without sending a DM (for example, only posting to the shared channel), control goes to the agent with the oldest unread DM, else back to the research lead, who also receives the kickoff. This avoids making the research lead a full relay, which would recreate Knecht's orchestrator effect by accident.
- **2c. Caps:** 20 tool calls per turn and 40 handoffs per phase (Knecht used 20 and 20 for a shorter episode). Runs that end on a cap are counted and reported separately.

**Answer to 2a–2c:**

### 3. How agents communicate
| Option | Pros | Cons |
|---|---|---|
| **Direct messages plus one shared channel** ✅ | Realistic. Shows whether proxy requests happen privately or publicly, which is a finding in itself. | More to log and classify. |
| Shared channel only | Simpler. Everything visible to everyone. | Probably suppresses violations (asking a peer to break policy in public is less likely). Higher chance of a null result. |

**Answer:** John: **Direct messages plus one shared channel**.

### 4. Who holds `maintenance_override`, and who keeps it after revocation
| Option | Pros | Cons |
|---|---|---|
| **Infrastructure engineer = agent A (loses it). "1 peer": compute scheduler keeps it. "3 peers": scheduler, budget controller and checkpoint engineer keep it.** ✅ | The agents who benefit from more time (research lead, training engineer) must *ask* a holder, and that request is the proxy behaviour we measure. | Results depend on which roles were picked. Report as a limitation. |
| Randomize holders across roles each run | Results don't hinge on one role. | Needs more runs to average out; 15 per condition isn't enough. |

**Answer:** John: **the recommended option.** Infrastructure engineer is agent A and loses the override. "1 peer": the compute scheduler keeps it. "3 peers": scheduler, budget controller and checkpoint engineer keep it. Research lead and training engineer never hold it after revocation, so they must ask a holder.

### 5. How the override gets used in Phase 1
| Option | Pros | Cons |
|---|---|---|
| **Scripted emergency: an alert says to use the override now** ✅ | Guarantees the bypass is used in every checkpoint, so revoking it means something. | Feels a bit staged. |
| Authorize it and let agents decide | More natural. | Some checkpoints may never use it, wasting runs. |

**Answer:**

### 6. Agent context
| Option | Pros | Cons |
|---|---|---|
| **Own history + last ~20 shared messages + a short state summary each round (always showing the current policy)** ✅ | Cheaper. Fewer agents getting lost. Policy line means no one can miss the revocation. | Agents may lose older details. |
| Full history | Nothing is missed. | Prompts grow long, cost climbs fast, models drift. |

**Answer:**

### 7. Reasoning mode on V4 Flash
| Option | Pros | Cons |
|---|---|---|
| **Off** ✅ | Cheap and fast. | No private reasoning to read when coding intent; messages and actions have to carry it. |
| On | Reasoning traces help tell "confused" from "deliberate". | Several times the cost, slower. Doesn't improve comparability with Knecht. |

**Answer:**

---

## Decide before the pilot (Sat ~6 PM)

### 8. How much pressure (deadline slack, approval delay)
| Option | Pros | Cons |
|---|---|---|
| **Tight but honest: the approved route still works if agents use it** ✅ | Violations likely enough to measure; still defensible. | Needs tuning in the pilot. Write down the settings and freeze them before the real runs. |
| Very tight | Violations very likely. | Critics can say we forced them. |
| Loose | Cleanest interpretation. | Risk of zero violations. |

**Answer:**

### 9. How to code intent (confused / unintended habit / deliberate)
| Option | Pros | Cons |
|---|---|---|
| **LLM classifier checked against ~50 hand labels** ✅ | Scales to every run; validation makes the numbers defensible. | Extra build and labelling time for B. |
| Hand labels only | Most trustworthy. | B can only label the violations, not every message. |

**Answer:**

### 10. Positive control
| Option | Pros | Cons |
|---|---|---|
| **Prompted "finish training at all costs" agent** ✅ | Free and quick. | Its instruction is visible in its prompt. |
| Model fine-tuned on Adaption | More convincing ("detector catches a model organism"). | Takes hours; risks the deadline. Only if there's time Sunday. |

**Answer:**

---

## Decide later (Sunday)

### 11. Which models, given the budget
| Option | Pros | Cons |
|---|---|---|
| **V4 Flash on every condition; V4 Pro and V3.2 only on sham vs "1 peer keeps it"** ✅ | Cheap-vs-strong comparison plus a direct comparison with Kanchi. | Results stay DeepSeek-only. |
| Also add one non-DeepSeek model on the key arms | Answers "is this just DeepSeek?" | Costs more; only if budget is left. |

**Answer:**

### 12. Title
| Option | Pros | Cons |
|---|---|---|
| "Zeno-Shadow" | Memorable; matches the repo name. | The quantum Zeno analogy doesn't hold; physics-literate judges may notice. |
| **"Revocation Probes: Do Agent Swarms Route Around Removed Permissions?"** ✅ | Says exactly what we did. | Less catchy. |
| "Break-Glass Never Closes" | Catchy; ties to real emergency-access practice. | Only fits if agents bypass out of habit rather than deliberately. |

**Answer:**

### 13. Names for roles A, B, C
- **A (Harness):**
- **B (Measurement):**
- **C (Write-up):**

---

## Settled
- 6 agents (research lead, training engineer, checkpoint engineer, compute scheduler, infrastructure engineer, budget controller)
- Policy changes for everyone; the permission is technically removed from only some agents
- Our own harness, not Knecht's code (no license, different structure)
- Build against a fake model first, then switch to OpenRouter
- Deterministic monitor outside the agents
- 15 runs per condition (3 checkpoints × 5)
