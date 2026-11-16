"""The evaluation report (spec §9)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

LEVEL_NAMES = {1: "Logged", 2: "Sampled", 3: "Estimated", 4: "Modeled"}
_RULE = "─" * 60


@dataclass(frozen=True, slots=True)
class Report:
    decision_point: str
    target: str
    level: int
    level_detail: str
    estimates: dict[str, Any]
    diagnostics: dict[str, Any]
    verdict: str
    verdict_reasons: list[str]
    assumptions: list[str]
    how_to_improve: list[str]
    warnings: list[str]
    inputs: dict[str, Any]

    @property
    def difference(self) -> float | None:
        return self.estimates["difference"]

    @property
    def ci95(self) -> tuple[float, float] | None:
        ci = self.estimates["ci95"]
        return None if ci is None else (ci[0], ci[1])

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_point": self.decision_point,
            "target": self.target,
            "level": {
                "level": self.level,
                "name": LEVEL_NAMES[self.level],
                "detail": self.level_detail,
            },
            "estimates": self.estimates,
            "diagnostics": self.diagnostics,
            "verdict": self.verdict,
            "verdict_reasons": self.verdict_reasons,
            "assumptions": self.assumptions,
            "how_to_improve": self.how_to_improve,
            "warnings": self.warnings,
            "inputs": self.inputs,
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, allow_nan=False)

    def __str__(self) -> str:
        return render(self)


def _row(lines: list[str], label: str, text: str) -> None:
    lines.append(f"{label:<16}{text}".rstrip())


def render(r: Report) -> str:
    est, diag = r.estimates, r.diagnostics
    n = diag["n"]
    lines = [f"agentope · {r.decision_point} · target: {r.target}", _RULE]

    level = f"L{r.level} {LEVEL_NAMES[r.level]}"
    _row(lines, "Evidence level", f" {level} ({r.level_detail})" if r.level_detail else f" {level}")
    if diag.get("absent_means_default"):
        outcome_text = (
            f"(outcome recorded {diag['rewarded']:,} · none recorded {diag['expired']:,} "
            f"→ default · {diag['expired_share']:.1%})"
        )
    else:
        outcome_text = (
            f"(rewarded {diag['rewarded']:,} · expired {diag['expired']:,} · "
            f"{diag['expired_share']:.1%})"
        )
    _row(lines, "Decisions", f" {n:,}   {outcome_text}")
    if diag["n_excluded"]:
        why = {1: "without logged propensities", 2: "without logging-model samples"}.get(
            r.level, "without what this level needs"
        )
        _row(lines, "", f" {diag['n_excluded']:,} {why} excluded")
    if diag["unmatched_outcomes"]:
        _row(lines, "", f" {diag['unmatched_outcomes']:,} outcomes matched no decision")
    lines.append("")

    over = f" (all {diag['n_logging_mean']:,} decisions)" if diag["n_excluded"] else ""
    _row(lines, "Logging policy", f"{est['logging_mean']:6.3f}  realized mean outcome{over}")
    if est["snips"] is None:
        _row(lines, "Target policy", " no trustworthy estimate")
        _row(lines, "", " (the target never agrees with a logged choice)")
    elif r.verdict == "unreliable":
        _row(lines, "Target policy", " no trustworthy estimate")
        _row(
            lines,
            "",
            f" (SNIPS {est['snips']:.3f} · IPS {est['ips']:.3f} · difference "
            f"{est['difference']:+.3f}, shown for diagnosis only)",
        )
    else:
        _row(lines, "Target policy", f"{est['snips']:6.3f}  SNIPS   (IPS {est['ips']:.3f})")
        ci = est["ci95"]
        ci_text = f"95% CI [{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "95% CI unavailable"
        _row(lines, "Difference", f"{est['difference']:+6.3f}  {ci_text}")
    lines.append("")

    support = (
        "support violations 0"
        if diag["support_violation_mass"] == 0
        else f"support violations {diag['support_violation_mass']:.1%} of target mass "
        f"({diag['support_violation_decisions']:,} decisions)"
    )
    if diag["support_check"] != "exact":
        support += f" [checked against {diag['support_check']}]"
    _row(
        lines,
        "Diagnostics",
        f" ESS {diag['ess']:,.0f} ({diag['ess_share']:.0%} of n) · max weight "
        f"{diag['max_weight']:.3g} · min propensity {diag['min_propensity']:.3g}",
    )
    _row(lines, "", f" {support}")
    sampling = diag.get("sampling")
    if sampling:
        _row(
            lines,
            "",
            f" logged choice reproduced in samples: {sampling['reproduction_rate']:.0%} · "
            f"{sampling['low_count_decisions']:,} decisions with < 3 matching samples",
        )
    model = diag.get("propensity_model")
    if model:
        features = ", ".join(model["context_features"]) or "none"
        _row(
            lines,
            "",
            f" propensity model: {model['folds']}-fold cross-fit · features: {features}",
        )
        _row(
            lines,
            "",
            f" log loss {model['log_loss']:.3f} vs {model['baseline_log_loss']:.3f} "
            f"context-free · calibration error {model['calibration_error']:.3f}",
        )
    lines.append("")

    _row(lines, "Verdict", f" {r.verdict}")
    for reason in r.verdict_reasons:
        _row(lines, "", f"  • {reason}")

    for title, items in (
        ("Warnings:", r.warnings),
        ("This estimate assumes:", r.assumptions),
        ("To strengthen this:", r.how_to_improve),
    ):
        if items:
            lines.extend(["", title])
            lines.extend(f"  • {item}" for item in items)
    return "\n".join(lines)
