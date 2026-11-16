# agentope

Offline evaluation of LLM agent decisions, without logprobs.

> Would this agent decision have gone better under a different policy?

`agentope` estimates how a different policy would have done at **one decision
point** (which tool to call, which model to route to, which prompt variant to
use) from logs you already have. Every number comes with its evidence level,
diagnostics, a verdict (`ok` / `weak` / `unreliable`) and the assumptions it
rests on. See [`spec.md`](spec.md) for the design and [`progress.md`](progress.md)
for what is implemented.

**Status: v0.2.** Level 1 (logged propensities, including ε-exploration),
Level 3 (estimated propensities) and import of OpenTelemetry traces (GenAI and
OpenInference conventions) are available. Level 2 (sampling the logging LLM)
is next. [`index.html`](index.html) has a guided walkthrough.

## Install

```sh
uv sync            # in this repository
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
