# `agentope` — offline evaluation of LLM agent decisions

**Status:** draft spec v0.1 · **Working name** (check PyPI before publishing) · **Author:** Max Pagels

> Would this agent decision have gone better under a different policy?
> `agentope` answers that from logs you already have or can cheaply start keeping.
> It never reads token logprobs, and every number it reports comes with the
> assumptions it rests on.

---

## 1. Summary

Teams change agents constantly: a new system prompt, a different model, a new
tool, a different router. Today they judge those changes with LLM-as-judge
scores or slow A/B tests. Off-policy evaluation (OPE) can estimate a change's
effect on **real outcomes** from logged traffic, but standard OPE needs action
propensities. Agents rarely log them, and token logprobs are not a reliable
substitute.

`agentope` does OPE for **one agent decision point at a time** (which tool to
call, which model to route to, which prompt variant to use). It gets propensities
without logprobs, in one of three ways:

1. **Logged**: the system randomized and recorded the probability.
2. **Sampled**: the logging LLM is re-run on the stored input and its choices are counted.
3. **Estimated**: a model of the logging policy is fit from the logs.

Each estimate is labeled with its **evidence level**. The tool picks the
strongest level the data supports, states the assumptions that level needs,
and tells you what to log next to move up a level.

Distribution: a Python package with a CLI entry point (`pip install agentope`
gives you the `agentope` command). The numeric core depends on numpy and
scipy. LLM sampling is an optional extra (`agentope[llm]`).

---

## 2. Goals and non-goals

### Goals

- **Simple first run.** One command on existing traces produces a readiness
  report, without needing to know any OPE.
- **Honest output.** Every estimate carries its evidence level, diagnostics, a
  plain-language list of assumptions, and a verdict (`ok`, `weak` or `unreliable`).
- **Unsafe evaluations cannot run by accident.** Evaluations that depend on
  untestable assumptions refuse to run until the user explicitly accepts them.
- **No logprobs, ever.** Works with any model behind any API, including models
  that expose no logprobs.
- **Deterministic evaluation.** All nondeterministic work (LLM sampling) happens
  in explicit steps that write files. Evaluating over those files is
  bit-reproducible.

### Non-goals

| Not doing | Why |
|---|---|
| Logprob-based propensities | Unavailable for many models (including many reasoning models), unstable across silent provider updates, distorted by top-p truncation, and degenerate when weighted over whole texts. |
| Evaluating multi-step trajectories | Importance weights multiplied over many steps have unusable variance. v1 evaluates one decision point with everything else held fixed. |
| Evaluating free-text actions directly | Text is mapped to a small set of semantic actions (§4.3). Evaluation happens over those. |
| Online learning or serving | `agentope` only evaluates. |
| Treating LLM-judge scores as outcomes by default | Judge scores may be used only at the *Modeled* level (§5.4), labeled as such. |

---

## 3. The question it answers

> For decision point **D**, if **target policy B** had made the choice instead of
> **logging policy A**, and everything else had stayed the same, what would the
> average **outcome** have been?

The headline number is **B's estimated mean outcome minus A's realized mean
outcome**, with an interval. Everything else in the report explains how far to
trust that number.

---

## 4. Concepts

### 4.1 Decision point

A place in the agent where one choice is made from a set of alternatives. Examples:

| Decision point | Candidates | Who decides today |
|---|---|---|
| `tool_choice` | `search`, `lookup_order`, `escalate`, `__none__` (answer directly) | the LLM |
| `router` | `small-model`, `large-model` | code or a bandit |
| `system_prompt` | `v1`, `v2` | code (a flag) |
| `plan_type` | `ask_clarifying`, `answer`, `handoff` | the LLM (free text, mapped) |

`__none__` is a real action. "The model answered without calling a tool" must
be a candidate, or tool-choice evaluation is biased.

### 4.2 Context, candidates, choice, outcome

- **Context:** a flat dict of features describing the situation (`str`,
  number, `bool` or `null`), e.g. `{"intent": "refund", "turn": 3, "tier": "pro"}`.
  Used for estimating propensities (§5.3) and for reporting by segment.
- **Stored input:** the exact, complete model input at the decision (messages,
  tool definitions, retrieved context). Needed only for the *Sampled* level and
  for LLM target policies. Stored separately and referenced by `input_ref`.
- **Candidates:** the action ids available at this decision.
- **Chosen:** the action id actually taken.
- **Outcome:** a number observed later (resolved = 1, CSAT, revenue, …),
  joined in by key (§6.2).

### 4.3 Action map

The function that turns what the agent did into an action id. Built-ins:

| Map | Action id | Assumption you're making (shown in every report) |
|---|---|---|
| `tool` (default) | tool name, or `__none__` | The outcome depends on *which* tool was called, not on its arguments or the surrounding text. |
| `tool+args:<fields>` | tool name plus the named argument fields | The outcome depends only on the tool and those fields. |
| `toolset` | sorted set of tool names called in parallel | The outcome depends only on which tools were called together. |
| custom (Python) | anything | Whatever your function ignores doesn't affect the outcome. |

This is the **no-direct-effect assumption** from marginalized IPS
(Saito & Joachims, 2022). It is the most important modeling choice the user
makes, so it is always explicit and never hidden behind a default without
being printed.

### 4.4 Policies

- **Logging policy (A):** whatever made the logged choices.
- **Target policy (B):** what you want to evaluate. It can be given as:
  1. a Python callable `(context, candidates) -> probabilities`;
  2. an LLM configuration (model, system prompt, temperature, tool list) that
     is sampled on stored inputs (§7.2);
  3. a precomputed `target.jsonl` file (§6.3).

### 4.5 Scope rule

v1 evaluates **one decision point at a time**. The estimate answers "change D
only". When B would change what happens *after* D (later tool calls, other
turns), those downstream effects are captured only insofar as the logged
outcome reflects them under A's downstream behavior. The report states this
every time.

---

## 5. Evidence levels

The tool assigns each decision a propensity source, then evaluates at the
**lowest level present** among the included decisions. It never silently
mixes levels. `--level` filters to one level.

### 5.1 Level 1 — Logged

Propensities were recorded when the decision was made, because the system
randomized.

**Ways to get there:**

- **Code-made decisions** (router, prompt variant): decide with
  `agentope.randomize` (§7.3), which logs the probability used.
- **LLM-made decisions:** wrap the decision in `agentope.explore`. With
  probability ε the action is drawn uniformly from a user-approved
  `safe_candidates` list instead of taken from the LLM, and the coin flip is
  logged. **Only the explored decisions are used for evaluation.** On those,
  the propensity is exactly `1/k`, known without any model of the LLM.
  Choosing which rounds to explore doesn't depend on context, so restricting
  to them doesn't bias the estimate.

**Assumptions:** logged probabilities are correct; the target puts no
probability on actions the logger could never pick (checked); the action
map's no-direct-effect assumption holds.

**Honest cost:** exploration means ε of traffic acts randomly within
`safe_candidates`. With exploration-only evaluation, the effective sample is
about ε·n. The `check` command reports how long you'd need to log for a given
ε to reach a target interval width.

### 5.2 Level 2 — Sampled (marginalized IPS, no logprobs)

The logging policy was an LLM, nothing was randomized deliberately, but the
stored input is complete and the logging configuration can still be called.

**Procedure:** for each decision, re-run the logging configuration on the
stored input N times, apply the action map to each sample, and estimate

```
p̂₀(a | x) = (count(a) + α) / (N + α·k)        # α = 0.5 by default
```

The target policy's probabilities are estimated the same way when B is an
LLM. Samples are cached in `samples.jsonl`, so evaluation is deterministic
afterward and sampling never has to be repeated.

**Assumptions** (printed in the report):

1. **Complete input:** the stored input is everything the model saw (system
   prompt, history, tool definitions, retrieved documents). *Partly
   checkable:* a hash of the stored input is compared with the trace when available.
2. **Replay fidelity:** the logging model behaves today as it did when logging.
   *Partly checkable:* the pinned model id must match, and the share of
   samples that reproduce the logged chosen action is reported. A large share
   of logged choices that never come up again in samples is a red flag.
3. **No direct effect** under the action map (§4.3).
4. **Enough samples:** 1/p̂ is biased upward when N is small, because p̂ is
   itself an estimate and a small p̂ gets a large weight. The report flags
   decisions where the chosen action appeared fewer than 3 times, and states
   the smoothing α.

**Not available if:** content capture was off (no stored input), the logging
model has been retired, or logging was deterministic. In the last case the
logger has no overlap, and only targets that agree with it can be evaluated;
the tool reports that rather than an estimate.

**Cost:** `decisions × N × (1 + [target is LLM])` model calls. Default
`N = 32`. `agentope check` prints the estimated call count. `--sample 2000`
evaluates a random subset of decisions.

### 5.3 Level 3 — Estimated

No logged or sampled propensities. A model of the logging policy,
`π̂₀(a | context)`, is fit from the logged (context, chosen) pairs
(multinomial logistic regression by default; cross-fitted).

**Assumptions:**

1. **No unmeasured confounding:** every input that influenced the logging
   choice *and* the outcome is in `context`. **Not checkable from data.**
   Anything the agent saw that isn't in `context` (retrieved documents,
   conversation tone) can bias the result in either direction.
2. **Well-specified propensity model** (calibration is reported).
3. **Overlap** (checked through the weight diagnostics).

**Guard:** refuses to run without `--accept-unverifiable` (CLI) or
`accept_unverifiable=True` (Python). The refusal message lists assumption 1
in plain words.

**Sensitivity analysis (v0.3):** reports the **break-even Γ**, the smallest
amount of unmeasured confounding (in the marginal sensitivity model) that
would erase the estimated improvement. "The improvement holds unless hidden
factors shift the logging odds by more than 1.8×" is something people can act on.

### 5.4 Level 4 — Modeled

No usable propensities at all. The user supplies an outcome model
`q(context, action) -> expected outcome` (a regression, or an LLM judge
calibrated against real outcomes), and the tool reports the direct-method
estimate.

**Assumption:** the outcome model is correct for actions B takes that A
rarely took. **Not checkable from data.** The report shows calibration on
the actions that *were* logged, and states that this says nothing about
actions that weren't.

**Guard:** same as Level 3. Verdict is never better than `weak`.

### 5.5 Assumptions at a glance

| Assumption | L1 Logged | L2 Sampled | L3 Estimated | L4 Modeled | Checkable? |
|---|:-:|:-:|:-:|:-:|---|
| Correct propensities | logged | estimated by sampling | modeled | — | L1 yes · L2 partly · L3 calibration only |
| No direct effect (action map) | ✓ | ✓ | ✓ | ✓ | no (a design choice) |
| Overlap / support | ✓ | ✓ | ✓ | — | yes (ESS, support checks) |
| Complete stored input | | ✓ | | | partly (hash) |
| Replay fidelity | | ✓ | | | partly (model id, reproduction rate) |
| No unmeasured confounding | | | ✓ | ✓ | **no** |
| Outcome model correct off-policy | | | | ✓ | **no** |
| Downstream effects as in §4.5 | ✓ | ✓ | ✓ | ✓ | no |
| Outcome join correct (§6.2) | ✓ | ✓ | ✓ | ✓ | partly (match rates) |

---

## 6. Data formats

All files are JSON Lines (`.jsonl`, optionally `.gz`, detected by content).
Unknown fields are ignored, for forward compatibility.

### 6.1 `decisions.jsonl`

```json
{
  "decision_id": "conv-8812:3",
  "t": 1763280000.0,
  "decision_point": "tool_choice",
  "context": {"intent": "refund", "turn": 3, "tier": "pro"},
  "candidates": ["search", "lookup_order", "escalate", "__none__"],
  "chosen": "lookup_order",
  "propensity": null,
  "propensity_source": null,
  "explored": false,
  "join_key": "conv-8812",
  "input_ref": "inputs/conv-8812-3.json",
  "logging_config": {"model": "provider/model-2026-09-01", "temperature": 0.7}
}
```

| Field | Required | Notes |
|---|:-:|---|
| `decision_id` | ✓ | unique |
| `t` | ✓ | decision time (unix seconds) |
| `decision_point` | ✓ | one per evaluation run |
| `context` | ✓ | flat dict; may be `{}` (L3 then has nothing to work with) |
| `candidates` | ✓ | action ids; must include `chosen` |
| `chosen` | ✓ | action id after the action map |
| `propensity` | | probability of `chosen`; set at L1, filled in by `agentope sample` at L2 |
| `propensity_source` | | `logged` · `sampled` · `estimated` · `null` |
| `explored` | | `true` if chosen by the ε-exploration coin (L1 for LLM decisions) |
| `n_samples` | | L2 only |
| `join_key` | ✓ | key for joining outcomes |
| `input_ref` | | path or URI of the stored input; needed for L2 and LLM targets |
| `logging_config` | | model id and sampling parameters; needed for L2 |

### 6.2 Outcomes and the join

```json
{"join_key": "conv-8812", "t": 1763283600.0, "value": 1.0}
```

CSV with the same columns is also accepted. The join rule:

- the **first** outcome with `decision.t ≤ outcome.t < decision.t + horizon`
  is the reward (`rewarded`);
- no outcome within the horizon gives `default_reward` (`expired`);
- outcomes matching no decision are counted and reported, not dropped silently.

`--horizon` is required. Reasonable defaults don't exist: a support ticket and
a purchase have very different horizons. `--default-reward` defaults to `0`,
and the share of expired decisions is shown prominently, because a high share
means the evaluation is mostly measuring the default.

When several decisions share a `join_key` (several turns in one
conversation), each gets the same outcome. The report flags this, because
then the evaluated decision gets credit or blame for an outcome other
decisions also influenced.

### 6.3 `target.jsonl`

```json
{"decision_id": "conv-8812:3", "probs": {"search": 0.1, "lookup_order": 0.7, "escalate": 0.2, "__none__": 0.0}}
```

Probabilities must sum to 1 over `candidates`. An optional
`"q_hat": {action: value}` field enables the doubly-robust estimator.

---

## 7. Interfaces

### 7.1 CLI

```sh
# 1. What can I evaluate with what I have? (no LLM calls, no outcomes needed)
agentope check --traces traces.otlp.json --decision-point tool_choice

# 2. Turn traces into decisions (+ stored inputs if content capture was on)
agentope import --traces traces.otlp.json --map tool -o decisions.jsonl

# 3. (Level 2 only) estimate propensities by sampling — the only step that calls an LLM
agentope sample decisions.jsonl --n 32 --target target.yaml -o samples.jsonl

# 4. Evaluate
agentope eval decisions.jsonl --outcomes outcomes.csv --horizon 7d \
              --target target.yaml        # or target.jsonl
```

For the common case, steps 2–4 collapse to one command:

```sh
agentope eval --traces traces.otlp.json --outcomes outcomes.csv --horizon 7d --target target.yaml
```

That runs import, and sampling when the evidence level needs it (after
printing the estimated call count and asking for confirmation unless
`--yes`), then evaluation.

`target.yaml` (LLM target policy):

```yaml
decision_point: tool_choice
type: llm
endpoint: openai-compatible        # base_url + API key from env
model: provider/model-2026-11-01
temperature: 0.7
system_prompt: prompts/v2.txt      # replaces the system message in each stored input
tools: unchanged                   # or a path to new tool definitions
```

Anything beyond replacing the model, system prompt, temperature and tools
needs the Python API.

Exit codes: `0` report produced · `1` refused (a guard fired) · `2` usage error.

### 7.2 Python

```python
import agentope as ao

decisions = ao.import_traces("traces.otlp.json", decision_point="tool_choice", action_map="tool")
print(ao.check(decisions))                      # readiness report

report = ao.evaluate(
    decisions,
    outcomes="outcomes.csv",
    horizon="7d",
    target=lambda ctx, cands: {"escalate": 1.0} if ctx["tier"] == "pro" else {"__none__": 1.0},
)
print(report)          # human summary
report.to_json()       # machine-readable
```

An LLM target in Python is a function from stored input to model request:

```python
def v2(stored_input):
    return {**stored_input, "messages": swap_system(stored_input["messages"], V2_PROMPT)}

report = ao.evaluate(decisions, outcomes=..., horizon="7d",
                     target=ao.LLMPolicy(render=v2, model="provider/model-2026-11-01", n=32))
```

### 7.3 Logging helpers (to reach Level 1)

```python
# Code-made decision: random choice with a recorded probability
choice = ao.randomize("router", candidates=["small", "large"], probs=[0.8, 0.2],
                      context=ctx, join_key=conv_id, log=logfile)

# LLM-made decision: epsilon-explore within approved alternatives
choice = ao.explore("tool_choice", llm_choice=tool_name,
                    safe_candidates=["search", "lookup_order", "__none__"],
                    epsilon=0.05, context=ctx, join_key=conv_id, log=logfile)
```

`explore` never draws from outside `safe_candidates`. Deciding which actions
are safe to take at random is the user's responsibility, and the docs say so
plainly.

---

## 8. Estimators and diagnostics

| Estimator | When | Notes |
|---|---|---|
| **SNIPS** (headline) | L1–L3 | self-normalized; lower variance, slightly biased |
| IPS | L1–L3 | unbiased when assumptions hold; always shown next to SNIPS |
| DR | L1–L3 with `q_hat` or an outcome model | doubly robust |
| DM | L4 | outcome model only |

No weight clipping: clipping trades bias for variance
silently. The verdict reports problems instead of hiding them.

**Diagnostics** (always reported; an estimate is never shown without them):

- `n` decisions, `rewarded` / `expired` / `unmatched` counts
- effective sample size `(Σw)² / Σw²`, and ESS as a share of n
- max weight, minimum propensity
- support violations: target probability on actions with zero logged or sampled probability
- L2: reproduction rate of the logged choice, decisions with low counts
- L3: propensity-model calibration
- 95% interval for the difference from the logging policy (bootstrap with a fixed seed, so deterministic)

**Verdict rules (v1 defaults, configurable):**

| Verdict | Condition |
|---|---|
| `unreliable` | any support violation carrying more than 1% of target mass, or ESS < 50, or more than 50% expired |
| `weak` | L3 or L4, or ESS < 10% of n, or more than 20% expired, or L2 reproduction rate < 50% |
| `ok` | otherwise |

An `unreliable` result still shows the numbers, but the headline reads
"no trustworthy estimate", not a value.

---

## 9. The report

```
agentope · tool_choice · target: prompts/v2.txt
────────────────────────────────────────────────────────────
Evidence level   L2 Sampled (N=32, α=0.5)
Decisions        4,812   (rewarded 3,950 · expired 862 · 17.9%)

Logging policy   0.612  realized mean outcome
Target policy    0.655  SNIPS   (IPS 0.661 · DR 0.649)
Difference      +0.043  95% CI [+0.011, +0.074]

Diagnostics      ESS 1,204 (25% of n) · max weight 9.8 · support violations 0
                 logged choice reproduced in samples: 81%

Verdict          ok

This estimate assumes:
  • Which tool is called matters, not its arguments or wording   (action map: tool)
  • Stored inputs are complete and the logging model is unchanged since logging
  • Only tool_choice changes; later steps behave as they did under the logging policy
  • An outcome missing within 7 days means outcome = 0

To strengthen this:
  • Log with agentope.explore (ε=0.05) for ~3 weeks → Level 1 at this traffic level
```

`report.to_json()` contains the same content with stable field names:
`level`, `estimates`, `diagnostics`, `verdict`, `assumptions[]`,
`how_to_improve[]`, and `inputs` (file hashes, versions, seed) for
reproducibility.

---

## 10. Readiness report (`agentope check`)

Runs on traces alone, with no outcomes, no LLM calls and no target policy.

```
tool_choice · 4,812 decisions found in traces

  Level 1 Logged     ✗  no logged propensities  → use agentope.explore or agentope.randomize
  Level 2 Sampled    ✓  stored inputs: 4,812/4,812 · logging model still available · temperature 0.7
                        est. cost at N=32: 154k calls (logging) + 154k (LLM target)
  Level 3 Estimated  ✓  context has 3 features — consider adding: retrieved_doc_count, customer_tier
  Level 4 Modeled    ✓  needs an outcome model

  Candidates: tool definitions found on 98% of decisions; __none__ added
  Warnings:   302 decisions called 2+ tools in parallel → consider action map `toolset`
```

---

## 11. Importing traces

v0.3 supports OTLP JSON exports using the **OpenTelemetry GenAI** conventions
(`gen_ai.*`) or **OpenInference**. Langfuse and Phoenix exports go through
the same path.

| Decision field | Source in the trace |
|---|---|
| decision | a model (chat) span whose response contains tool calls, or none (`__none__`) |
| `chosen` | tool name(s) in the response, after the action map |
| `candidates` | tool definitions on the request, when recorded; else the union seen in the data (flagged) |
| `t`, `join_key` | span start time; trace or session id (configurable) |
| `input_ref` | input messages, **only if content capture was enabled** |
| `logging_config` | request model, response model, temperature |
| `context` | user-specified attribute extraction (`--context intent=attr.path,…`) |

Known limits: GenAI conventions are still in *Development* status, and
attribute names differ between instrumentations. Content capture is usually
opt-in, so many existing traces support only L3 and L4. `check` says so up
front.

---

## 12. Determinism and reproducibility

- `sample` is the only step that calls an LLM. Its output (`samples.jsonl`)
  records model id, parameters, sample count and raw action counts per decision.
- `eval` over a fixed set of files is deterministic: fixed-order arithmetic,
  and a seeded bootstrap (seed recorded in the report).
- Every report records the SHA-256 of each input file and the package version.

---

## 13. Milestones

| Version | Scope |
|---|---|
| **v0.1** | `decisions.jsonl` + outcomes join; L1 and L3 with guard; SNIPS/IPS; diagnostics, verdicts, report; Python callable and `target.jsonl` targets; `randomize` / `explore` helpers |
| **v0.2** | L2: `sample` with an OpenAI-compatible endpoint, caching, cost estimates; LLM target policies; `check` |
| **v0.3** | OTLP import (GenAI + OpenInference); DR; L3 break-even Γ |
| **v0.4** | L4 with calibration display |

---

## 14. Open questions

1. **Default N for sampling.** Run a pilot on one real agent dataset to find
   the smallest N at which the estimates stop changing much. 32 is a placeholder.
2. **Smoothing α.** Additive smoothing avoids zero propensities at the cost of
   some bias. Compare against dropping decisions whose chosen action never
   comes up again in sampling (which has its own selection bias).
3. **Verdict thresholds** (§8) are heuristics. Calibrate them in simulation:
   how often does each verdict's interval cover the true value?
4. **Shared outcomes across turns** (§6.2): is a per-conversation evaluation
   mode (all decisions in a conversation under B) worth the variance in v1, or should it wait?
5. **Name.** `agentope` is descriptive but bland; check that it's free on PyPI either way.

---

## References

- Saito, Y. & Joachims, T. (2022). *Off-Policy Evaluation for Large Action Spaces via Embeddings.* ICML. (MIPS; the no-direct-effect assumption.)
- Saito, Y., Ren, Q. & Joachims, T. (2023). *Off-Policy Evaluation for Large Action Spaces via Conjunct Effect Modeling.* ICML. (OffCEM.)
- Kallus, N. & Zhou, A. (2018). *Confounding-Robust Policy Improvement.* NeurIPS. (Marginal sensitivity model for policy evaluation.)
