"""Decision records (spec §6.1)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .errors import DataError
from .io import is_path, parse_time, read_jsonl

type Scalar = str | int | float | bool | None

PROPENSITY_SOURCES = ("logged", "sampled", "estimated")
PROB_TOLERANCE = 1e-6
_REQUIRED = ("decision_id", "t", "decision_point", "context", "candidates", "chosen", "join_key")


def validate_context(ctx: object, where: str) -> dict[str, Scalar]:
    if not isinstance(ctx, Mapping):
        raise DataError(f"{where}: context must be an object")
    out: dict[str, Scalar] = {}
    for key, value in ctx.items():
        if not isinstance(key, str):
            raise DataError(f"{where}: context keys must be strings")
        if value is not None and not isinstance(value, (str, bool, int, float)):
            raise DataError(
                f"{where}: context[{key!r}] must be a string, number, boolean or null "
                "(context is a flat dict)"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise DataError(f"{where}: context[{key!r}] must be finite")
        out[key] = value
    return out


def validate_probs(
    raw: object, candidates: tuple[str, ...], where: str, what: str = "probabilities"
) -> dict[str, float]:
    """Check a probability mapping over candidates. Missing candidates get 0."""
    if not isinstance(raw, Mapping):
        raise DataError(f"{where}: {what} must be a mapping from action id to probability")
    out = dict.fromkeys(candidates, 0.0)
    for action, p in raw.items():
        if action not in out:
            raise DataError(f"{where}: {what} give probability to {action!r}, not a candidate")
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0:
            raise DataError(f"{where}: {what}[{action!r}] must be a number >= 0, got {p!r}")
        out[action] = float(p)
    total = math.fsum(out.values())
    if abs(total - 1.0) > PROB_TOLERANCE:
        raise DataError(f"{where}: {what} sum to {total:.6g}, not 1")
    return out


def _action_list(value: object, name: str, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DataError(f"{where}: {name} must be a non-empty list of action ids")
    if not all(isinstance(a, str) and a for a in value):
        raise DataError(f"{where}: {name} must contain non-empty strings")
    if len(set(value)) != len(value):
        raise DataError(f"{where}: {name} contains duplicates")
    return tuple(value)


def _key(value: object, name: str, where: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise DataError(f"{where}: {name} must be a string")
    return str(value)


@dataclass(frozen=True, slots=True, eq=False)
class Decision:
    """One logged decision.

    Besides the fields in spec §6.1, two optional fields are understood:

    - ``safe_candidates``: for explored decisions, the set the exploration
      drew from uniformly (written by :func:`agentope.explore`).
    - ``logging_probs``: the full logging distribution over candidates, when
      known (written by :func:`agentope.randomize`). It makes the support
      check exact.

    A ``propensity`` with no ``propensity_source`` is treated as logged.
    """

    decision_id: str
    t: float
    decision_point: str
    context: dict[str, Scalar]
    candidates: tuple[str, ...]
    chosen: str
    join_key: str
    propensity: float | None = None
    propensity_source: str | None = None
    explored: bool = False
    safe_candidates: tuple[str, ...] | None = None
    logging_probs: dict[str, float] | None = None
    n_samples: int | None = None
    input_ref: str | None = None
    logging_config: dict[str, Any] | None = None
    action_map: str | None = None
    """The action map that produced ``chosen`` (written by trace import)."""
    candidates_source: str | None = None
    input_sha256: str | None = None
    """Hash of the stored input as imported (checked again when sampling)."""
    """Where ``candidates`` came from; ``"inferred"`` means from actions seen in the logs."""

    @property
    def has_logged_propensity(self) -> bool:
        return self.propensity is not None and self.propensity_source == "logged"

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], where: str = "decision") -> Decision:
        for field in _REQUIRED:
            if d.get(field) is None:
                raise DataError(f"{where}: missing required field {field!r}")
        decision_id = _key(d["decision_id"], "decision_id", where)
        where = f"{where} ({decision_id})"

        decision_point = d["decision_point"]
        if not isinstance(decision_point, str) or not decision_point:
            raise DataError(f"{where}: decision_point must be a non-empty string")
        candidates = _action_list(d["candidates"], "candidates", where)
        chosen = d["chosen"]
        if chosen not in candidates:
            raise DataError(f"{where}: chosen {chosen!r} is not among candidates")

        propensity = d.get("propensity")
        if propensity is not None:
            if (
                isinstance(propensity, bool)
                or not isinstance(propensity, (int, float))
                or not 0 < propensity <= 1
            ):
                raise DataError(f"{where}: propensity must be a number in (0, 1]")
            propensity = float(propensity)

        source = d.get("propensity_source")
        if source not in (None, *PROPENSITY_SOURCES):
            raise DataError(
                f"{where}: propensity_source must be one of {', '.join(PROPENSITY_SOURCES)} or null"
            )

        explored = d.get("explored") or False
        if not isinstance(explored, bool):
            raise DataError(f"{where}: explored must be true or false")

        safe = d.get("safe_candidates")
        if safe is not None:
            safe = _action_list(safe, "safe_candidates", where)
            if not set(safe) <= set(candidates):
                raise DataError(f"{where}: safe_candidates must be a subset of candidates")

        logging_probs = d.get("logging_probs")
        if logging_probs is not None:
            logging_probs = validate_probs(logging_probs, candidates, where, "logging_probs")

        if explored:
            pool = safe or candidates
            if chosen not in pool:
                raise DataError(
                    f"{where}: explored decision chose {chosen!r}, not a safe candidate"
                )
            expected = 1.0 / len(pool)
            if propensity is None:
                propensity = expected
            elif abs(propensity - expected) > 1e-9:
                raise DataError(
                    f"{where}: explored decision has propensity {propensity:g}, but uniform "
                    f"exploration over {len(pool)} safe candidates gives {expected:g}"
                )
            if source not in (None, "logged"):
                raise DataError(f"{where}: explored decisions have logged propensities")
            source = "logged"
            logging_probs = {a: (expected if a in pool else 0.0) for a in candidates}

        if logging_probs is not None:
            p_chosen = logging_probs[chosen]
            if p_chosen == 0:
                raise DataError(f"{where}: logging_probs give the chosen action probability 0")
            if propensity is None:
                propensity = p_chosen
            elif abs(propensity - p_chosen) > PROB_TOLERANCE:
                raise DataError(
                    f"{where}: propensity {propensity:g} disagrees with "
                    f"logging_probs[{chosen!r}] = {p_chosen:g}"
                )

        if propensity is not None and source is None:
            source = "logged"

        n_samples = d.get("n_samples")
        if n_samples is not None and (
            isinstance(n_samples, bool) or not isinstance(n_samples, int) or n_samples < 1
        ):
            raise DataError(f"{where}: n_samples must be a positive integer")
        input_ref = d.get("input_ref")
        if input_ref is not None and not isinstance(input_ref, str):
            raise DataError(f"{where}: input_ref must be a string")
        logging_config = d.get("logging_config")
        if logging_config is not None and not isinstance(logging_config, Mapping):
            raise DataError(f"{where}: logging_config must be an object")
        action_map = d.get("action_map")
        if action_map is not None and not isinstance(action_map, str):
            raise DataError(f"{where}: action_map must be a string")
        input_sha256 = d.get("input_sha256")
        if input_sha256 is not None and not isinstance(input_sha256, str):
            raise DataError(f"{where}: input_sha256 must be a string")
        candidates_source = d.get("candidates_source")
        if candidates_source is not None and not isinstance(candidates_source, str):
            raise DataError(f"{where}: candidates_source must be a string")

        return cls(
            decision_id=decision_id,
            t=parse_time(d["t"], where),
            decision_point=decision_point,
            context=validate_context(d["context"], where),
            candidates=candidates,
            chosen=chosen,
            join_key=_key(d["join_key"], "join_key", where),
            propensity=propensity,
            propensity_source=source,
            explored=explored,
            safe_candidates=safe,
            logging_probs=logging_probs,
            n_samples=n_samples,
            input_ref=input_ref,
            logging_config=dict(logging_config) if logging_config is not None else None,
            action_map=action_map,
            candidates_source=candidates_source,
            input_sha256=input_sha256,
        )


def load_decisions(source: object) -> list[Decision]:
    """Load decisions from a JSONL path or an iterable of dicts / Decisions."""
    if is_path(source):
        items: Iterable[tuple[str, Any]] = (
            (f"{source}:{lineno}", obj)
            for lineno, obj in read_jsonl(source)  # type: ignore[arg-type]
        )
    elif isinstance(source, Iterable) and not isinstance(source, (Mapping, bytes)):
        items = ((f"decision #{i}", obj) for i, obj in enumerate(source, 1))
    else:
        raise DataError("decisions must be a path or a list of decision records")

    out: list[Decision] = []
    seen: dict[str, str] = {}
    for where, obj in items:
        if isinstance(obj, Decision):
            decision = obj
        elif isinstance(obj, Mapping):
            decision = Decision.from_dict(obj, where)
        else:
            raise DataError(f"{where}: expected a decision object")
        if decision.decision_id in seen:
            raise DataError(
                f"{where}: duplicate decision_id {decision.decision_id!r} "
                f"(first seen at {seen[decision.decision_id]})"
            )
        seen[decision.decision_id] = where
        out.append(decision)
    return out
