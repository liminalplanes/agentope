"""Simulated agent logs with known ground truth.

Contexts: intent ∈ {refund, status, other} (uniform) and pro ∈ {True, False}
(P(pro) = 0.3). The outcome is Bernoulli with probability q(context, action).
Because the context distribution is finite, every policy's true value is exact.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

ACTIONS = ["search", "lookup_order", "escalate", "__none__"]
INTENTS = ["refund", "status", "other"]
P_PRO = 0.3

_Q = {
    "refund": {"lookup_order": 0.7, "escalate": 0.5, "search": 0.3, "__none__": 0.2},
    "status": {"lookup_order": 0.8, "search": 0.5, "escalate": 0.3, "__none__": 0.4},
    "other": {"search": 0.6, "__none__": 0.5, "escalate": 0.4, "lookup_order": 0.2},
}

type Policy = Callable[[dict, list[str]], Mapping[str, float]]


def q(ctx: dict, action: str) -> float:
    return min(1.0, _Q[ctx["intent"]][action] + (0.1 if ctx["pro"] else 0.0))


def logging_policy(ctx: dict, candidates: list[str]) -> dict[str, float]:
    """Context-dependent with full support: favours a different action per intent,
    and pro users are escalated more often."""
    favourite = {"refund": "escalate", "status": "search", "other": "__none__"}[ctx["intent"]]
    weights = {a: (4.0 if a == favourite else 1.0) for a in ACTIONS}
    if ctx["pro"]:
        weights["escalate"] += 2.0
    total = sum(weights.values())
    return {a: w / total for a, w in weights.items()}


def best_action_target(ctx: dict, candidates: list[str]) -> dict[str, float]:
    best = max(ACTIONS, key=lambda a: q(ctx, a))
    return {best: 1.0}


def contexts_with_weights() -> list[tuple[dict, float]]:
    return [
        ({"intent": intent, "pro": pro}, (1 / len(INTENTS)) * (P_PRO if pro else 1 - P_PRO))
        for intent in INTENTS
        for pro in (True, False)
    ]


def true_value(policy: Policy) -> float:
    return sum(
        w * sum(p * q(ctx, a) for a, p in policy(ctx, ACTIONS).items())
        for ctx, w in contexts_with_weights()
    )


def simulate(
    n: int,
    seed: int,
    mode: str = "logged",
    epsilon: float = 0.2,
    horizon: float = 86400.0,
    start: float = 1_763_280_000.0,
) -> tuple[list[dict], list[dict]]:
    """Return (decisions, outcomes).

    mode="logged": propensities and logging_probs recorded (Level 1).
    mode="explore": ε-exploration over all actions; non-explored rounds come from
        the logging policy and have no propensity.
    mode="unlogged": no propensities at all (Level 3).
    """
    rng = random.Random(seed)
    decisions, outcomes = [], []
    for i in range(n):
        ctx = {"intent": rng.choice(INTENTS), "pro": rng.random() < P_PRO}
        t = start + i * 60.0
        probs = logging_policy(ctx, ACTIONS)
        record = {
            "decision_id": f"d{i}",
            "t": t,
            "decision_point": "tool_choice",
            "context": ctx,
            "candidates": ACTIONS,
            "join_key": f"conv-{i}",
        }
        if mode == "explore" and rng.random() < epsilon:
            chosen = rng.choice(ACTIONS)
            record |= {"chosen": chosen, "explored": True, "safe_candidates": ACTIONS}
        else:
            chosen = rng.choices(ACTIONS, weights=[probs[a] for a in ACTIONS])[0]
            record["chosen"] = chosen
            if mode == "logged":
                record |= {"propensity": probs[chosen], "logging_probs": probs}
        decisions.append(record)
        value = 1.0 if rng.random() < q(ctx, chosen) else 0.0
        outcomes.append({"join_key": f"conv-{i}", "t": t + horizon / 2, "value": value})
    return decisions, outcomes
