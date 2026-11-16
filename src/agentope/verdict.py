"""Verdict rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VerdictThresholds:
    unreliable_support_mass: float = 0.01
    """Unreliable when support violations carry more than this share of target mass."""
    unreliable_min_ess: float = 50
    """Unreliable when the effective sample size is below this."""
    unreliable_expired_share: float = 0.5
    """Unreliable when more than this share of decisions expired."""
    weak_ess_share: float = 0.10
    """Weak when ESS is below this share of n."""
    weak_expired_share: float = 0.20
    """Weak when more than this share of decisions expired."""
    weak_reproduction_rate: float = 0.5
    """Level 2: weak when fewer than this share of logged choices came up in samples."""


def assess(
    level: int,
    diag: dict[str, Any],
    estimable: bool,
    th: VerdictThresholds,
    absent_means_default: bool = False,
) -> tuple[str, list[str]]:
    """Return (verdict, reasons). With ``absent_means_default``, a missing outcome is
    the intended meaning (success-only logs), so the expired-share rules don't apply."""
    unreliable = []
    if not estimable:
        unreliable.append("the target gives zero probability to every logged choice")
    if diag["support_violation_mass"] > th.unreliable_support_mass:
        unreliable.append(
            f"support violations carry {diag['support_violation_mass']:.1%} of target "
            f"probability (limit {th.unreliable_support_mass:.0%})"
        )
    if diag["ess"] < th.unreliable_min_ess:
        unreliable.append(
            f"effective sample size {diag['ess']:.1f} is below {th.unreliable_min_ess:g}"
        )
    if not absent_means_default and diag["expired_share"] > th.unreliable_expired_share:
        unreliable.append(
            f"{diag['expired_share']:.1%} of decisions expired "
            f"(limit {th.unreliable_expired_share:.0%})"
        )
    if unreliable:
        return "unreliable", unreliable

    weak = []
    if level >= 3:
        weak.append(f"Level {level} rests on assumptions that cannot be checked from data")
    if diag["ess_share"] < th.weak_ess_share:
        weak.append(
            f"effective sample size is {diag['ess_share']:.1%} of n (below {th.weak_ess_share:.0%})"
        )
    if not absent_means_default and diag["expired_share"] > th.weak_expired_share:
        weak.append(
            f"{diag['expired_share']:.1%} of decisions expired (above {th.weak_expired_share:.0%})"
        )
    sampling = diag.get("sampling")
    if sampling and sampling["reproduction_rate"] < th.weak_reproduction_rate:
        weak.append(
            f"the logged choice came up again in samples on only "
            f"{sampling['reproduction_rate']:.0%} of decisions "
            f"(below {th.weak_reproduction_rate:.0%})"
        )
    if weak:
        return "weak", weak
    return "ok", []
