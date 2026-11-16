"""`check`: what can be evaluated with the data at hand (spec §10).

Runs on traces or decisions alone: no outcomes, no LLM calls, no target policy.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .action_maps import NONE_ACTION
from .decisions import Decision, load_decisions


def _compact(n: float) -> str:
    if n >= 1e6:
        return f"{n / 1e6:.1f}M".replace(".0M", "M")
    if n >= 1e4:
        return f"{n / 1e3:.0f}k"
    return f"{n:,.0f}"


@dataclass
class PointCheck:
    decision_point: str
    n: int
    logged: int
    explored: int
    stored_inputs: int
    models: list[str]
    deterministic: bool
    context_features: list[str]
    candidates_from: Counter[str]
    none_in_candidates: bool
    calls_logging: int
    calls_target: int

    @property
    def levels(self) -> dict[int, bool]:
        return {
            1: self.logged > 0,
            2: self.stored_inputs > 0 and not self.deterministic,
            3: bool(self.context_features),
        }

    @property
    def best(self) -> int | None:
        return next((lvl for lvl, ok in self.levels.items() if ok), None)


@dataclass
class CheckReport:
    source: str
    points: list[PointCheck]
    n_samples: int
    llm_target: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "n_samples": self.n_samples,
            "decision_points": [
                {
                    "decision_point": p.decision_point,
                    "decisions": p.n,
                    "levels": {str(k): v for k, v in p.levels.items()} | {"4": False},
                    "best_level": p.best,
                    "logged": p.logged,
                    "explored": p.explored,
                    "stored_inputs": p.stored_inputs,
                    "logging_models": p.models,
                    "deterministic_logging": p.deterministic,
                    "context_features": p.context_features,
                    "candidates_from": dict(p.candidates_from),
                    "estimated_calls": {"logging": p.calls_logging, "target": p.calls_target},
                }
                for p in self.points
            ],
            "notes": self.notes,
        }

    def __str__(self) -> str:
        lines: list[str] = []
        for p in self.points:
            ok = p.levels
            mark = {True: "✓", False: "✗"}
            lines.append(f"{p.decision_point} · {p.n:,} decisions found in {self.source}")
            lines.append("")
            if ok[1]:
                extra = f" ({p.explored:,} explored)" if p.explored else ""
                l1 = f"{p.logged:,}/{p.n:,} with logged propensities{extra}"
            else:
                l1 = "no logged propensities  → use agentope.explore or agentope.randomize"
            lines.append(f"  Level 1 Logged     {mark[ok[1]]}  {l1}")

            if p.stored_inputs == 0:
                l2 = "no stored inputs (content capture off)  → turn on content capture"
            elif p.deterministic:
                l2 = "logging was deterministic (temperature 0): no overlap to sample"
            else:
                models = ", ".join(p.models) or "model unknown (pass --model)"
                l2 = (
                    f"stored inputs: {p.stored_inputs:,}/{p.n:,} · logging model: {models} "
                    "(availability is checked by `sample`)"
                )
            lines.append(f"  Level 2 Sampled    {mark[ok[2]]}  {l2}")
            if p.stored_inputs:
                calls = _compact(p.calls_logging)
                cost = f"est. cost at N={self.n_samples}: {calls} calls (logging)"
                if self.llm_target:
                    cost += f" + {_compact(p.calls_target)} (LLM target)"
                lines.append(f"                        {cost}")

            if p.context_features:
                feats = ", ".join(p.context_features)
                l3 = (
                    f"context has {len(p.context_features)} features: {feats} "
                    "(needs --accept-unverifiable)"
                )
            else:
                l3 = "context is empty  → add features with --context name=attribute"
            lines.append(f"  Level 3 Estimated  {mark[ok[3]]}  {l3}")
            lines.append("  Level 4 Modeled    –  not available yet (v0.4)")
            lines.append("")

            sources = " · ".join(
                f"{'inferred from the logs' if s == 'inferred' else 'from ' + s} on {c / p.n:.0%}"
                for s, c in p.candidates_from.most_common()
            )
            none = f"; {NONE_ACTION} included" if p.none_in_candidates else ""
            lines.append(f"  Candidates: {sources}{none}")
            best = f"Level {p.best}" if p.best else "nothing yet"
            lines.append(f"  Best available: {best}")
            lines.append("")
        if self.notes:
            lines.append("  Warnings:")
            lines.extend(f"    • {note}" for note in self.notes)
        return "\n".join(lines).rstrip()


def _point(
    decision_point: str, ds: Sequence[Decision], n_samples: int, llm_target: bool
) -> PointCheck:
    stored = sum(1 for d in ds if d.input_ref or d.input_sha256)
    models = sorted(
        {
            str((d.logging_config or {})["model"])
            for d in ds
            if (d.logging_config or {}).get("model")
        }
    )
    temps = [
        (d.logging_config or {}).get("temperature") for d in ds if d.input_ref or d.input_sha256
    ]
    deterministic = bool(temps) and all(t == 0 for t in temps)
    features = []
    for key in sorted({k for d in ds for k in d.context}):
        values = {repr(d.context.get(key)) for d in ds if d.context.get(key) is not None}
        if len(values) > 1:
            features.append(key)
    return PointCheck(
        decision_point=decision_point,
        n=len(ds),
        logged=sum(d.has_logged_propensity for d in ds),
        explored=sum(d.explored for d in ds),
        stored_inputs=stored,
        models=models,
        deterministic=deterministic,
        context_features=features,
        candidates_from=Counter(d.candidates_source or "decisions file" for d in ds),
        none_in_candidates=any(NONE_ACTION in d.candidates for d in ds),
        calls_logging=stored * n_samples,
        calls_target=stored * n_samples if llm_target else 0,
    )


def check(
    decisions: object,
    *,
    n_samples: int = 32,
    llm_target: bool = False,
    decision_point: str | None = None,
    source: str | None = None,
) -> CheckReport:
    """Readiness report for decisions (a decisions.jsonl path, a list, or the result
    of :func:`agentope.import_traces`, whose import warnings are included)."""
    loaded = load_decisions(decisions)
    points: dict[str, list[Decision]] = {}
    for d in loaded:
        if decision_point is None or d.decision_point == decision_point:
            points.setdefault(d.decision_point, []).append(d)
    summary = getattr(decisions, "summary", None)
    if source is None:
        source = (
            summary.source
            if summary is not None
            else str(decisions)
            if isinstance(decisions, str)
            else "decisions"
        )
    notes: list[str] = []
    if summary is not None:
        rendered = summary.render().splitlines()
        notes.extend(line.removeprefix("  ! ") for line in rendered if line.startswith("  ! "))
    report = CheckReport(
        source=source,
        points=[_point(p, ds, n_samples, llm_target) for p, ds in sorted(points.items())],
        n_samples=n_samples,
        llm_target=llm_target,
        notes=notes,
    )
    if any(p.stored_inputs == 0 for p in report.points):
        report.notes.append(
            "Without stored inputs, LLM targets (prompt or model changes) can't be evaluated, "
            "and only the tool and toolset action maps work"
        )
    return report
