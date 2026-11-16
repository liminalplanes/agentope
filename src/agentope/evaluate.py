"""`evaluate`: estimate a target policy's mean outcome on logged decisions."""

import math
import statistics
from collections import Counter
from collections.abc import Sequence
from typing import Any

from . import __version__
from .decisions import Decision, load_decisions
from .errors import AgentopeError, DataError, RefusedError
from .estimators import bootstrap_difference_ci, effective_sample_size, ips, snips
from .io import format_duration, format_rough_duration, is_path, parse_duration, sha256_file
from .outcomes import join_outcomes, load_outcomes
from .propensity_model import PropensityModelResult, fit_logging_policy
from .report import Report
from .targets import resolve_target
from .verdict import VerdictThresholds, assess

AVAILABLE_LEVELS = (1, 3)

LEVEL3_REFUSAL = """\
Level 3 (Estimated) needs your explicit acceptance of an assumption that cannot be checked.

At Level 3, agentope models how the logging policy chose from `context`.
That is only valid if every input that influenced both the
agent's choice and the outcome is recorded in `context`. Anything the agent saw
that is not in `context` (retrieved documents, conversation tone, ...) can bias
the result in either direction, and nothing in the data can reveal it.

Re-run with --accept-unverifiable (CLI) or accept_unverifiable=True (Python) to
proceed, or log with agentope.explore / agentope.randomize to reach Level 1."""

NO_LOGGED_REFUSAL = """\
Level 1 (Logged) was requested, but no decision has a logged propensity.
Log with agentope.explore or agentope.randomize to reach Level 1, or use Level 3
(--level 3 --accept-unverifiable)."""

ACTION_MAP_ASSUMPTIONS = {
    "tool": "Which tool is called matters, not its arguments or wording (action map: tool)",
    "toolset": "Only which tools are called together matters, not their arguments or wording "
    "(action map: toolset)",
    "identity": "The action ids capture everything about the choice that affects the outcome "
    "(action map: identity)",
}

EXPLORE_EPSILON = 0.05
TARGET_ESS = 400  # about ±0.05 on a 0–1 outcome


def _action_map_assumption(action_map: str) -> str:
    if action_map in ACTION_MAP_ASSUMPTIONS:
        return ACTION_MAP_ASSUMPTIONS[action_map]
    if action_map.startswith("tool+args:"):
        fields = action_map.removeprefix("tool+args:")
        return (
            f"The outcome depends only on the tool and the argument fields {fields} "
            f"(action map: {action_map})"
        )
    return f"Whatever the action map ignores does not affect the outcome (action map: {action_map})"


def _exploration_time(decisions: Sequence[Decision]) -> str | None:
    """Rough logging time for ε-exploration to reach ESS ≈ TARGET_ESS for a target
    inside the safe candidates (weights k on matching explored rounds → ESS ≈ m/k)."""
    if len(decisions) < 2:
        return None
    span = max(d.t for d in decisions) - min(d.t for d in decisions)
    if span <= 0:
        return None
    rate = (len(decisions) - 1) / span
    k = statistics.median(len(d.candidates) for d in decisions)
    return format_rough_duration(TARGET_ESS * k / (EXPLORE_EPSILON * rate))


def evaluate(
    decisions: object,
    *,
    outcomes: object,
    horizon: str | float,
    target: object,
    level: int | None = None,
    accept_unverifiable: bool = False,
    default_reward: float = 0.0,
    action_map: str = "tool",
    decision_point: str | None = None,
    seed: int = 0,
    n_bootstrap: int = 2000,
    folds: int = 5,
    thresholds: VerdictThresholds | None = None,
) -> Report:
    """Estimate how ``target`` would have done on the logged ``decisions``.

    decisions: path to decisions.jsonl, or a list of decision dicts / Decisions.
    outcomes: path to outcomes (JSONL or CSV), or a list of outcome dicts.
    horizon: how long after a decision an outcome still counts ('7d', '12h', seconds).
    target: a callable ``(context, candidates) -> {action: prob}``, a target.jsonl
        path, or a 'module:function' / 'file.py:function' string.
    level: 1 (Logged) or 3 (Estimated). By default, Level 1 if any decision has a
        logged propensity (only those decisions are evaluated), otherwise Level 3.
    accept_unverifiable: required for Level 3.

    Raises RefusedError when a guard fires and DataError for invalid input.
    """
    if (
        isinstance(default_reward, bool)
        or not isinstance(default_reward, (int, float))
        or not (math.isfinite(default_reward))
    ):
        raise DataError("default_reward must be a finite number")
    if n_bootstrap < 1:
        raise DataError("n_bootstrap must be at least 1")
    if folds < 1:
        raise DataError("folds must be at least 1")
    if level is not None and level not in (1, 2, 3, 4):
        raise DataError("level must be 1, 2, 3 or 4")
    if level in (2, 4):
        raise DataError(
            f"Level {level} is not available in agentope {__version__} "
            "(Level 2 arrives in v0.2, Level 4 in v0.4)"
        )
    horizon_s = parse_duration(horizon)
    thresholds = thresholds or VerdictThresholds()

    files: dict[str, str] = {}
    for src in (decisions, outcomes):
        if is_path(src):
            files[str(src)] = sha256_file(src)  # type: ignore[arg-type]

    all_decisions = load_decisions(decisions)
    if not all_decisions:
        raise DataError("no decisions to evaluate")
    points = sorted({d.decision_point for d in all_decisions})
    if decision_point is None:
        if len(points) > 1:
            raise DataError(
                f"decisions cover several decision points ({', '.join(points)}); "
                "choose one with --decision-point / decision_point="
            )
        decision_point = points[0]
    ds = [d for d in all_decisions if d.decision_point == decision_point]
    if not ds:
        raise DataError(f"no decisions for decision point {decision_point!r}")

    tgt = resolve_target(target)
    files.update(tgt.files)
    outs = load_outcomes(outcomes)

    has_logged = [d.has_logged_propensity for d in ds]
    if level is None:
        level = 1 if any(has_logged) else 3
    if level == 1:
        if not any(has_logged):
            raise RefusedError(NO_LOGGED_REFUSAL)
        included_idx = [i for i, ok in enumerate(has_logged) if ok]
    else:
        if not accept_unverifiable:
            raise RefusedError(LEVEL3_REFUSAL)
        included_idx = list(range(len(ds)))
    included = [ds[i] for i in included_idx]
    n = len(included)

    joined = join_outcomes(ds, outs, horizon_s, float(default_reward))
    rewards = [joined.rewards[i] for i in included_idx]
    rewarded = sum(joined.rewarded[i] for i in included_idx)

    model: PropensityModelResult | None = None
    if level == 1:
        propensities = [d.propensity for d in included]
        distributions = [d.logging_probs for d in included]
    else:
        model = fit_logging_policy(included, folds=folds, seed=seed)
        propensities = model.propensities
        distributions = model.distributions
    if any(p is None or p <= 0 for p in propensities):
        raise AgentopeError("a logged choice has propensity 0; cannot weight it")

    target_probs = [tgt.probs(d) for d in included]
    weights = [
        tp[d.chosen] / p  # type: ignore[operator]
        for d, tp, p in zip(included, target_probs, propensities, strict=True)
    ]

    # Support: target mass on actions the logging policy could not have taken.
    seen = {d.chosen for d in included}
    masses = []
    partial = False
    for d, tp, dist in zip(included, target_probs, distributions, strict=True):
        if dist is None:
            partial = True
            zero = [a for a in d.candidates if a not in seen]
        else:
            zero = [a for a, p in dist.items() if p == 0]
        masses.append(math.fsum(tp[a] for a in zero))
    if level == 3:
        support_check = "actions chosen in the logs"
    elif partial:
        support_check = "actions chosen in the logs where logging_probs are missing"
    else:
        support_check = "exact"

    # The logging policy's realized mean is taken over every decision at this point,
    # not only the included ones: when only explored rounds are included, their mean
    # is that of the uniform explorer, not of the policy actually running.
    logging_mean = math.fsum(joined.rewards) / len(ds)
    v_ips = ips(weights, rewards)
    v_snips = snips(weights, rewards)
    ci, undefined = (None, 0)
    if v_snips is not None:
        weights_all = [0.0] * len(ds)
        for i, w in zip(included_idx, weights, strict=True):
            weights_all[i] = w
        ci, undefined = bootstrap_difference_ci(
            weights_all, joined.rewards, [d.join_key for d in ds], n_bootstrap, seed
        )
    ess = effective_sample_size(weights)
    expired = n - rewarded
    key_counts = Counter(d.join_key for d in included)
    shared = sum(c for c in key_counts.values() if c > 1)
    n_explored = sum(d.explored for d in included)

    diagnostics: dict[str, Any] = {
        "n": n,
        "n_excluded": len(ds) - n,
        "n_logging_mean": len(ds),
        "rewarded": rewarded,
        "expired": expired,
        "expired_share": expired / n,
        "outcomes": joined.n_outcomes,
        "unmatched_outcomes": joined.unmatched,
        "shared_join_key_decisions": shared,
        "explored": n_explored,
        "ess": ess,
        "ess_share": ess / n,
        "max_weight": max(weights),
        "min_propensity": min(propensities),  # type: ignore[type-var]
        "support_violation_mass": math.fsum(masses) / n,
        "support_violation_decisions": sum(m > 0 for m in masses),
        "support_check": support_check,
        "bootstrap": {"resamples": n_bootstrap, "undefined": undefined, "cluster": "join_key"},
        "propensity_model": None,
    }
    if model is not None:
        diagnostics["propensity_model"] = {
            "type": "multinomial logit",
            "folds": model.folds,
            "context_features": model.feature_keys,
            "n_features": model.n_features,
            "converged": model.converged,
            "log_loss": model.log_loss,
            "baseline_log_loss": model.baseline_log_loss,
            "calibration_error": model.calibration_error,
        }

    verdict, reasons = assess(level, diagnostics, v_snips is not None, thresholds)

    # Level label
    if level == 1:
        if n_explored == n:
            level_detail = "ε-exploration"
        elif n_explored:
            level_detail = "logged, incl. ε-exploration"
        else:
            level_detail = ""
    else:
        level_detail = f"multinomial logit, {model.folds}-fold cross-fit"  # type: ignore[union-attr]

    horizon_label = horizon if isinstance(horizon, str) else format_duration(horizon_s)
    warnings: list[str] = []
    assumptions: list[str] = []
    improve: list[str] = []

    if level == 1:
        assumptions.append("Logged propensities are the probabilities actually used when deciding")
        if n_explored:
            assumptions.append(
                "Whether a decision was explored did not depend on its context "
                "(true when agentope.explore made the coin flip)"
            )
        if len(ds) > n and n_explored < n:
            assumptions.append(
                "Decisions with logged propensities are representative of those without"
            )
        if len(ds) > n:
            warnings.append(
                f"{len(ds) - n:,} of {len(ds):,} decisions have no logged propensity and were "
                "excluded; the estimate covers only the included decisions"
            )
        if all(p == 1.0 for p in propensities):
            warnings.append(
                "Every logged propensity is 1: logging was deterministic, so only targets "
                "that agree with it can be evaluated"
            )
    else:
        assert model is not None
        k = len(model.feature_keys)
        feature_text = ", ".join(model.feature_keys) if k else "none"
        assumptions.append(
            f"Every input that influenced both the logging choice and the outcome is in "
            f"context ({k} features: {feature_text}). Not checkable from data"
        )
        assumptions.append(
            "The propensity model (multinomial logit) describes the logging policy well "
            "(see calibration above)"
        )
        assumptions.append("The interval treats the estimated propensities as fixed")
        if k == 0:
            warnings.append(
                "Context has no usable features: Level 3 then assumes the logging policy's "
                "choice did not depend on the situation at all"
            )
        if model.folds < 2:
            warnings.append(
                "All decisions share one join key, so propensities could not be cross-fitted"
            )
        if not model.converged:
            warnings.append("The propensity model did not fully converge")
        duration = _exploration_time(ds)
        improve.append(
            f"Log with agentope.explore (ε={EXPLORE_EPSILON}) for {duration} → Level 1 at this "
            f"traffic level (aiming for ESS ≈ {TARGET_ESS})"
            if duration
            else f"Log with agentope.explore (ε={EXPLORE_EPSILON}) → Level 1"
        )
        improve.append(
            "Record more of what the agent saw in context; Level 3 is only as good as context"
        )

    assumptions.append(_action_map_assumption(action_map))
    assumptions.append(
        f"Only {decision_point} changes; later steps behave as they did under the logging policy"
    )
    assumptions.append(
        f"An outcome missing within {horizon_label} means outcome = {float(default_reward):g}"
    )
    if shared:
        assumptions.append(
            "Each decision gets the full outcome of its join key, also when other decisions "
            "sharing the key influenced it"
        )
        warnings.append(
            f"{shared:,} decisions share a join key with another decision and get the same outcome"
        )
    if support_check != "exact" and level == 1:
        improve.append(
            "Record full logging distributions (agentope.randomize does) so support is "
            "checked exactly"
        )
    if diagnostics["support_violation_mass"] > 0:
        improve.append(
            f"The target puts {diagnostics['support_violation_mass']:.1%} of its probability on "
            "actions the logging policy never takes; include them in exploration or keep "
            "the target within the logged actions"
        )
    if (
        level == 1
        and n_explored
        and (ess < thresholds.unreliable_min_ess or ess / n < thresholds.weak_ess_share)
    ):
        improve.append("Collect more explored decisions, or raise ε")
    if diagnostics["expired_share"] > thresholds.weak_expired_share:
        improve.append(
            f"{diagnostics['expired_share']:.1%} of decisions expired: check the outcome join "
            f"and whether --horizon {horizon_label} is long enough"
        )
    if undefined:
        warnings.append(
            f"{undefined:,} of {n_bootstrap:,} bootstrap resamples had zero total weight"
        )

    estimates = {
        "logging_mean": logging_mean,
        "snips": v_snips,
        "ips": v_ips,
        "difference": None if v_snips is None else v_snips - logging_mean,
        "ci95": None if ci is None else [ci[0], ci[1]],
        "trustworthy": v_snips is not None and verdict != "unreliable",
    }
    inputs = {
        "files": files,
        "agentope_version": __version__,
        "seed": seed,
        "n_bootstrap": n_bootstrap,
        "folds": folds if level == 3 else None,
        "horizon_seconds": horizon_s,
        "default_reward": float(default_reward),
        "action_map": action_map,
    }
    return Report(
        decision_point=decision_point,
        target=tgt.description,
        level=level,
        level_detail=level_detail,
        estimates=estimates,
        diagnostics=diagnostics,
        verdict=verdict,
        verdict_reasons=reasons,
        assumptions=assumptions,
        how_to_improve=improve,
        warnings=warnings,
        inputs=inputs,
    )
