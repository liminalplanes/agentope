"""Action maps: turn what the agent did into an action id (spec §4.3)."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .errors import DataError
from .targets import _load_callable

NONE_ACTION = "__none__"


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] | None = None
    """None when the arguments were not recorded."""


class MissingArguments(Exception):
    """The action map needs tool arguments the trace does not contain."""


@dataclass(frozen=True, slots=True)
class ActionMap:
    name: str
    fn: Callable[[Sequence[ToolCall]], str]
    enumerable: bool
    """True when candidates are tool names (+ __none__), so tool definitions give them."""


def _tool(calls: Sequence[ToolCall]) -> str:
    return calls[0].name if calls else NONE_ACTION


def _toolset(calls: Sequence[ToolCall]) -> str:
    return "+".join(sorted({c.name for c in calls})) if calls else NONE_ACTION


def _tool_args(fields: tuple[str, ...]) -> Callable[[Sequence[ToolCall]], str]:
    def action(calls: Sequence[ToolCall]) -> str:
        if not calls:
            return NONE_ACTION
        call = calls[0]
        if call.arguments is None:
            raise MissingArguments(call.name)
        values = ",".join(
            f"{f}={json.dumps(call.arguments.get(f), sort_keys=True, ensure_ascii=False)}"
            for f in fields
        )
        return f"{call.name}({values})"

    return action


def resolve_action_map(spec: str) -> ActionMap:
    """'tool', 'toolset', 'tool+args:<f1>,<f2>', or a Python callable as
    'module:function' / 'file.py:function' taking a list of ``{"name", "arguments"}``."""
    if spec == "tool":
        return ActionMap("tool", _tool, enumerable=True)
    if spec == "toolset":
        return ActionMap("toolset", _toolset, enumerable=False)
    if spec.startswith("tool+args:"):
        fields = tuple(f.strip() for f in spec.removeprefix("tool+args:").split(",") if f.strip())
        if not fields:
            raise DataError("tool+args needs at least one field, e.g. tool+args:order_id")
        return ActionMap(spec, _tool_args(fields), enumerable=False)
    if ":" in spec:
        user_fn = _load_callable(spec)

        def custom(calls: Sequence[ToolCall]) -> str:
            result = user_fn([{"name": c.name, "arguments": c.arguments} for c in calls])  # type: ignore[call-arg, arg-type]
            if not isinstance(result, str) or not result:
                raise DataError(f"action map {spec} must return a non-empty string")
            return result

        return ActionMap(spec, custom, enumerable=False)
    raise DataError(
        f"unknown action map {spec!r}; use tool, toolset, tool+args:<fields> or module:function"
    )
