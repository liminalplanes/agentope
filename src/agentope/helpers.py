"""Logging helpers that produce Level 1 data (spec §7.3)."""

from __future__ import annotations

import json
import random
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from os import PathLike
from pathlib import Path
from typing import Any, Protocol

from .decisions import Scalar, validate_context, validate_probs
from .errors import DataError


class _Rng(Protocol):
    def random(self) -> float: ...


type LogTarget = str | PathLike[str] | Callable[[dict[str, Any]], object] | Any

_LOCK = threading.Lock()
_DEFAULT_RNG = random.Random()


def _write(log: LogTarget, record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, allow_nan=False)
    with _LOCK:
        if isinstance(log, (str, PathLike)):
            with Path(log).open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        elif hasattr(log, "write"):
            log.write(line + "\n")
            if hasattr(log, "flush"):
                log.flush()
        elif callable(log):
            log(record)
        else:
            raise DataError("log must be a path, a writable file object, or a callable")


def _draw(actions: Sequence[str], probs: Sequence[float], rng: _Rng) -> str:
    u = rng.random()
    cumulative = 0.0
    for action, p in zip(actions, probs, strict=True):
        cumulative += p
        if u < cumulative:
            return action
    return next(a for a, p in zip(reversed(actions), reversed(probs), strict=True) if p > 0)


def _record(
    decision_point: str,
    candidates: Sequence[str],
    chosen: str,
    context: Mapping[str, Scalar] | None,
    join_key: str,
    decision_id: str | None,
    t: float | None,
) -> dict[str, Any]:
    return {
        "decision_id": decision_id or uuid.uuid4().hex,
        "t": time.time() if t is None else t,
        "decision_point": decision_point,
        "context": validate_context(context or {}, decision_point),
        "candidates": list(candidates),
        "chosen": chosen,
        "join_key": str(join_key),
    }


def _check_actions(actions: Sequence[str], name: str) -> tuple[str, ...]:
    out = tuple(actions)
    if not out or not all(isinstance(a, str) and a for a in out) or len(set(out)) != len(out):
        raise DataError(f"{name} must be a non-empty list of distinct action ids")
    return out


def randomize(
    decision_point: str,
    candidates: Sequence[str],
    probs: Sequence[float] | Mapping[str, float],
    *,
    join_key: str,
    log: LogTarget,
    context: Mapping[str, Scalar] | None = None,
    decision_id: str | None = None,
    t: float | None = None,
    rng: _Rng | None = None,
) -> str:
    """Choose at random with the given probabilities and log the probability used.

    Writes one decisions.jsonl record with ``propensity_source = "logged"`` and the
    full ``logging_probs``, so later support checks are exact. Returns the action.
    """
    cands = _check_actions(candidates, "candidates")
    if isinstance(probs, Mapping):
        dist = validate_probs(probs, cands, decision_point)
    else:
        if len(probs) != len(cands):
            raise DataError("probs must have one entry per candidate")
        dist = validate_probs(dict(zip(cands, probs, strict=True)), cands, decision_point)
    chosen = _draw(cands, [dist[a] for a in cands], rng or _DEFAULT_RNG)
    record = _record(decision_point, cands, chosen, context, join_key, decision_id, t)
    record |= {
        "propensity": dist[chosen],
        "propensity_source": "logged",
        "explored": False,
        "logging_probs": dist,
    }
    _write(log, record)
    return chosen


def explore(
    decision_point: str,
    llm_choice: str,
    safe_candidates: Sequence[str],
    epsilon: float,
    *,
    join_key: str,
    log: LogTarget,
    candidates: Sequence[str] | None = None,
    context: Mapping[str, Scalar] | None = None,
    decision_id: str | None = None,
    t: float | None = None,
    rng: _Rng | None = None,
) -> str:
    """ε-explore an LLM-made decision within user-approved alternatives.

    With probability ``epsilon`` the action is drawn uniformly from
    ``safe_candidates`` (never from outside it) and the decision is logged as
    explored with propensity ``1/len(safe_candidates)``. Otherwise the LLM's
    choice is used and logged without a propensity. Only explored decisions are
    used at Level 1.

    ``candidates`` is every action available at this decision (defaults to the
    safe candidates plus the LLM's choice). Deciding which actions are safe to
    take at random is the caller's responsibility.
    """
    safe = _check_actions(safe_candidates, "safe_candidates")
    if isinstance(epsilon, bool) or not isinstance(epsilon, (int, float)) or not 0 <= epsilon <= 1:
        raise DataError("epsilon must be a number in [0, 1]")
    if candidates is None:
        cands = safe if llm_choice in safe else (*safe, llm_choice)
    else:
        cands = _check_actions(candidates, "candidates")
        if not set(safe) <= set(cands):
            raise DataError("safe_candidates must be a subset of candidates")
        if llm_choice not in cands:
            raise DataError(f"llm_choice {llm_choice!r} is not among candidates")

    generator = rng or _DEFAULT_RNG
    explored = generator.random() < epsilon
    if explored:
        chosen = safe[min(int(generator.random() * len(safe)), len(safe) - 1)]
    else:
        chosen = llm_choice
    record = _record(decision_point, cands, chosen, context, join_key, decision_id, t)
    record |= {
        "propensity": 1.0 / len(safe) if explored else None,
        "propensity_source": "logged" if explored else None,
        "explored": explored,
        "safe_candidates": list(safe),
        "llm_choice": llm_choice,
        "epsilon": epsilon,
    }
    _write(log, record)
    return chosen


def span_attributes(record: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten a record from :func:`explore` / :func:`randomize` into OpenTelemetry span
    attributes (``agentope.*``), which :func:`agentope.import_traces` reads back.

    Use it as the log target to keep exploration data in your traces::

        ao.explore(..., log=lambda r: span.set_attributes(ao.span_attributes(r)))
    """
    out: dict[str, Any] = {}
    for key in (
        "decision_id",
        "decision_point",
        "chosen",
        "explored",
        "propensity",
        "epsilon",
        "llm_choice",
    ):
        value = record.get(key)
        if value is not None:
            out[f"agentope.{key}"] = value
    for key in ("candidates", "safe_candidates"):
        if record.get(key):
            out[f"agentope.{key}"] = list(record[key])
    if record.get("logging_probs") is not None:
        out["agentope.logging_probs"] = json.dumps(record["logging_probs"], sort_keys=True)
    return out


__all__ = ["explore", "randomize", "span_attributes"]
