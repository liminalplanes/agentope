"""Outcomes and the outcome join (spec §6.2)."""

import csv
import math
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .decisions import Decision
from .errors import DataError
from .io import first_char, is_path, open_text, parse_time, read_jsonl


@dataclass(frozen=True, slots=True)
class Outcome:
    join_key: str
    t: float
    value: float


def _outcome(d: Mapping[str, Any], where: str) -> Outcome:
    for field in ("join_key", "t", "value"):
        if d.get(field) in (None, ""):
            raise DataError(f"{where}: missing required field {field!r}")
    key = d["join_key"]
    if isinstance(key, bool) or not isinstance(key, (str, int)):
        raise DataError(f"{where}: join_key must be a string")
    value = d["value"]
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            raise DataError(f"{where}: value must be a number, got {value!r}") from None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DataError(f"{where}: value must be a finite number, got {value!r}")
    return Outcome(join_key=str(key), t=parse_time(d["t"], where), value=float(value))


def load_outcomes(source: object) -> list[Outcome]:
    """Load outcomes from a JSONL or CSV path (detected by content) or an iterable of dicts."""
    if is_path(source):
        if first_char(source) == "{":  # type: ignore[arg-type]
            return [_outcome(obj, f"{source}:{n}") for n, obj in read_jsonl(source)]  # type: ignore[arg-type]
        with open_text(source) as f:  # type: ignore[arg-type]
            reader = csv.DictReader(f)
            missing = {"join_key", "t", "value"} - set(reader.fieldnames or ())
            if missing:
                raise DataError(f"{source}: CSV is missing columns: {', '.join(sorted(missing))}")
            return [_outcome(row, f"{source}:{n}") for n, row in enumerate(reader, 2)]
    if isinstance(source, Iterable) and not isinstance(source, (Mapping, bytes)):
        out = []
        for i, obj in enumerate(source, 1):
            if isinstance(obj, Outcome):
                out.append(obj)
            elif isinstance(obj, Mapping):
                out.append(_outcome(obj, f"outcome #{i}"))
            else:
                raise DataError(f"outcome #{i}: expected an outcome object")
        return out
    raise DataError("outcomes must be a path or a list of outcome records")


@dataclass(frozen=True, slots=True)
class JoinResult:
    rewards: list[float]
    """Aligned with the decisions passed in."""
    rewarded: list[bool]
    n_outcomes: int
    unmatched: int
    """Outcomes not assigned to any decision."""


def join_outcomes(
    decisions: Sequence[Decision],
    outcomes: Sequence[Outcome],
    horizon: float,
    default_reward: float,
) -> JoinResult:
    """The reward of a decision is the first outcome with the same join key and
    ``decision.t <= outcome.t < decision.t + horizon``; otherwise ``default_reward``.
    Ties in outcome time are broken by input order."""
    by_key: dict[str, list[tuple[float, int, float]]] = defaultdict(list)
    for i, o in enumerate(outcomes):
        by_key[o.join_key].append((o.t, i, o.value))
    for entries in by_key.values():
        entries.sort()

    used: set[int] = set()
    rewards: list[float] = []
    rewarded: list[bool] = []
    for d in decisions:
        entries = by_key.get(d.join_key)
        hit = None
        if entries:
            j = bisect_left(entries, d.t, key=lambda e: e[0])
            if j < len(entries) and entries[j][0] < d.t + horizon:
                hit = entries[j]
        if hit is None:
            rewards.append(default_reward)
            rewarded.append(False)
        else:
            rewards.append(hit[2])
            rewarded.append(True)
            used.add(hit[1])
    return JoinResult(
        rewards=rewards,
        rewarded=rewarded,
        n_outcomes=len(outcomes),
        unmatched=len(outcomes) - len(used),
    )
