# agentope: implementation progress

Tracks implementation against [`spec.md`](spec.md). Section numbers (§) refer to the spec.

**Legend:** `[ ]` not started · `[~]` in progress / partial · `[x]` done

**Status (2026-11-16):** v0.2 implemented: trace import (OTLP JSON, GenAI + OpenInference), `eval --traces`, `agentope.*` span attributes, `--absent-means-default`, on top of v0.1 (Levels 1 and 3, `eval`, logging helpers). 52 tests passing. Milestones were reordered at the owner's request: import moved to v0.2, Level 2 sampling to v0.3, DR / Γ / Level 4 to v0.4. Next: Level 2 sampling (§3).

---

## 0. Spec work

### 0.1 Open questions that block upcoming work

- [ ] **`samples.jsonl` schema** (§5.2, §12). Define the field layout: decision id, model id, parameters, N, raw action counts, input hash. *Blocks v0.3.*
- [ ] **YAML for `target.yaml`.** Dependencies are allowed, so PyYAML can be a dependency (or part of `[llm]`). Decide when building v0.3.
- [ ] **`check` timing.** Goal 1 promises a readiness report on existing traces. Import now exists, so `check` can run on traces in v0.3 without sampling.

### 0.2 Spec issues found while implementing (all resolved in `spec.md`)

- [x] **Success-only outcome logs.** Added `--absent-means-default` (§6.2, §8), chosen by the owner.
- [x] **Logging baseline uses all decisions** at the decision point, also when only explored rounds are included (§8).
- [x] **Level selection wording** (§5): strongest level the data supports; never mixed.
- [x] **New optional fields** in §6.1: `safe_candidates`, `logging_probs`, `action_map`, `candidates_source`, `input_sha256`.
- [x] **Support checks** without a full logging distribution use "actions chosen in the logs" (§8).
- [x] **Timestamps:** unix seconds or ISO 8601 with a timezone (§6.1).
- [x] **Interval** details: cluster bootstrap by join key (§8).
- [ ] **Determinism (§12).** With numpy/scipy, reports are bit-reproducible for the same inputs, seed and library versions on the same platform; across machines, BLAS differences may change the last digits at Level 3. Say so in §12.

### 0.3 Follow-ups for users with thin traces

- [ ] Add a "What you can evaluate with what you have" section to the spec: content, attributes only, or neither, mapped to levels and target types.
- [ ] State plainly in §1, §4.4 and `check` that LLM targets (prompt or model changes) need stored inputs at every level.
- [x] §11: when response content is missing, `chosen` comes from `execute_tool` spans; `__none__` when a model span has no tool execution after it.
- [x] §5.5 / §9: "candidates inferred from the data" is printed as an assumption.
- [~] §8: empty or near-empty `context` at Level 3. *Done:* a warning when context has no usable features. *Open:* whether this should force `unreliable`.
- [x] §7.3: `explore` / `randomize` can write span attributes via `ao.span_attributes`, read back by import.
- [ ] Notes for self-hosted open-weight models: pin weights and serving config, and warn that output can vary with batch size (vLLM and similar), which affects replay fidelity.
- [ ] `check`: say which action maps are available when there is no content (`tool` and `toolset` only).

---

## 1. Project setup

- [ ] Confirm the name is free on PyPI (§14 Q5).
- [x] `pyproject.toml` via uv: package `agentope` 0.2.0 (src layout, `uv_build`), Python ≥ 3.14, numpy and scipy, console script `agentope`. *Not yet:* the `[llm]` extra (v0.3).
- [x] Layout: `src/agentope/{io,decisions,outcomes,targets,propensity_model,estimators,verdict,report,evaluate,helpers,traces,action_maps,importer,cli}.py`.
- [~] Dev tooling: pytest and ruff. *Open:* type checking, CI.
- [x] `argparse` CLI with exit codes `0` / `1` refused / `2` usage error.

---

## 2. v0.1: core evaluation (Levels 1 and 3) — done

- [x] **Input:** JSONL reader (gzip by content, unknown fields ignored, `file:line` errors); `Decision` validation; outcomes as JSONL or CSV; horizon parser; `target.jsonl`; Python callable targets.
- [x] **Outcome join:** first outcome in `[t, t + horizon)`; `default_reward`; rewarded / expired / unmatched counts; shared join keys flagged.
- [x] **Propensities:** Level 1 logged and explored; Level 3 conditional logit (numpy/scipy, L-BFGS), cross-fitted by join key, with log loss vs. a context-free baseline and calibration error; Level 3 guard.
- [x] **Estimators:** IPS, SNIPS, no clipping; logging baseline over all decisions; vectorized cluster bootstrap.
- [x] **Diagnostics and verdict:** ESS, max weight, min propensity, support violations (and which check), configurable thresholds.
- [x] **Report:** text in the §9 layout and JSON; assumptions, warnings, `how_to_improve` (incl. ε-exploration time), input hashes.
- [x] **Helpers:** `randomize`, `explore` (never outside `safe_candidates`); log to path, file object or callable.
- [x] **Tests:** simulation with exact ground truth, recovery at both levels, CI coverage, determinism, edge cases, golden report.
- [ ] Performance regression test. (Measured 2026-11-16: 100k decisions in ~1.6 s at Level 1, ~2.3 s at Level 3.)

---

## 3. v0.2: trace import — done

- [x] OTLP JSON reader: Collector file-exporter lines or one document, optionally gzipped; typed attribute values; parent/child links; duplicate spans dropped.
- [x] Span kinds for OpenTelemetry GenAI (`gen_ai.operation.name`) and OpenInference (`openinference.span.kind`).
- [x] Decision selection: first model call per agent run (default) or every call (`--decisions all`, adds `llm_call_index`).
- [x] `chosen`: `agentope.chosen` → tool spans after the model span → response content → finish reason; undecidable spans skipped and counted; tool requests that never ran become `__none__` and are counted.
- [x] Candidates: `agentope.candidates` → tool definitions (+ `__none__`) → inferred (flagged, printed as an assumption).
- [x] `--context name=attribute,…` looked up on span, ancestors, resource; missing values counted.
- [x] Join key: `--join-key`, else `gen_ai.conversation.id`, `session.id`, trace id.
- [x] `logging_config` from request/response model, temperature, top_p, max_tokens (incl. OpenInference `llm.invocation_parameters`).
- [x] Stored inputs (content capture on): chat-completions request body (system instructions, messages incl. tool calls and tool results, tool definitions, sampling parameters) in `inputs/`, plus `input_sha256`.
- [x] Action maps: `tool`, `toolset`, `tool+args:<fields>`, custom `module:function`; parallel calls counted with a `toolset` hint.
- [x] `agentope import` with the summary shown in `index.html`; `agentope eval --traces` (summary on stderr); `ao.import_traces()`.
- [x] `ao.span_attributes()` for `explore` / `randomize`; round trip tested.
- [x] `--absent-means-default` / `absent_means_default=True`.
- [x] Tests: import → eval gives the same estimates as evaluating the decisions directly (explore, logged and unlogged data); GenAI with content; OpenInference; first vs. all; parallel calls; skips; context lookup; CLI.
- [ ] Test against real Langfuse and Phoenix exports (need sample files).
- [ ] Older GenAI conventions that put content in span *events* (`gen_ai.choice`, `gen_ai.user.message`) instead of attributes: not read yet.
- [ ] Other OpenInference input forms (multimodal parts beyond text, `input.value` JSON) are only partly converted to stored inputs.

---

## 4. v0.3: sampling (Level 2) and `check`

- [ ] Write the `samples.jsonl` format (from §0.1).
- [ ] Stored-input loader (`input_ref` relative to the decisions file) and an `input_sha256` check.
- [ ] OpenAI-compatible client under `[llm]`: `base_url` and key from env; concurrency limit, retries with backoff, rate-limit handling. Tests use a local mock server (owner's choice).
- [ ] `agentope sample`: N samples per decision, action map applied to each sampled response, results cached, resumable after interruption.
- [ ] `p̂ = (count + α) / (N + α·k)`, default α = 0.5 (§5.2).
- [ ] Replay-fidelity diagnostics: pinned model id must match; reproduction rate of the logged choice; decisions where the chosen action appeared < 3 times.
- [ ] Detect deterministic logging (temperature 0, or all samples identical): report the lack of overlap instead of an estimate.
- [ ] Verdict rule: a reproduction rate < 50% gives `weak`.
- [ ] `target.yaml`: model, system prompt replacement, temperature, tools (`unchanged` or a path).
- [ ] `ao.LLMPolicy(render=, model=, n=)` in Python.
- [ ] Cost estimate; confirmation prompt unless `--yes`; `--sample N` seeded subset.
- [ ] `agentope check` readiness report (§10) on traces or decisions.
- [ ] One-shot `eval --traces` runs sampling when the level needs it.
- [ ] Pilot study: N at which estimates stabilize (§14 Q1); α vs. dropping decisions (§14 Q2).

---

## 5. v0.4: DR, sensitivity, Level 4

- [ ] DR estimator using `q_hat` from `target.jsonl` or a supplied outcome model.
- [ ] Level 3 break-even Γ under the marginal sensitivity model (Kallus & Zhou 2018), with a plain-language sentence in the report.
- [ ] Level 4: outcome model interface `q(context, action)`, direct method, calibration on logged actions with the caveat, guard as at Level 3, verdict capped at `weak`.

---

## 6. Documentation

- [x] `index.html`: what agentope is, evidence levels, guide, trace example, verdict meanings, troubleshooting.
- [~] **The trace example in `index.html`.** The commands and summary format now match the real CLI. Its numbers are still illustrative, not from a run. Turn it into a runnable example (simulated support agent → OTLP traces → import → eval) and use real output.
- [x] README: status, quickstart, trace import, `--absent-means-default`.
- [ ] Keep `index.html`, `README.md` and the CLI in sync as features land.

---

## 7. Research and calibration (ongoing)

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
| 2026-11-16 | `--absent-means-default` flag for success-only outcome logs | Owner's choice; keeps the expired rules for everyone else |
| 2026-11-16 | Trace import before Level 2 (milestones reordered) | Owner's choice; lets users start from the traces they already have |
| 2026-11-16 | Stored inputs are OpenAI-compatible chat-completions request bodies | Owner's choice; replayable against vLLM, Ollama, llama.cpp and hosted APIs |
| 2026-11-16 | Import takes the first model call per agent run by default | One decision per turn, made before any tool result; `--decisions all` for every call |
| 2026-11-16 | Tool spans beat response content for `chosen` when the export has tool spans | They show what actually ran (e.g. after exploration overrode the model) |
| 2026-11-16 | Level 2 tests will use a mock server only | Owner's choice |
