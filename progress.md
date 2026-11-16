# agentope: implementation progress

Tracks implementation against [`spec.md`](spec.md) (draft v0.1). Section numbers (§) refer to the spec.

**Legend:** `[ ]` not started · `[~]` in progress / partial · `[x]` done

**Status (2026-11-16):** v0.1 implemented (Levels 1 and 3, `eval`, logging helpers), 39 tests passing. Next: settle the v0.2 spec gaps (§0), then Level 2 sampling.

---

## 0. Spec work

### 0.1 Gaps that block implementation

- [ ] **`samples.jsonl` schema** (§5.2, §12). The spec lists what it records but gives no field layout. Define it: decision id, model id, parameters, N, raw action counts, input hash. *Blocks v0.2.*
- [x] **Partial target probabilities.** Missing candidates mean probability 0. Probabilities on non-candidates are an error. The sum must be within 1e-6 of 1; nothing is renormalized.
- [x] **Python callable targets from the CLI.** `--target module:function` or `--target path/to/file.py:function`.
- [x] **How the difference CI is computed** (§8). Percentile bootstrap of (SNIPS − logging mean), resampling whole join keys; 2000 resamples, seed 0 by default.
- [ ] **YAML parsing.** Dependencies are now allowed, so PyYAML can simply be a dependency (or part of `[llm]`). Decide when building v0.2.
- [ ] **`check` arrives too late.** Goal 1 promises a readiness report "on existing traces", but `check` is v0.2 and trace import is v0.3. Either let `check` run on `decisions.jsonl` in v0.2, or move a minimal importer earlier.

### 0.2 Spec issues found while implementing v0.1

- [ ] **The expired rule punishes success-only outcome logs.** Many systems record an outcome only when something good happens (a purchase, a resolved ticket). Then every failure counts as "expired", and the >50%-expired rule marks the result `unreliable`, although "no outcome = 0" is exactly right for that data. Proposal: an option such as `--absent-means-default` that says absence is the outcome, which turns off the expired-share verdict rules but keeps the share in the report.
- [ ] **Write into §3/§9: the logging baseline uses all decisions.** When only some decisions are included (e.g. only explored rounds at Level 1), the logging policy's realized mean is still taken over *all* decisions at the decision point. Using the explored rounds only would measure the uniform explorer, not the running policy, and inflate the difference. Implemented this way; the spec should say so.
- [ ] **Level selection wording (§1 vs §5).** §1 says "picks the strongest level the data supports"; §5 says "evaluates at the lowest level present". Implemented: Level 1 if any decision has a logged propensity (evaluating only those, with a warning and, unless all are explored, a "representative" assumption), otherwise Level 3. Update §5 to match.
- [ ] **Add the new optional fields to §6.1:** `safe_candidates` (pool used by exploration), `logging_probs` (full logging distribution, makes support checks exact), plus `llm_choice` and `epsilon` written by `explore`.
- [ ] **Support checks without a full logging distribution.** With only `propensity` recorded, zero-probability actions can't be known. Implemented proxy: actions never chosen in the logs. The report says which check was used. Put this in §8.
- [ ] **Timestamps.** Implemented: unix seconds or ISO 8601 *with* a timezone; naive timestamps are rejected. Put this in §6.
- [ ] **Determinism (§12).** With numpy/scipy, reports are bit-reproducible for the same inputs, seed and library versions on the same platform; across machines, BLAS differences may change the last digits at Level 3. Say so in §12.

### 0.3 Follow-ups for users with thin traces

- [ ] Add a "What you can evaluate with what you have" section: content, attributes only, or neither, mapped to levels and target types.
- [ ] State plainly in §1, §4.4 and `check` that LLM targets (prompt or model changes) need stored inputs at every level.
- [ ] §11: when response content is missing, find `chosen` from `execute_tool` spans (`gen_ai.tool.name`), and infer `__none__` when a chat span has no tool-execution children.
- [ ] §5.5 / §9: list "candidates inferred from the data" as a printed assumption whenever it applies.
- [~] §8: empty or near-empty `context` at Level 3. *Done:* a warning when context has no usable features. *Open:* whether this should force `unreliable`.
- [ ] §7.3: `explore` and `randomize` can also write span attributes (`agentope.propensity`, `agentope.explored`, `agentope.candidates`), so Level 1 data arrives in existing traces.
- [ ] Notes for self-hosted open-weight models: pin weights and serving config, and warn that output can vary with batch size (vLLM and similar), which affects replay fidelity.
- [ ] `check`: say which action maps are available when there is no content (`tool` and `toolset` only).

---

## 1. Project setup

- [ ] Confirm the name is free on PyPI (§14 Q5).
- [x] `pyproject.toml` via uv: package `agentope` (src layout, `uv_build`), Python ≥ 3.14, depends on numpy and scipy, console script `agentope`. *Not yet:* the `[llm]` extra (v0.2).
- [x] Layout: `src/agentope/{io,decisions,outcomes,targets,propensity_model,estimators,verdict,report,evaluate,helpers,cli}.py`.
- [~] Dev tooling: pytest and ruff (`uv run pytest`, `uv run ruff check`). *Open:* type checking, CI.
- [x] `argparse` CLI with exit codes `0` report produced, `1` refused, `2` usage error (§7.1).

---

## 2. v0.1: core evaluation (Levels 1 and 3)

### 2.1 Input

- [x] JSONL reader: gzip detected from magic bytes; unknown fields ignored; errors carry `file:line`.
- [x] `Decision` model and validation (required fields, `chosen ∈ candidates`, flat context, unique ids). Several decision points in one file need `--decision-point`.
- [x] Outcomes reader for JSONL and CSV (detected by content).
- [x] Horizon parser (`7d`, `12h`, `30m`, `90s`, or seconds).
- [x] `target.jsonl` reader with validation. `q_hat` is accepted but unused until DR (v0.3).
- [x] Python callable target wrapper `(context, candidates) -> probs`.

### 2.2 Outcome join (§6.2)

- [x] First outcome in `[t, t + horizon)`, ties by input order; `default_reward` otherwise.
- [x] `rewarded` / `expired` / `unmatched` counts; shared join keys flagged and listed as an assumption.
- [x] `--horizon` required.

### 2.3 Propensities

- [x] **Level 1, logged** and **explored** (propensity `1/k` over `safe_candidates`; only explored rounds used).
- [x] **Level 3, estimated:** conditional multinomial logit (numpy/scipy, L-BFGS), one-hot / 0-1 / standardized / null-indicator features, L2 penalty, 5-fold cross-fitting grouped by join key, log loss vs. a context-free baseline, calibration error.
- [x] Level selection and `--level`; Levels 2 and 4 give a clear "not available yet" error.
- [x] Level 3 guard (`--accept-unverifiable` / `accept_unverifiable=True`), refusal explains the assumption.

### 2.4 Estimators (§8)

- [x] IPS and SNIPS, no clipping.
- [x] Logging policy realized mean (over all decisions at the point, see §0.2).
- [x] Seeded cluster bootstrap CI for the difference (vectorized).

### 2.5 Diagnostics and verdict (§8)

- [x] n, rewarded/expired/unmatched, ESS and ESS/n, max weight, min propensity, support violations with target mass and the kind of check used.
- [x] Verdict rules with configurable `VerdictThresholds`; `unreliable` headline reads "no trustworthy estimate".

### 2.6 Report (§9)

- [x] Text renderer in the §9 layout, plus warnings.
- [x] `report.to_json()` with `level`, `estimates`, `diagnostics`, `verdict`, `verdict_reasons`, `assumptions`, `how_to_improve`, `warnings`, `inputs`.
- [x] Assumptions built from level, action map (`--map`, used for the report only until import exists), horizon, default reward and shared keys.
- [x] `how_to_improve` hints, including the ε-exploration time needed to reach Level 1 at the observed traffic rate.
- [x] `inputs`: SHA-256 of each input file (decisions, outcomes, target file), version, seed and settings.

### 2.7 Logging helpers (§7.3)

- [x] `ao.randomize(...)` records `propensity` and full `logging_probs`.
- [x] `ao.explore(...)` never draws outside `safe_candidates`; records `explored`, `safe_candidates`, `llm_choice`, `epsilon`.
- [x] Logs to a path, a file object or a callable; thread-safe; injectable RNG.

### 2.8 Interfaces

- [x] Python API `ao.evaluate(...)`.
- [x] CLI `agentope eval` with `--outcomes`, `--horizon`, `--target`, `--decision-point`, `--level`, `--accept-unverifiable`, `--default-reward`, `--map`, `--seed`, `--bootstrap`, `--folds`, `--json`, `-o`.

### 2.9 Tests

- [x] Simulation harness with exact ground truth (`tests/sim.py`).
- [x] Level 1 (logged and explored) and Level 3 recover the true difference.
- [x] CI coverage over 120 simulated datasets is within [88%, 99.5%].
- [x] Determinism: identical JSON across runs.
- [x] Join edge cases, validation errors, guards, support violations, never-agreeing targets, exit codes.
- [x] Golden text report (`tests/golden/`, regenerate with `UPDATE_GOLDEN=1`).
- [ ] Performance regression test. (Measured 2026-11-16: 100k decisions in ~1.6 s at Level 1, ~2.3 s at Level 3.)

---

## 3. v0.2: sampling (Level 2) and `check`

- [ ] Write the `samples.jsonl` format (from §0.1).
- [ ] Stored-input loader (`input_ref` as a path; URIs later) and an input-hash check against the trace (§5.2 assumption 1).
- [ ] OpenAI-compatible client under `[llm]`:
  - `base_url` and key from env
  - concurrency limit, retries with backoff, rate-limit handling
  - test against vLLM / Ollama / llama.cpp as well as hosted APIs
- [ ] `agentope sample`: N samples per decision, action map applied to each, results cached, resumable after interruption.
- [ ] `p̂ = (count + α) / (N + α·k)`, default α = 0.5 (§5.2).
- [ ] Replay-fidelity diagnostics: pinned model id must match; reproduction rate of the logged choice; decisions where the chosen action appeared < 3 times.
- [ ] Detect deterministic logging (temperature 0, or all samples identical): report the lack of overlap instead of an estimate.
- [ ] Verdict rule: a reproduction rate < 50% gives `weak`.
- [ ] Load `target.yaml`: model, system prompt replacement, temperature, tools (`unchanged` or a path).
- [ ] `ao.LLMPolicy(render=, model=, n=)` in Python.
- [ ] Cost estimate; confirmation prompt unless `--yes`; `--sample N` seeded subset.
- [ ] `agentope check` readiness report (§10): available levels, cost at N, context features, candidate coverage, parallel-tool warning.
- [ ] Pilot study: N at which estimates stabilize (§14 Q1); α vs. dropping decisions (§14 Q2).

---

## 4. v0.3: trace import, DR, sensitivity

- [ ] OTLP JSON parser (with or without gzip).
- [ ] Attribute mapping for OpenTelemetry GenAI (`gen_ai.*`) and OpenInference; handle differences between instrumentations.
- [ ] Decision extraction (§11):
  - chat spans with tool calls
  - fallback to `execute_tool` spans when content is missing
  - `__none__` inference
- [ ] Candidates from request tool definitions; otherwise the union seen in the data, flagged and added to the assumptions list.
- [ ] Write stored inputs to `inputs/` when content capture is on.
- [ ] `--context name=attr.path,…` extraction.
- [ ] `logging_config` from the request and response model and temperature.
- [ ] `toolset` and `tool+args:<fields>` action maps; custom Python maps.
- [ ] `agentope import`; one-shot `agentope eval --traces …` (import → sample if needed → eval).
- [ ] Test with Langfuse and Phoenix exports.
- [ ] DR estimator using `q_hat` from `target.jsonl` or a supplied outcome model.
- [ ] Level 3 break-even Γ under the marginal sensitivity model (Kallus & Zhou 2018), with a plain-language sentence in the report.

---

## 5. v0.4: Level 4 (modeled)

- [ ] Outcome model interface `q(context, action) -> expected outcome`.
- [ ] Direct-method estimator.
- [ ] Calibration on logged actions, with the stated caveat that it says nothing about actions that weren't logged.
- [ ] Guard as at Level 3; verdict capped at `weak`.

---

## 6. Research and calibration (ongoing)

- [ ] Calibrate verdict thresholds in simulation: coverage of each verdict's interval (§14 Q3).
- [ ] Decide whether a per-conversation evaluation mode belongs in v1 (§14 Q4).

---

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-16 | Removed all gittins references from the spec | Keep agentope standalone |
| 2026-11-16 | Python ≥ 3.14, uv for dependency management | Project was set up with `uv init` |
| 2026-11-16 | Depend on numpy and scipy (spec §1 updated) | ~10× faster bootstrap and Level 3 fitting; owner approved external dependencies |
| 2026-11-16 | Logging baseline = realized mean over all decisions at the point | Explored-only mean measures the uniform explorer, not the running policy |
| 2026-11-16 | Default level: Level 1 on the subset with logged propensities, else Level 3 | Exploration logs mix explored and non-explored rounds; only explored rounds have known propensities |
| 2026-11-16 | Bootstrap resamples join keys, not decisions | Decisions sharing a join key share an outcome |
| 2026-11-16 | Level 3 support = actions chosen somewhere in the logs | A fitted softmax never gives exactly 0; actions never chosen have no evidence at all |
| 2026-11-16 | Naive timestamps rejected | Guessing a timezone could silently shift outcome windows |
