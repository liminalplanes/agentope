"""Reading OTLP JSON trace exports (spec §11).

Accepts what the OpenTelemetry Collector's file exporter writes (one
``ExportTraceServiceRequest`` JSON object per line) as well as a single JSON
document or a list of them, optionally gzipped. Span kinds are recognized under
both the OpenTelemetry GenAI conventions (``gen_ai.*``) and OpenInference.
"""

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import DataError
from .io import PathArg, open_text

LLM_OPERATIONS = {"chat", "text_completion", "generate_content"}


@dataclass(slots=True, eq=False)
class Span:
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    start: float
    """Seconds since the epoch."""
    attributes: dict[str, Any]
    resource: dict[str, Any]
    parent: Span | None = None
    children: list[Span] = field(default_factory=list)

    @property
    def operation(self) -> str | None:
        return self.attributes.get("gen_ai.operation.name")

    @property
    def openinference_kind(self) -> str | None:
        kind = self.attributes.get("openinference.span.kind")
        return kind.upper() if isinstance(kind, str) else None

    @property
    def is_llm(self) -> bool:
        return self.operation in LLM_OPERATIONS or self.openinference_kind == "LLM"

    @property
    def is_tool(self) -> bool:
        return self.operation == "execute_tool" or self.openinference_kind == "TOOL"

    @property
    def is_agent(self) -> bool:
        return self.operation == "invoke_agent" or self.openinference_kind == "AGENT"

    def ancestors(self) -> Iterable[Span]:
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def lookup(self, key: str) -> Any:
        """An attribute from this span, its nearest ancestor that has it, or the resource."""
        if key in self.attributes:
            return self.attributes[key]
        for node in self.ancestors():
            if key in node.attributes:
                return node.attributes[key]
        return self.resource.get(key)


@dataclass(slots=True)
class TraceSet:
    spans: list[Span]
    traces: dict[str, list[Span]]
    duplicates: int
    """Spans dropped because the same (trace id, span id) appeared before."""

    def roots(self, trace_id: str) -> list[Span]:
        return [s for s in self.traces[trace_id] if s.parent is None]


def attribute_value(value: Mapping[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "arrayValue" in value:
        return [attribute_value(v) for v in (value["arrayValue"] or {}).get("values") or []]
    if "kvlistValue" in value:
        return attributes((value["kvlistValue"] or {}).get("values"))
    if "bytesValue" in value:
        return value["bytesValue"]
    return None


def attributes(items: object) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:  # type: ignore[union-attr]
        if isinstance(item, Mapping) and isinstance(item.get("key"), str):
            out[item["key"]] = attribute_value(item.get("value") or {})
    return out


def _seconds(nanos: object, where: str) -> float:
    try:
        return int(nanos) / 1e9  # type: ignore[call-overload]
    except TypeError, ValueError:
        raise DataError(f"{where}: span has no valid startTimeUnixNano") from None


def _documents(path: PathArg) -> list[Any]:
    with open_text(path) as f:
        text = f.read()
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        docs = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    docs.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise DataError(f"{path}:{lineno}: invalid JSON ({e.msg})") from None
        return docs
    return whole if isinstance(whole, list) else [whole]


def read_otlp(path: PathArg) -> TraceSet:
    spans: list[Span] = []
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for doc in _documents(path):
        if not isinstance(doc, Mapping) or "resourceSpans" not in doc:
            raise DataError(f"{path}: not an OTLP JSON trace export (no resourceSpans)")
        for rs in doc["resourceSpans"] or []:
            resource = attributes((rs.get("resource") or {}).get("attributes"))
            scopes = rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []
            for scope in scopes:
                for raw in scope.get("spans") or []:
                    trace_id, span_id = str(raw.get("traceId", "")), str(raw.get("spanId", ""))
                    if not trace_id or not span_id:
                        raise DataError(f"{path}: span without traceId or spanId")
                    if (trace_id, span_id) in seen:
                        duplicates += 1
                        continue
                    seen.add((trace_id, span_id))
                    spans.append(
                        Span(
                            trace_id=trace_id,
                            span_id=span_id,
                            parent_id=raw.get("parentSpanId") or None,
                            name=str(raw.get("name", "")),
                            start=_seconds(raw.get("startTimeUnixNano"), f"{path} ({span_id})"),
                            attributes=attributes(raw.get("attributes")),
                            resource=resource,
                        )
                    )

    index = {(s.trace_id, s.span_id): s for s in spans}
    traces: dict[str, list[Span]] = defaultdict(list)
    for s in spans:
        traces[s.trace_id].append(s)
        if s.parent_id and (parent := index.get((s.trace_id, s.parent_id))):
            s.parent = parent
            parent.children.append(s)
    for s in spans:
        s.children.sort(key=lambda c: c.start)
    for members in traces.values():
        members.sort(key=lambda m: m.start)
    return TraceSet(spans=spans, traces=dict(traces), duplicates=duplicates)
