# agentope

Offline evaluation of LLM agent decisions, without logprobs.

> Would this agent decision have gone better under a different policy?

`agentope` estimates how a different policy would have done at **one decision
point** (which tool to call, which model to route to, which prompt variant to
use) from logs you already have. Every number comes with its evidence level,
diagnostics, a verdict (`ok` / `weak` / `unreliable`) and the assumptions it
rests on. See [`spec.md`](https://github.com/liminalplanes/agentope/blob/main/spec.md) for the design and [`progress.md`](https://github.com/liminalplanes/agentope/blob/main/progress.md)
for what is implemented.

**Status: v0.3.** Level 1 (logged propensities, including ε-exploration),
Level 2 (sampling the logging model on stored inputs), Level 3 (estimated
propensities), LLM target policies, `check` and import of OpenTelemetry traces
(GenAI and OpenInference conventions) are available. Level 4 and the
doubly-robust estimator are next. The project site and documentation live in
[`site/`](https://github.com/liminalplanes/agentope/blob/main/site/README.md) (`cd site && npm install && npm run dev`).

## Install

```sh
uv sync --all-extras   # in this repository; the llm extra is needed for sampling
uv run agentope --help
```

## Quickstart

1. **Log decisions with known probabilities** (Level 1):

   ```python
   import agentope as ao

   # an LLM-made decision: with probability ε, take a random safe alternative
   tool = ao.explore("tool_choice", llm_choice=tool_name,
                     safe_candidates=["search", "lookup_order", "__none__"],
                     epsilon=0.05, context={"intent": intent, "tier": tier},
                     join_key=conversation_id, log="decisions.jsonl")

   # a code-made decision: randomize with recorded probabilities
   model = ao.randomize("router", candidates=["small", "large"], probs=[0.8, 0.2],
                        join_key=conversation_id, log="decisions.jsonl")
   ```

2. **Record outcomes** with the same join key, as JSONL or CSV:

   ```
   join_key,t,value
   conv-8812,1763283600,1
   ```

3. **Evaluate a target policy**, given as a Python function or a `target.jsonl`:

   ```python
   # policy.py
   def escalate_pro(context, candidates):
       return {"escalate": 1.0} if context["tier"] == "pro" else {"__none__": 1.0}
   ```

   ```sh
   uv run agentope eval decisions.jsonl --decision-point tool_choice \
       --outcomes outcomes.csv --horizon 7d --target policy.py:escalate_pro
   ```

   Or in Python:

   ```python
   report = ao.evaluate("decisions.jsonl", outcomes="outcomes.csv", horizon="7d",
                        target=escalate_pro, decision_point="tool_choice")
   print(report)
   report.to_json()
   ```

## From traces

Already tracing your agent with OpenTelemetry? Import an OTLP JSON export
(e.g. from the Collector's file exporter). No prompts or message content are
needed; context comes from span attributes you name:

```sh
uv run agentope import --traces traces.otlp.json.gz \
    --context intent=app.intent,tier=app.customer_tier -o decisions.jsonl
uv run agentope eval decisions.jsonl --outcomes outcomes.csv --horizon 7d \
    --target policy.py:escalate_pro
# or in one step: agentope eval --traces traces.otlp.json.gz --context … --outcomes …
```

To get Level 1 data into the traces, let `explore` write onto the model span:

```python
ao.explore(..., log=lambda record: span.set_attributes(ao.span_attributes(record)))
```

If your system only records an outcome when something good happens, pass
`--absent-means-default` so missing outcomes count as the default reward
instead of making the result unreliable.

## No exploration yet? Sample the model (Level 2)

If content capture was on (so `import` wrote stored inputs) and you can still
run the logging model, agentope can estimate propensities by asking the model
again, N times per decision, on an OpenAI-compatible endpoint (vLLM, Ollama,
llama.cpp, hosted APIs):

```sh
uv run agentope check decisions.jsonl                  # what's possible, and the call count
uv run agentope sample decisions.jsonl -o samples.jsonl --n 32 \
    --base-url http://localhost:8000/v1                 # the only step that calls an LLM
uv run agentope eval decisions.jsonl --samples samples.jsonl \
    --outcomes outcomes.csv --horizon 7d --target policy.py:escalate_pro
```

To evaluate a prompt or model change, describe it as an LLM target and sample
it too:

```yaml
# v2.yaml
type: llm
model: qwen2.5-7b-instruct
system_prompt: prompts/v2.txt     # replaces the system message
temperature: 0.7
```

```sh
uv run agentope sample decisions.jsonl -o samples.jsonl --target v2.yaml --base-url …
uv run agentope eval decisions.jsonl --samples samples.jsonl --target v2.yaml …
```

Sampling resumes where it stopped and reuses what's already in `samples.jsonl`.
The report checks replay fidelity: how often the logged choice comes up again,
whether a different model answered, and whether stored inputs changed.

## Level 3

Without logged propensities, `agentope` falls back to Level 3. Level 3 models
the logging policy from `context` and refuses to run until you pass
`--accept-unverifiable`, because it assumes everything that influenced both the
choice and the outcome is in `context`, and that cannot be checked from data.

Exit codes: `0` report produced · `1` refused · `2` usage error.

## Development

```sh
uv run pytest
uv run ruff check src tests && uv run ruff format src tests
UPDATE_GOLDEN=1 uv run pytest tests/test_evaluate.py::test_golden_text_report  # refresh golden report
```
