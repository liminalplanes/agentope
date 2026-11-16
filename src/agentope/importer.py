"""Turn traces into decision records (spec §11).

Each model (chat) span is a candidate decision. By default only the first model
call of each agent run is used (``decisions="first"``): one decision per turn,
taken before any tool result is known. What was chosen is read, in order of
preference, from:

1. an ``agentope.chosen`` span attribute (written via :func:`agentope.span_attributes`);
2. ``execute_tool`` / OpenInference ``TOOL`` spans that follow the model span,
   whenever the export contains tool spans at all (they show what actually ran);
3. tool calls in the response content (``gen_ai.output.messages`` or
   OpenInference ``llm.output_messages.*``), when content capture is on;
4. the finish reason, which can only tell "no tool call" (→ ``__none__``).

Candidates come from ``agentope.candidates``, then from tool definitions on the
request, and otherwise are inferred from every action seen (flagged in the report).
When input content was captured, the model input is written as a
chat-completions request body, for Level 2 replay.
"""

import json
import math
import os
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .action_maps import NONE_ACTION, MissingArguments, ToolCall, resolve_action_map
from .decisions import Decision
from .errors import DataError
from .io import PathArg, canonical_sha256, sha256_file
from .traces import Span, TraceSet, read_otlp

DEFAULT_JOIN_KEYS = ("gen_ai.conversation.id", "session.id")


# ── small helpers ────────────────────────────────────────────────────────────


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _args(value: Any) -> dict[str, Any] | None:
    parsed = _json(value)
    return parsed if isinstance(parsed, dict) else None


def _nested(attrs: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    """Unflatten OpenInference-style keys ('llm.tools.0.tool.json_schema') under prefix."""
    root: dict[str, Any] = {}
    for key, value in attrs.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].split(".")
        node = root
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                break
            node = child
        else:
            node[parts[-1]] = value
    return root


def _indexed(node: Any) -> list[Any]:
    if not isinstance(node, dict):
        return []
    return [node[k] for k in sorted((k for k in node if k.isdigit()), key=int)]


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", text)


def parse_context_spec(spec: object) -> list[tuple[str, str]]:
    """'intent=app.intent,tier=app.customer_tier' (or a mapping / list) → [(name, attribute)]."""
    if spec is None:
        return []
    if isinstance(spec, Mapping):
        return [(str(k), str(v)) for k, v in spec.items()]
    items = spec.split(",") if isinstance(spec, str) else list(spec)  # type: ignore[call-overload]
    out = []
    for item in items:
        item = str(item).strip()
        if not item:
            continue
        name, sep, attr = item.partition("=")
        name, attr = name.strip(), attr.strip()
        if sep and (not name or not attr):
            raise DataError(f"invalid --context entry {item!r}; use name=attribute")
        out.append((name, attr) if sep else (name, name))
    return out


# ── reading tool calls, tools and inputs from spans ──────────────────────────


def _tool_name(span: Span) -> str:
    a = span.attributes
    name = a.get("gen_ai.tool.name") or a.get("tool.name")
    if isinstance(name, str) and name:
        return name
    return span.name.removeprefix("execute_tool").strip() or span.name


def _span_tool_calls(span: Span, traces: TraceSet) -> list[ToolCall]:
    siblings = span.parent.children if span.parent else traces.roots(span.trace_id)
    stop = min(
        (s.start for s in siblings if s is not span and s.is_llm and s.start > span.start),
        default=math.inf,
    )
    pool = [c for c in span.children if c.is_tool]
    pool += [s for s in siblings if s is not span and s.is_tool and span.start <= s.start < stop]
    pool.sort(key=lambda s: s.start)
    return [
        ToolCall(
            _tool_name(s),
            _args(
                s.attributes.get("gen_ai.tool.call.arguments")
                or s.attributes.get("tool.parameters")
            ),
        )
        for s in pool
    ]


def _content_tool_calls(span: Span) -> list[ToolCall] | None:
    """Tool calls in the response content, or None when no output content was captured."""
    a = span.attributes
    if "gen_ai.output.messages" in a:
        messages = _json(a["gen_ai.output.messages"])
        calls = []
        for message in messages if isinstance(messages, list) else []:
            for part in message.get("parts") or [] if isinstance(message, dict) else []:
                if isinstance(part, dict) and part.get("type") == "tool_call" and part.get("name"):
                    calls.append(ToolCall(str(part["name"]), _args(part.get("arguments"))))
        return calls
    output = _nested(a, "llm.output_messages.")
    if output:
        calls = []
        for entry in _indexed(output):
            message = entry.get("message", {}) if isinstance(entry, dict) else {}
            for tc in _indexed(message.get("tool_calls")):
                fn = (
                    (tc.get("tool_call") or {}).get("function") or {}
                    if isinstance(tc, dict)
                    else {}
                )
                if fn.get("name"):
                    calls.append(ToolCall(str(fn["name"]), _args(fn.get("arguments"))))
        return calls
    return None


def _finish_reasons(span: Span) -> list[str] | None:
    value = span.attributes.get("gen_ai.response.finish_reasons")
    if isinstance(value, str):
        value = [value]
    return [str(v) for v in value] if isinstance(value, list) else None


def _merge_arguments(from_spans: list[ToolCall], from_content: list[ToolCall]) -> list[ToolCall]:
    remaining = list(from_content)
    merged = []
    for call in from_spans:
        if call.arguments is None:
            match = next((c for c in remaining if c.name == call.name), None)
            if match is not None:
                remaining.remove(match)
                call = ToolCall(call.name, match.arguments)
        merged.append(call)
    return merged


def _openai_tool(definition: Mapping[str, Any]) -> dict[str, Any]:
    if definition.get("type") == "function" and isinstance(definition.get("function"), dict):
        return dict(definition)
    fn = {k: definition[k] for k in ("name", "description", "parameters") if k in definition}
    return {"type": "function", "function": fn}


def _tool_definitions(span: Span) -> list[dict[str, Any]] | None:
    raw = span.lookup("gen_ai.tool.definitions")
    if raw is not None:
        defs = _json(raw)
        if isinstance(defs, list):
            return [_openai_tool(d) for d in defs if isinstance(d, dict)]
    tools = _nested(span.attributes, "llm.tools.")
    if tools:
        out = []
        for entry in _indexed(tools):
            schema = (
                _json((entry.get("tool") or {}).get("json_schema"))
                if isinstance(entry, dict)
                else None
            )
            if isinstance(schema, dict):
                out.append(_openai_tool(schema))
        return out
    return None


def _text(parts: Any) -> str | None:
    if isinstance(parts, str):
        return parts
    if isinstance(parts, dict):
        parts = [parts]
    if not isinstance(parts, list):
        return None
    texts = [p.get("content") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
    texts = [t for t in texts if isinstance(t, str)]
    return "\n".join(texts) if texts else None


def _arguments_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value or {}, ensure_ascii=False)


def _genai_messages(span: Span) -> list[dict[str, Any]] | None:
    a = span.attributes
    messages = _json(a.get("gen_ai.input.messages"))
    if not isinstance(messages, list):
        return None
    out: list[dict[str, Any]] = []
    system = _text(_json(a.get("gen_ai.system_instructions")))
    if system:
        out.append({"role": "system", "content": system})
    for message in messages:
        if not isinstance(message, dict):
            continue
        parts = [p for p in message.get("parts") or [] if isinstance(p, dict)]
        responses = [p for p in parts if p.get("type") == "tool_call_response"]
        if responses:
            for p in responses:
                response = p.get("response")
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": p.get("id"),
                        "content": response if isinstance(response, str) else json.dumps(response),
                    }
                )
            continue
        calls = [p for p in parts if p.get("type") == "tool_call"]
        entry: dict[str, Any] = {"role": message.get("role"), "content": _text(parts)}
        if calls:
            entry["tool_calls"] = [
                {
                    "id": p.get("id"),
                    "type": "function",
                    "function": {
                        "name": p.get("name"),
                        "arguments": _arguments_text(p.get("arguments")),
                    },
                }
                for p in calls
            ]
        elif entry["content"] is None:
            entry["content"] = ""
        out.append(entry)
    return out


def _openinference_messages(span: Span) -> list[dict[str, Any]] | None:
    nested = _nested(span.attributes, "llm.input_messages.")
    if not nested:
        return None
    out = []
    for item in _indexed(nested):
        message = item.get("message", {}) if isinstance(item, dict) else {}
        content = message.get("content")
        if content is None and "contents" in message:
            texts = [
                (c.get("message_content") or {}).get("text") for c in _indexed(message["contents"])
            ]
            content = "\n".join(t for t in texts if isinstance(t, str)) or None
        entry: dict[str, Any] = {"role": message.get("role"), "content": content}
        calls = []
        for tc in _indexed(message.get("tool_calls")):
            call = (tc.get("tool_call") or {}) if isinstance(tc, dict) else {}
            fn = call.get("function") or {}
            calls.append(
                {
                    "id": call.get("id"),
                    "type": "function",
                    "function": {
                        "name": fn.get("name"),
                        "arguments": _arguments_text(fn.get("arguments")),
                    },
                }
            )
        if calls:
            entry["tool_calls"] = calls
        if message.get("tool_call_id"):
            entry["tool_call_id"] = message["tool_call_id"]
        if entry["content"] is None and not calls:
            entry["content"] = ""
        out.append(entry)
    return out


def _logging_config(span: Span) -> dict[str, Any]:
    a = span.attributes
    params = _json(a.get("llm.invocation_parameters"))
    params = params if isinstance(params, dict) else {}
    config = {
        "model": a.get("gen_ai.request.model") or a.get("llm.model_name") or params.get("model"),
        "response_model": a.get("gen_ai.response.model"),
        "temperature": a.get("gen_ai.request.temperature", params.get("temperature")),
        "top_p": a.get("gen_ai.request.top_p", params.get("top_p")),
        "max_tokens": a.get("gen_ai.request.max_tokens", params.get("max_tokens")),
    }
    return {k: v for k, v in config.items() if v is not None}


def _stored_input(span: Span, config: Mapping[str, Any]) -> dict[str, Any] | None:
    """The model input as an OpenAI-compatible chat-completions request body."""
    messages = _genai_messages(span)
    if messages is None:
        messages = _openinference_messages(span)
    if not messages:
        return None
    body: dict[str, Any] = {"model": config.get("model"), "messages": messages}
    tools = _tool_definitions(span)
    if tools:
        body["tools"] = tools
    for key in ("temperature", "top_p", "max_tokens"):
        if key in config:
            body[key] = config[key]
    return body


# ── import ───────────────────────────────────────────────────────────────────


@dataclass
class ImportSummary:
    source: str
    n_traces: int
    n_spans: int
    duplicate_spans: int = 0
    decision_points: Counter[str] = field(default_factory=Counter)
    chosen_from: Counter[str] = field(default_factory=Counter)
    n_none: int = 0
    candidates_from: Counter[str] = field(default_factory=Counter)
    explored: int = 0
    with_propensity: int = 0
    epsilons: set[float] = field(default_factory=set)
    context_keys: list[str] = field(default_factory=list)
    context_missing: Counter[str] = field(default_factory=Counter)
    stored_inputs: int = 0
    inputs_dir: str | None = None
    parallel: int = 0
    requested_not_run: int = 0
    not_in_definitions: int = 0
    join_key_fallback: int = 0
    skipped: Counter[str] = field(default_factory=Counter)

    @property
    def n_decisions(self) -> int:
        return sum(self.decision_points.values())

    def render(self, output: str | None = None) -> str:
        n = self.n_decisions
        lines = [f"{self.source} · {self.n_traces:,} traces · {self.n_spans:,} spans"]
        for point, count in sorted(self.decision_points.items()):
            lines.append(f"{point:<16} {count:,} decisions")
        if not n:
            lines.append("no decisions found")
        else:
            chosen = [f"{c:,} from {src}" for src, c in self.chosen_from.most_common()]
            if self.n_none:
                chosen.append(f"{self.n_none:,} {NONE_ACTION} (no tool call)")
            lines.append(f"  chosen         {' · '.join(chosen)}")
            cands = [
                f"{'inferred from the logs' if src == 'inferred' else 'from ' + src} on {c:,}/{n:,}"
                for src, c in self.candidates_from.most_common()
            ]
            lines.append(f"  candidates     {' · '.join(cands)}")
            if self.with_propensity:
                eps = f" (ε={next(iter(self.epsilons)):g})" if len(self.epsilons) == 1 else ""
                parts = []
                if self.explored:
                    parts.append(f"{self.explored:,} explored{eps}")
                if self.with_propensity > self.explored:
                    parts.append(f"{self.with_propensity - self.explored:,} logged")
                parts.append(f"{n - self.with_propensity:,} without")
                lines.append(f"  propensities   {' · '.join(parts)}")
            else:
                lines.append("  propensities   none logged")
            if self.context_keys:
                missing = [
                    f"{k} missing on {self.context_missing[k]:,}"
                    for k in self.context_keys
                    if self.context_missing[k]
                ]
                text = ", ".join(self.context_keys) + (
                    f" ({'; '.join(missing)})" if missing else ""
                )
            else:
                text = "none (pass --context name=attribute,…)"
            lines.append(f"  context        {text}")
            levels = "Levels 1 and 3 available" if self.with_propensity else "Level 3 only"
            if self.stored_inputs:
                where = f"written to {self.inputs_dir}" if self.inputs_dir else "found"
                lines.append(
                    f"  stored inputs  {self.stored_inputs:,}/{n:,} {where} → {levels}; "
                    "Level 2 after agentope sample"
                )
            else:
                lines.append(f"  stored inputs  none (content capture off) → {levels}")
        notes = []
        if self.parallel:
            notes.append(
                f"{self.parallel:,} decisions called 2+ tools in parallel → consider --map toolset"
            )
        if self.requested_not_run:
            notes.append(
                f"{self.requested_not_run:,} responses requested a tool but none ran → "
                f"recorded as {NONE_ACTION}"
            )
        if self.not_in_definitions:
            notes.append(
                f"{self.not_in_definitions:,} chosen actions were missing from the tool "
                "definitions and were added as candidates"
            )
        if self.join_key_fallback:
            notes.append(
                f"{self.join_key_fallback:,} decisions had no join key attribute → trace id used"
            )
        if self.duplicate_spans:
            notes.append(f"{self.duplicate_spans:,} duplicate spans ignored")
        for reason, count in self.skipped.most_common():
            notes.append(f"skipped {count:,}: {reason}")
        lines.extend(f"  ! {note}" for note in notes)
        if output:
            lines.append(f"wrote {output}")
        return "\n".join(lines)


class ImportedDecisions(list):
    """Decision records (dicts) from traces, with the import summary attached."""

    summary: ImportSummary
    action_map: str
    source_files: dict[str, str]


def _run_key(span: Span) -> tuple[str, str]:
    for node in span.ancestors():
        if node.is_agent:
            return (span.trace_id, node.span_id)
    return (span.trace_id, "")


def import_traces(
    path: PathArg,
    *,
    decision_point: str = "tool_choice",
    action_map: str = "tool",
    context: object = None,
    join_key: str | None = None,
    decisions: str = "first",
    inputs_dir: PathArg | None = None,
    inputs_base: PathArg | None = None,
) -> ImportedDecisions:
    """Read an OTLP JSON trace export and return decision records.

    context: which attributes form the context, as 'name=attribute,…', a mapping
        {name: attribute}, or a list. Looked up on the model span, then its
        ancestors, then the resource.
    join_key: attribute holding the outcome key; default gen_ai.conversation.id,
        then session.id, then the trace id.
    decisions: "first" (first model call per agent run) or "all" (every model
        call; adds an ``llm_call_index`` context feature).
    inputs_dir: where to write stored inputs (only when content was captured);
        ``input_ref`` is written relative to ``inputs_base`` when given.
    """
    if decisions not in ("first", "all"):
        raise DataError("decisions must be 'first' or 'all'")
    amap = resolve_action_map(action_map)
    ctx_spec = parse_context_spec(context)
    traces = read_otlp(path)
    summary = ImportSummary(
        source=Path(path).name,
        n_traces=len(traces.traces),
        n_spans=len(traces.spans),
        duplicate_spans=traces.duplicates,
        context_keys=[name for name, _ in ctx_spec],
        inputs_dir=str(inputs_dir) if inputs_dir is not None else None,
    )
    tool_spans_present = any(s.is_tool for s in traces.spans)

    runs: dict[tuple[str, str], list[Span]] = defaultdict(list)
    for span in traces.spans:
        if span.is_llm:
            runs[_run_key(span)].append(span)
    selected: list[tuple[Span, int]] = []
    for members in runs.values():
        members.sort(key=lambda s: s.start)
        chosen_members = members[:1] if decisions == "first" else members
        selected.extend((s, i) for i, s in enumerate(chosen_members))
    selected.sort(key=lambda item: (item[0].start, item[0].trace_id, item[0].span_id))

    written_dir = Path(inputs_dir) if inputs_dir is not None else None
    records: list[dict[str, Any]] = []
    for span, call_index in selected:
        a = span.attributes
        explicit = a.get("agentope.chosen")
        if isinstance(explicit, str) and explicit:
            chosen, source = explicit, "agentope.chosen"
        else:
            content_calls = _content_tool_calls(span)
            if tool_spans_present:
                calls = _span_tool_calls(span, traces)
                if content_calls:
                    calls = _merge_arguments(calls, content_calls)
                elif not calls and any("tool" in r for r in _finish_reasons(span) or []):
                    summary.requested_not_run += 1
                if not calls and content_calls:
                    summary.requested_not_run += 1
                source = "execute_tool spans"
            elif content_calls is not None:
                calls, source = content_calls, "response content"
            else:
                reasons = _finish_reasons(span)
                if reasons is None:
                    summary.skipped[
                        "cannot tell whether a tool was called (no tool spans, content or "
                        "finish reason)"
                    ] += 1
                    continue
                if any("tool" in r for r in reasons):
                    summary.skipped["a tool was called but its name was not recorded"] += 1
                    continue
                calls, source = [], "finish reason"
            if len(calls) > 1:
                summary.parallel += 1
            try:
                chosen = amap.fn(calls)
            except MissingArguments:
                summary.skipped["tool arguments not recorded (the action map needs them)"] += 1
                continue

        candidates_attr = a.get("agentope.candidates")
        if isinstance(candidates_attr, list) and all(isinstance(c, str) for c in candidates_attr):
            candidates, candidates_source = (
                list(dict.fromkeys(candidates_attr)),
                "agentope.candidates",
            )
        elif amap.enumerable and (defs := _tool_definitions(span)):
            names = [d.get("function", {}).get("name") for d in defs]
            candidates = list(dict.fromkeys(n for n in names if isinstance(n, str) and n))
            candidates.append(NONE_ACTION)
            candidates_source = "tool definitions"
        else:
            candidates, candidates_source = None, "inferred"
        if candidates is not None and chosen not in candidates:
            candidates.append(chosen)
            summary.not_in_definitions += 1

        ctx: dict[str, Any] = {}
        for name, attr in ctx_spec:
            value = span.lookup(attr)
            if value is None:
                summary.context_missing[name] += 1
            ctx[name] = _scalar(value)
        if decisions == "all":
            ctx["llm_call_index"] = call_index

        key = None
        for attr in (join_key,) if join_key else DEFAULT_JOIN_KEYS:
            value = span.lookup(attr)
            if value not in (None, ""):
                key = str(value)
                break
        if key is None:
            if join_key:
                summary.join_key_fallback += 1
            key = span.trace_id

        decision_id = a.get("agentope.decision_id")
        if not isinstance(decision_id, str) or not decision_id:
            decision_id = f"{span.trace_id}:{span.span_id}"
        point = a.get("agentope.decision_point")
        point = point if isinstance(point, str) and point else decision_point

        record: dict[str, Any] = {
            "decision_id": decision_id,
            "t": span.start,
            "decision_point": point,
            "context": ctx,
            "candidates": candidates,
            "chosen": chosen,
            "join_key": key,
            "action_map": amap.name,
            "candidates_source": candidates_source,
        }
        if a.get("agentope.explored") is True:
            record["explored"] = True
        propensity = a.get("agentope.propensity")
        if isinstance(propensity, (int, float)) and not isinstance(propensity, bool):
            record["propensity"] = float(propensity)
            record["propensity_source"] = "logged"
        if isinstance(safe := a.get("agentope.safe_candidates"), list):
            record["safe_candidates"] = safe
        if isinstance(probs := _json(a.get("agentope.logging_probs")), dict):
            record["logging_probs"] = probs
        if isinstance(eps := a.get("agentope.epsilon"), (int, float)) and not isinstance(eps, bool):
            record["epsilon"] = float(eps)
            if record.get("explored") or "propensity" in record:
                summary.epsilons.add(float(eps))

        config = _logging_config(span)
        if config:
            record["logging_config"] = config
        body = _stored_input(span, config)
        if body is not None:
            summary.stored_inputs += 1
            record["input_sha256"] = canonical_sha256(body)
            if written_dir is not None:
                written_dir.mkdir(parents=True, exist_ok=True)
                target = written_dir / f"{_safe_name(decision_id)}.json"
                target.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
                ref = (
                    os.path.relpath(target, inputs_base) if inputs_base is not None else str(target)
                )
                record["input_ref"] = Path(ref).as_posix()

        records.append(record)
        summary.decision_points[point] += 1
        if chosen == NONE_ACTION and source != "agentope.chosen":
            summary.n_none += 1
        else:
            summary.chosen_from[source] += 1
        summary.candidates_from[candidates_source] += 1
        if record.get("explored"):
            summary.explored += 1
        if "propensity" in record or record.get("explored"):
            summary.with_propensity += 1

    # Candidates nobody declared: everything seen at the same decision point.
    seen: dict[str, set[str]] = defaultdict(set)
    for r in records:
        seen[r["decision_point"]].add(r["chosen"])
    for r in records:
        if r["candidates"] is None:
            actions = seen[r["decision_point"]] | ({NONE_ACTION} if amap.enumerable else set())
            r["candidates"] = sorted(actions, key=lambda x: (x == NONE_ACTION, x))

    for r in records:  # fail early, with the span to look at
        try:
            Decision.from_dict(r, f"trace {r['decision_id']}")
        except DataError as e:
            raise DataError(f"{path}: {e}") from None

    out = ImportedDecisions(records)
    out.summary = summary
    out.action_map = amap.name
    out.source_files = {str(path): sha256_file(path)}
    return out


def write_decisions(records: Sequence[Mapping[str, Any]], path: PathArg) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")
