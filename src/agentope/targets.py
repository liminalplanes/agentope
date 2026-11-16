"""Target policies: Python callables and target.jsonl files."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Callable, Mapping
from os import PathLike
from pathlib import Path
from typing import Any

from .decisions import Decision, validate_probs
from .errors import DataError
from .io import is_path, read_jsonl, sha256_file

type TargetCallable = Callable[[dict[str, Any], list[str]], Mapping[str, float]]


class Target:
    """A target policy B: for each decision, a distribution over its candidates.

    Probabilities must sum to 1 over the decision's candidates. Candidates the
    policy leaves out get probability 0; actions outside the candidates are an error.
    """

    def __init__(
        self,
        fn: Callable[[Decision], Mapping[str, float]],
        description: str,
        files: dict[str, str] | None = None,
    ):
        self._fn = fn
        self.description = description
        self.files = files or {}

    def probs(self, decision: Decision) -> dict[str, float]:
        raw = self._fn(decision)
        return validate_probs(
            raw, decision.candidates, f"target ({decision.decision_id})", "target probabilities"
        )


def callable_target(fn: TargetCallable, description: str | None = None) -> Target:
    """Wrap ``fn(context, candidates) -> {action: probability}``."""
    if description is None:
        name = getattr(fn, "__qualname__", None) or type(fn).__name__
        module = getattr(fn, "__module__", None)
        description = f"{module}.{name}" if module and module != "__main__" else name
    return Target(lambda d: fn(dict(d.context), list(d.candidates)), description)


def load_target_jsonl(path: str | PathLike[str]) -> Target:
    rows: dict[str, Any] = {}
    for lineno, obj in read_jsonl(path):
        where = f"{path}:{lineno}"
        decision_id = obj.get("decision_id")
        if decision_id is None or isinstance(decision_id, bool):
            raise DataError(f"{where}: missing decision_id")
        decision_id = str(decision_id)
        if decision_id in rows:
            raise DataError(f"{where}: duplicate decision_id {decision_id!r}")
        if "probs" not in obj:
            raise DataError(f"{where}: missing probs")
        rows[decision_id] = obj["probs"]

    def lookup(d: Decision) -> Mapping[str, float]:
        try:
            return rows[d.decision_id]
        except KeyError:
            raise DataError(
                f"{path}: no target probabilities for decision {d.decision_id!r}"
            ) from None

    return Target(lookup, str(path), {str(path): sha256_file(path)})


def _load_callable(spec: str) -> TargetCallable:
    location, _, attr = spec.rpartition(":")
    if not location or not attr:
        raise DataError(f"invalid target {spec!r}; use module:function or path/to/file.py:function")
    if location.endswith(".py"):
        path = Path(location)
        if not path.is_file():
            raise DataError(f"target file {location!r} not found")
        module_spec = importlib.util.spec_from_file_location(f"_agentope_target_{path.stem}", path)
        if module_spec is None or module_spec.loader is None:
            raise DataError(f"cannot import {location!r}")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        if "" not in sys.path:
            sys.path.insert(0, "")
        try:
            module = importlib.import_module(location)
        except ImportError as e:
            raise DataError(f"cannot import target module {location!r}: {e}") from None
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise DataError(f"{location!r} has no callable {attr!r}")
    return fn


def resolve_target(target: object) -> Target:
    """Accept a Target, a callable, a target.jsonl path, or a 'module:function' /
    'file.py:function' string."""
    if isinstance(target, Target):
        return target
    if is_path(target):
        text = str(target)
        if Path(text).is_file():
            return load_target_jsonl(text)
        if ":" in text:
            fn = _load_callable(text)
            t = callable_target(fn, text)
            location = text.rpartition(":")[0]
            if location.endswith(".py"):
                t.files = {location: sha256_file(location)}
            return t
        raise DataError(f"target {text!r} is neither a file nor module:function")
    if callable(target):
        return callable_target(target)  # type: ignore[arg-type]
    raise DataError("target must be a callable, a target.jsonl path, or module:function")
