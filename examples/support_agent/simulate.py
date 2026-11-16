"""Two weeks of the support agent in production, as OpenTelemetry traces.

Writes what a real deployment would have:

- traces.otlp.json.gz: one OTLP JSON request per conversation (as the OpenTelemetry
  Collector's file exporter writes them), GenAI conventions;
- helpdesk.csv: whether each ticket was resolved, from the helpdesk.

Two switches set the scenario:

- ``explore``: the agent wraps its first move in ``agentope.explore`` and writes the
  coin flip onto the model span with ``agentope.span_attributes`` (Level 1);
- ``capture_content``: the traces include the messages and tool definitions, as many
  tracing tools record them, so the model can be asked again later (Level 2).
"""

import csv
import gzip
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from world import (
    ACTIONS,
    INTENTS,
    P_ORDER_NUMBER,
    P_PRO,
    SAFE,
    SYSTEM_PROMPT,
    TOOLS,
    customer_message,
    model_policy,
    p_resolved,
)

import agentope as ao

MODEL = "qwen2.5-7b-instruct"
EPSILON = 0.1
CONVERSATIONS = 12_000
DAYS = 14
START = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)


def _value(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, list):
        return {"arrayValue": {"values": [_value(x) for x in v]}}
    return {"stringValue": str(v)}


def _attrs(d: dict) -> list[dict]:
    return [{"key": k, "value": _value(v)} for k, v in d.items()]


def _nanos(t: datetime) -> str:
    return str(round(t.timestamp() * 1e9))


def _span(trace_id, span_id, parent, name, start, end, attributes, kind=1) -> dict:
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": parent or "",
        "name": name,
        "kind": kind,
        "startTimeUnixNano": _nanos(start),
        "endTimeUnixNano": _nanos(end),
        "attributes": _attrs(attributes),
    }


RESOURCE = _attrs({"service.name": "support-agent", "deployment.environment": "production"})
SCOPE = {"name": "support-agent", "version": "3.8.1"}


def _content(ctx: dict, conversation: str, tier: str, user: str, llm_choice: str) -> dict:
    """GenAI content-capture attributes for the first model call."""
    system = SYSTEM_PROMPT.format(ticket=conversation, tier=tier)
    output = (
        [{"type": "text", "content": "Here's what you can do: …"}]
        if llm_choice == "__none__"
        else [{"type": "tool_call", "id": "call_0", "name": llm_choice, "arguments": {}}]
    )
    return {
        "gen_ai.system_instructions": json.dumps([{"type": "text", "content": system}]),
        "gen_ai.input.messages": json.dumps(
            [{"role": "user", "parts": [{"type": "text", "content": user}]}]
        ),
        "gen_ai.output.messages": json.dumps([{"role": "assistant", "parts": output}]),
        "gen_ai.tool.definitions": json.dumps(TOOLS),
    }


def simulate(
    out_dir: Path, *, explore: bool, capture_content: bool, seed: int = 7
) -> None:
    rng = random.Random(seed)
    traces = gzip.open(out_dir / "traces.otlp.json.gz", "wt", encoding="utf-8")  # noqa: SIM115
    outcomes = (out_dir / "helpdesk.csv").open("w", newline="", encoding="utf-8")  # noqa: SIM115
    writer = csv.writer(outcomes)
    writer.writerow(["join_key", "t", "value"])
    gap = DAYS * 86400 / CONVERSATIONS

    for i in range(CONVERSATIONS):
        conversation = f"conv-{48213 + i}"
        t0 = START + timedelta(seconds=i * gap + rng.uniform(0, gap))
        intent = rng.choices(list(INTENTS), weights=list(INTENTS.values()))[0]
        ctx = {
            "intent": intent,
            "has_order_number": rng.random() < P_ORDER_NUMBER[intent],
            "customer_tier": "pro" if rng.random() < P_PRO else "standard",
        }
        user = customer_message(rng, ctx, conversation)

        # The model picks a first move.
        probs = model_policy(ctx)
        llm_choice = rng.choices(ACTIONS, weights=[probs[a] for a in ACTIONS])[0]
        chat = {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": MODEL,
            "gen_ai.response.model": MODEL,
            "gen_ai.request.temperature": 0.7,
            "gen_ai.usage.input_tokens": rng.randint(900, 1450),
            "gen_ai.usage.output_tokens": rng.randint(14, 60),
            "gen_ai.response.finish_reasons": [
                "stop" if llm_choice == "__none__" else "tool_calls"
            ],
        }
        if capture_content:
            chat |= _content(ctx, conversation, ctx["customer_tier"], user, llm_choice)

        chosen = llm_choice
        if explore:
            chosen = ao.explore(
                "tool_choice",
                llm_choice=llm_choice,
                safe_candidates=SAFE,
                candidates=ACTIONS,
                epsilon=EPSILON,
                join_key=conversation,
                decision_id=f"{conversation}:1",
                t=t0.timestamp(),
                rng=rng,
                log=lambda record, attrs=chat: attrs.update(ao.span_attributes(record)),
            )

        trace_id = f"{rng.getrandbits(128):032x}"
        ids = [f"{rng.getrandbits(64):016x}" for _ in range(4)]
        ms = timedelta(milliseconds=1)
        spans = [
            _span(
                trace_id, ids[0], None, "invoke_agent support-agent", t0, t0 + 2600 * ms,
                {
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": "support-agent",
                    "gen_ai.conversation.id": conversation,
                    "app.intent": ctx["intent"],
                    "app.has_order_number": ctx["has_order_number"],
                    "app.customer_tier": ctx["customer_tier"],
                },
            ),
            _span(trace_id, ids[1], ids[0], f"chat {MODEL}", t0 + 40 * ms, t0 + 980 * ms, chat, 3),
        ]
        if chosen != "__none__":
            spans.append(
                _span(
                    trace_id, ids[2], ids[0], f"execute_tool {chosen}", t0 + 1000 * ms,
                    t0 + 1450 * ms,
                    {
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": chosen,
                        "gen_ai.tool.call.id": f"call_{rng.getrandbits(48):012x}",
                    },
                )
            )
        spans.append(
            _span(
                trace_id, ids[3], ids[0], f"chat {MODEL}", t0 + 1500 * ms, t0 + 2550 * ms,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": MODEL,
                    "gen_ai.response.finish_reasons": ["stop"],
                },
                3,
            )
        )
        request = {
            "resourceSpans": [
                {
                    "resource": {"attributes": RESOURCE},
                    "scopeSpans": [{"scope": SCOPE, "spans": spans}],
                }
            ]
        }
        traces.write(json.dumps(request, separators=(",", ":")) + "\n")

        # The helpdesk records the ticket's fate: resolved within ~2 days, or closed unresolved.
        resolved = rng.random() < p_resolved(ctx, chosen)
        closed = t0 + (timedelta(hours=rng.uniform(0.3, 40)) if resolved else timedelta(hours=48))
        writer.writerow([conversation, closed.strftime("%Y-%m-%dT%H:%M:%SZ"), int(resolved)])

    traces.close()
    outcomes.close()
