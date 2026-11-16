# agentope: implementation progress

Tracks implementation against [`spec.md`](spec.md). Section numbers (§) refer to the spec.

**Legend:** `[ ]` not started · `[~]` in progress / partial · `[x]` done

**Status (2026-11-16):** v0.3 implemented: Level 2 (`agentope sample` against OpenAI-compatible endpoints, resumable `samples.jsonl`, replay diagnostics), LLM target policies (`target.yaml`, `ao.LLMPolicy`) and `agentope check`, on top of v0.2 (trace import) and v0.1 (Levels 1 and 3). 61 tests passing. Next: v0.4 (DR, break-even Γ, Level 4), or the hardening items in §1.

---

## 0. Spec work

### 0.1 Open questions

- [x] **`samples.jsonl` schema**: one line per (decision, policy) with raw counts (spec §5.2).
- [x] **YAML for `target.yaml`**: PyYAML in the `llm` extra.
- [x] **`check` timing**: shipped with Level 2; runs on traces or decisions.
- [ ] **Default N and α** (§14 Q1–Q2). Simulation evidence: at N = 32 a logged choice with true propensity ≈ 0.11 sometimes never comes up, its smoothed propensity drops to 0.015 and weights reach ~68 (ESS < 10% of n → `weak`). N = 64 fixed it there. Consider raising the default N, or making `check` recommend N from the smallest propensity you need to resolve.

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

- [x] PyPI name `agentope` was free (checked 2026-11-16).
- [x] Release setup: Apache-2.0 `LICENSE`, package metadata (author Liminal Planes, URLs, classifiers, `py.typed`), `bump-my-version` config (pyproject, site version, Python API docs), `Makefile` (`make check`, `make release BUMP=…`), GitHub Actions `release.yml` (tag → test → build → PyPI via trusted publishing → GitHub release) and `ci.yml` (Python and site on every push and PR).
- [ ] Before the first release: PyPI trusted publisher (pending) and the `pypi` GitHub environment.
- [x] `pyproject.toml` via uv: package `agentope` 0.3.0 (src layout, `uv_build`), Python ≥ 3.14, numpy and scipy, console script `agentope`. `llm` extra with httpx and PyYAML.
- [x] Layout: `src/agentope/{io,decisions,outcomes,targets,propensity_model,estimators,verdict,report,evaluate,helpers,traces,action_maps,importer,llm,sampling,checks,cli}.py`.
- [~] Dev tooling: pytest, ruff, CI. *Open:* type checking for the Python package.
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
- [x] `agentope import` with the summary shown in the docs (From traces); `agentope eval --traces` (summary on stderr); `ao.import_traces()`.
- [x] `ao.span_attributes()` for `explore` / `randomize`; round trip tested.
- [x] `--absent-means-default` / `absent_means_default=True`.
- [x] Tests: import → eval gives the same estimates as evaluating the decisions directly (explore, logged and unlogged data); GenAI with content; OpenInference; first vs. all; parallel calls; skips; context lookup; CLI.
- [ ] Test against real Langfuse and Phoenix exports (need sample files).
- [ ] Older GenAI conventions that put content in span *events* (`gen_ai.choice`, `gen_ai.user.message`) instead of attributes: not read yet.
- [ ] Other OpenInference input forms (multimodal parts beyond text, `input.value` JSON) are only partly converted to stored inputs.

---

## 4. v0.3: sampling (Level 2) and `check` — done

- [x] `samples.jsonl` format (spec §5.2); latest line per (decision, policy) wins.
- [x] Stored-input loader (`input_ref` relative to the decisions file) and hash check against `input_sha256` from import (one canonical hash shared by import and sampling).
- [x] OpenAI-compatible client in the `llm` extra (httpx): `--base-url` / `AGENTOPE_BASE_URL`, `AGENTOPE_API_KEY` / `OPENAI_API_KEY`; retries with exponential backoff and jitter on 408/409/425/429/5xx and transport errors, honouring `Retry-After`; other 4xx fail at once.
- [x] `agentope sample` / `ao.sample()`: N samples per decision and policy, action map applied to each response, `--n-per-request` via the `n` parameter, `--concurrency`, `--sample K` seeded subset, `--model` override, `--no-logging`; resumes by skipping unchanged (decision, policy, model, params, request, action map, N).
- [x] Cost shown before sampling; asks for confirmation, refuses without `--yes` when not in a terminal.
- [x] Level 2 in `eval --samples`: `p̂ = (count + α) / (N + α·k)`, α = 0.5 (`--alpha`); support = actions never produced in samples; default level order 1 → 2 → 3.
- [x] Replay diagnostics: reproduction rate (< 50% → `weak`), decisions with < 3 matching samples, response-model mismatch share, stored-input hash changes, failed and off-candidate samples, "same answer in every sample" (no overlap) warning.
- [x] LLM targets: `target.yaml` / `.json` (`type: llm`; `name`, `model`, `system_prompt` as text or file, `temperature`, `top_p`, `max_tokens`, `tools: unchanged | file`; anything else refused with a pointer to the Python API) and `ao.LLMPolicy` (overrides or `render`). Probabilities = raw sample frequencies; off-candidate samples count as support violations.
- [x] `agentope check` / `ao.check()` (§10) on traces or decisions: levels with reasons, call cost at N (logging + LLM target), context features, candidate sources, import warnings, best available level; `--json`.
- [x] Tests with a local mock server: Level 2 recovers the true difference for a callable target and for an LLM target; resume and cache keys; 429 retries and 400 failures; changed model flagged; guards; `LLMPolicy`; `check`; CLI; traces with content → import → sample → eval.
- [ ] One-shot `eval --traces` that samples when the level needs it (now: import + evaluate; sampling is a separate step).
- [ ] Deterministic logging is detected from samples (every sample identical) and from `temperature: 0` in `check`; `eval` doesn't refuse, it warns.
- [ ] Try against a real vLLM / Ollama server (tests use the mock only, by the owner's choice).
- [ ] Pilot study on real data: N at which estimates stabilize (§14 Q1); α vs. dropping decisions (§14 Q2).

---

## 5. v0.4: DR, sensitivity, Level 4

- [ ] DR estimator using `q_hat` from `target.jsonl` or a supplied outcome model.
- [ ] Level 3 break-even Γ under the marginal sensitivity model (Kallus & Zhou 2018), with a plain-language sentence in the report.
- [ ] Level 4: outcome model interface `q(context, action)`, direct method, calibration on logged actions with the caveat, guard as at Level 3, verdict capped at `weak`.

---

## 6. Documentation and site

- [x] Site in `site/`: TanStack Start (React 19, Vite 8), Tailwind CSS v4, shadcn/ui (Radix), Geist fonts bundled, light/dark/system theme without a flash, Biome. Every page prerendered to static HTML (`npm run build` → `dist/client`).
- [x] Landing page, in the order a developer needs it: **what it does** (hero: what you give it → what you get back, real numbers), **how it works** (picture of real conversations + comparison with LLM-as-judge and A/B tests), **what you can evaluate** (one decision changed: tool choice, routing, handover, a prompt or model at that step; not a fit: a whole new agent, free-text quality, unrecorded outcomes), **evidence levels and verdicts**, a **worked example with the traces you already have** (Level 2: check → import → sample → eval → answer with the true value), and **what you could add for better evidence** (the same rule at Level 3, 2 and 1 on a shared scale, real results with the true value; Level 3's range just misses it, which is the point).
- [x] Docs in MDX (`site/src/content/docs/`) with sidebar from frontmatter, "On this page" with scroll tracking, previous/next, copyable code blocks (Shiki, dual theme), callouts and verdict badges. Each page is its own chunk; the nav reads frontmatter only.
- [x] Pages: Introduction, Quickstart, Evidence levels, Reading a report, From traces, Sampling the model, CLI, Python API, Data formats. The CLI page comes from the real `--help` output; the Python API page from the real signatures.
- [x] Removed the hand-written root `index.html` and `guide.html` (content moved into the site).
- [x] Landing page "Works with your stack": traces (OpenTelemetry GenAI, OpenTelemetry Collector, OpenInference: tested; Arize Phoenix, Langfuse: should work) and model servers for Level 2 (any OpenAI-compatible API: tested; vLLM, Ollama, llama.cpp: should work), with logos (Simple Icons, CC0, where available; otherwise the project's GitHub avatar in `site/public/logos/`, shown in grayscale) and links. Move entries to "tested" as real exports and servers are tried.
- [ ] **Generate the Python API reference** from docstrings (it's hand-written for v0.3.0 and will drift). Options: a small script that runs `inspect` and writes MDX at build time, or griffe → JSON → MDX.
- [ ] **Hosting.** Pick a host. For GitHub Pages at `liminalplanes.github.io/agentope`, set a base path (`/agentope/`) in the router and Vite config, and add a Pages workflow. Root-domain hosts (Netlify, Vercel, Cloudflare Pages) need no change.
- [ ] Search (e.g. a ⌘K command palette over the docs, built from frontmatter and headings at build time).
- [x] Runnable example `examples/support_agent/`, two scenarios from one simulated world (`uv run python examples/support_agent/run.py`, ~15 s): **sampled** (unchanged agent, traces with messages, a local stand-in model server answers like the simulated model; landing page) and **explored** (10% ε-exploration; docs walkthrough). Current run: Level 2 +0.074 [+0.058, +0.090], true +0.080; Level 1 +0.066 [+0.022, +0.110], true +0.094.
- [ ] The docs' trace example and quickstart output are still illustrative; switch them to the example's real output.
- [ ] Keep the site, `README.md` and the CLI in sync as features land.

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
| 2026-11-16 | `samples.jsonl`: one line per (decision, policy), raw counts | Smoothing changes don't need re-sampling; resume by key |
| 2026-11-16 | LLM target probabilities are raw sample frequencies (no α) | They are never divided by, so smoothing would only add bias |
| 2026-11-16 | `LLMPolicy` is evaluated from samples, not sampled inside `evaluate` | Keeps all LLM calls in the explicit `sample` step (spec goal: deterministic evaluation) |
| 2026-11-16 | `httpx` and PyYAML in the `llm` extra | Spec §1: sampling is optional |
| 2026-11-16 | Version 0.3.0 | Level 2 milestone complete |
| 2026-11-16 | Landing page example uses Level 2 (no change to the agent); exploration is the docs walkthrough | Most teams arrive with traces and no exploration |
| 2026-11-16 | Fixed three messages found by running the example: import summary said Level 2 "once sampling lands"; Level 2 reports suggested `--n 64` when N was already 64 (now 2×N); support-violation advice mentioned exploration at Level 2 | Dogfooding |
