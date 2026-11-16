"""Build OTLP JSON trace exports for tests."""

from __future__ import annotations

import gzip
import itertools
import json
from pathlib import Path
from typing import Any


def value(x: Any) -> dict[str, Any]:
    if isinstance(x, bool):
        return {"boolValue": x}
    if isinstance(x, int):
        return {"intValue": str(x)}
    if isinstance(x, float):
        return {"doubleValue": x}
    if isinstance(x, str):
        return {"stringValue": x}
    if isinstance(x, list):
        return {"arrayValue": {"values": [value(v) for v in x]}}
    if isinstance(x, dict):
        return {"kvlistValue": {"values": [{"key": k, "value": value(v)} for k, v in x.items()]}}
    raise TypeError(x)


def attrs(d: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": k, "value": value(v)} for k, v in d.items() if v is not None]


class Builder:
    def __init__(self, resource: dict[str, Any] | None = None):
        self.spans: list[dict[str, Any]] = []
        self.resource = resource or {"service.name": "support-agent"}
        self._ids = itertools.count(1)

    def span(
        self,
        trace: str,
        name: str,
        start: float,
        attributes: dict[str, Any],
        parent: str | None = None,
    ) -> str:
        span_id = f"{next(self._ids):016x}"
        self.spans.append(
            {
                "traceId": trace,
                "spanId": span_id,
                "parentSpanId": parent or "",
                "name": name,
                "kind": 3,
                "startTimeUnixNano": str(round(start * 1e9)),
                "endTimeUnixNano": str(round((start + 0.5) * 1e9)),
                "attributes": attrs(attributes),
            }
        )
        return span_id

    def export(self) -> dict[str, Any]:
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": attrs(self.resource)},
                    "scopeSpans": [{"scope": {"name": "test"}, "spans": self.spans}],
                }
            ]
        }

    def write(self, path: Path, *, per_trace_lines: bool = True, gz: bool = False) -> Path:
        if per_trace_lines:  # like the Collector's file exporter: one request per line
            by_trace: dict[str, list[dict[str, Any]]] = {}
            for s in self.spans:
                by_trace.setdefault(s["traceId"], []).append(s)
            lines = []
            for spans in by_trace.values():
                doc = self.export()
                doc["resourceSpans"][0]["scopeSpans"][0]["spans"] = spans
                lines.append(json.dumps(doc))
            text = "\n".join(lines) + "\n"
        else:
            text = json.dumps(self.export(), indent=2)
        if gz:
            with gzip.open(path, "wt") as f:
                f.write(text)
        else:
            path.write_text(text)
        return path


def genai(op: str, **extra: Any) -> dict[str, Any]:
    return {"gen_ai.operation.name": op, **extra}


def traces_from_simulation(decisions: list[dict[str, Any]]) -> Builder:
    """One GenAI-style trace per simulated decision, content capture off. Explored and
    logged propensities travel as agentope.* span attributes."""
    b = Builder()
    for i, d in enumerate(decisions):
        trace = f"{i + 1:032x}"
        t = d["t"]
        agent = b.span(
            trace,
            "invoke_agent support-agent",
            t,
            genai(
                "invoke_agent",
                **{
                    "gen_ai.conversation.id": d["join_key"],
                    "app.intent": d["context"]["intent"],
                    "app.pro": d["context"]["pro"],
                },
            ),
        )
        chat_attrs = genai(
            "chat",
            **{
                "gen_ai.request.model": "qwen2.5-7b-instruct",
                "gen_ai.request.temperature": 0.7,
                "gen_ai.response.finish_reasons": [
                    "stop" if d["chosen"] == "__none__" else "tool_calls"
                ],
            },
        )
        if d.get("explored"):
            chat_attrs |= {
                "agentope.explored": True,
                "agentope.candidates": d["candidates"],
                "agentope.safe_candidates": d["safe_candidates"],
            }
        if d.get("logging_probs"):
            chat_attrs |= {
                "agentope.propensity": d["propensity"],
                "agentope.candidates": d["candidates"],
                "agentope.logging_probs": json.dumps(d["logging_probs"]),
            }
        b.span(trace, "chat qwen2.5-7b-instruct", t + 0.01, chat_attrs, parent=agent)
        if d["chosen"] != "__none__":
            b.span(
                trace,
                f"execute_tool {d['chosen']}",
                t + 0.02,
                genai("execute_tool", **{"gen_ai.tool.name": d["chosen"]}),
                parent=agent,
            )
            b.span(
                trace,
                "chat qwen2.5-7b-instruct",
                t + 0.03,
                genai("chat", **{"gen_ai.response.finish_reasons": ["stop"]}),
                parent=agent,
            )
    return b
