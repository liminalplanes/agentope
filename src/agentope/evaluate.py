"""`evaluate`: estimate a target policy's mean outcome on logged decisions."""

import math
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .decisions import Decision, load_decisions
from .errors import AgentopeError, DataError, RefusedError
from .estimators import bootstrap_difference_ci, effective_sample_size, ips, snips
from .io import format_duration, format_rough_duration, is_path, parse_duration, sha256_file
from .outcomes import join_outcomes, load_outcomes
from .propensity_model import PropensityModelResult, fit_logging_policy
from .report import Report
from .sampling import LOGGING, SampleRecord, load_samples, resolve_llm_target
from .targets import resolve_target
from .verdict import VerdictThresholds, assess

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

NO_SAMPLES_REFUSAL = """\
Level 2 (Sampled) was requested, but there are no logging-model samples for these
decisions. Run `agentope sample decisions.jsonl -o samples.jsonl` (needs stored
inputs, i.e. content capture) and pass --samples samples.jsonl."""

ACTION_MAP_ASSUMPTIONS = {
    "tool": "Which tool is called matters, not its arguments or wording (action map: tool)",
    "toolset": "Only which tools are called together matters, not their arguments or wording "
    "(action map: toolset)",
    "identity": "The action ids capture everything about the choice that affects the outcome "
    "(action map: identity)",
}

EXPLORE_EPSILON = 0.05
TARGET_ESS = 400  # about ±0.05 on a 0–1 outcome
LOW_COUNT = 3


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


def _sampled(samples: dict, decision: Decision, policy: str) -> SampleRecord | None:
    record = samples.get((decision.decision_id, policy))
    return record if record is not None and record.valid > 0 else None


def evaluate(
    decisions: object,
    *,
    outcomes: object,
    horizon: str | float,
    target: object,
    level: int | None = None,
    accept_unverifiable: bool = False,
    default_reward: float = 0.0,
    absent_means_default: bool = False,
    action_map: str | None = None,
    decision_point: str | None = None,
    samples: object = None,
    alpha: float = 0.5,
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
        path, a 'module:function' / 'file.py:function' string, or an LLM target
        (``LLMPolicy`` or target.yaml), whose probabilities come from ``samples``.
    level: 1 (Logged), 2 (Sampled) or 3 (Estimated). By default the strongest
        level the data supports: 1 if any decision has a logged propensity, else 2
        if ``samples`` has logging-model samples, else 3. Only decisions that have
        what the level needs are evaluated.
    accept_unverifiable: required for Level 3.
    absent_means_default: a decision with no outcome within the horizon really had
        outcome ``default_reward`` (e.g. only successes are recorded). Turns off the
        expired-share verdict rules; the share is still reported.
    action_map: the action map that produced ``chosen``, for the report. By default,
        the one recorded by trace import, else "tool".
    samples: samples.jsonl from ``agentope sample`` (Level 2 and LLM targets).
    alpha: additive smoothing for sampled logging propensities (Level 2).

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
    if not (isinstance(alpha, (int, float)) and alpha > 0):
        raise DataError("alpha must be a positive number")
    if level is not None and level not in (1, 2, 3, 4):
        raise DataError("level must be 1, 2, 3 or 4")
    if level == 4:
        raise DataError(f"Level 4 is not available in agentope {__version__} (it arrives in v0.4)")
    horizon_s = parse_duration(horizon)
    thresholds = thresholds or VerdictThresholds()

    files: dict[str, str] = {}
    for src in (decisions, outcomes, samples):
        if is_path(src) and Path(str(src)).is_file():
            files[str(src)] = sha256_file(src)  # type: ignore[arg-type]
    files.update(getattr(decisions, "source_files", None) or {})

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
    if action_map is None:
        recorded = {d.action_map for d in ds if d.action_map}
        action_map = recorded.pop() if len(recorded) == 1 else "tool"

    sample_set = load_samples(samples)
    llm_target = resolve_llm_target(target)
    tgt = None
    if llm_target is not None:
        files.update(llm_target.source_files)
        target_description = llm_target.description
    else:
        tgt = resolve_target(target)
        files.update(tgt.files)
        target_description = tgt.description
    outs = load_outcomes(outcomes)

    has_logged = [d.has_logged_propensity for d in ds]
    has_sampled = [_sampled(sample_set, d, LOGGING) is not None for d in ds]
    if level is None:
        level = 1 if any(has_logged) else 2 if any(has_sampled) else 3
    if level == 1:
        if not any(has_logged):
            raise RefusedError(NO_LOGGED_REFUSAL)
        eligible = has_logged
    elif level == 2:
        if not any(has_sampled):
            raise RefusedError(NO_SAMPLES_REFUSAL)
        eligible = has_sampled
    else:
        if not accept_unverifiable:
            raise RefusedError(LEVEL3_REFUSAL)
        eligible = [True] * len(ds)
    lacking_level = len(ds) - sum(eligible)

    lacking_target = 0
    if llm_target is not None:
        with_target = [_sampled(sample_set, d, llm_target.name) is not None for d in ds]
        lacking_target = sum(1 for e, t in zip(eligible, with_target, strict=True) if e and not t)
        eligible = [e and t for e, t in zip(eligible, with_target, strict=True)]
        if not any(eligible):
            raise DataError(
                f"no samples for LLM target {llm_target.name!r}; run agentope sample with "
                "--target to sample it on the stored inputs"
            )
    included_idx = [i for i, ok in enumerate(eligible) if ok]
    included = [ds[i] for i in included_idx]
    n = len(included)

    joined = join_outcomes(ds, outs, horizon_s, float(default_reward))
    rewards = [joined.rewards[i] for i in included_idx]
    rewarded = sum(joined.rewarded[i] for i in included_idx)

    # Logging propensities, and the actions the logging policy could not have taken.
    model: PropensityModelResult | None = None
    seen = {d.chosen for d in included}
    zero_sets: list[set[str]] = []
    partial = False
    logging_records: list[SampleRecord] = []
    if level == 1:
        propensities = [float(d.propensity) for d in included]  # type: ignore[arg-type]
        for d in included:
            if d.logging_probs is None:
                partial = True
                zero_sets.append({a for a in d.candidates if a not in seen})
            else:
                zero_sets.append({a for a, p in d.logging_probs.items() if p == 0})
        support_check = (
            "actions chosen in the logs where logging_probs are missing" if partial else "exact"
        )
    elif level == 2:
        propensities = []
        for d in included:
            record = _sampled(sample_set, d, LOGGING)
            assert record is not None
            logging_records.append(record)
            k = len(d.candidates)
            propensities.append(
                (record.counts.get(d.chosen, 0) + alpha) / (record.valid + alpha * k)
            )
            zero_sets.append({a for a in d.candidates if record.counts.get(a, 0) == 0})
        support_check = "actions the logging model never produced in samples"
    else:
        model = fit_logging_policy(included, folds=folds, seed=seed)
        propensities = model.propensities
        zero_sets = [{a for a, p in dist.items() if p == 0} for dist in model.distributions]
        support_check = "actions chosen in the logs"
    if any(p <= 0 for p in propensities):
        raise AgentopeError("a logged choice has propensity 0; cannot weight it")

    # Target probabilities. An LLM target's samples outside the candidates are mass
    # the logging policy could not have produced: counted as a support violation.
    target_probs: list[dict[str, float]] = []
    off_mass: list[float] = []
    for d in included:
        if llm_target is not None:
            record = _sampled(sample_set, d, llm_target.name)
            assert record is not None
            probs = {a: record.counts.get(a, 0) / record.valid for a in d.candidates}
            target_probs.append(probs)
            off_mass.append(max(0.0, 1.0 - math.fsum(probs.values())))
        else:
            target_probs.append(tgt.probs(d))  # type: ignore[union-attr]
            off_mass.append(0.0)

    weights = [
        tp[d.chosen] / p for d, tp, p in zip(included, target_probs, propensities, strict=True)
    ]
    masses = [
        math.fsum(tp[a] for a in zero) + off
        for tp, zero, off in zip(target_probs, zero_sets, off_mass, strict=True)
    ]

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
        "min_propensity": min(propensities),
        "support_violation_mass": math.fsum(masses) / n,
        "support_violation_decisions": sum(m > 0 for m in masses),
        "support_check": support_check,
        "bootstrap": {"resamples": n_bootstrap, "undefined": undefined, "cluster": "join_key"},
        "propensity_model": None,
        "sampling": None,
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
    if level == 2:
        sampling = _sampling_diagnostics(included, logging_records, alpha)
        diagnostics["sampling"] = sampling

    diagnostics["absent_means_default"] = absent_means_default
    verdict, reasons = assess(
        level, diagnostics, v_snips is not None, thresholds, absent_means_default
    )

    if level == 1:
        if n_explored == n:
            level_detail = "ε-exploration"
        elif n_explored:
            level_detail = "logged, incl. ε-exploration"
        else:
            level_detail = ""
    elif level == 2:
        level_detail = f"N={diagnostics['sampling']['n_median']:g}, α={alpha:g}"
    else:
        level_detail = f"multinomial logit, {model.folds}-fold cross-fit"  # type: ignore[union-attr]

    horizon_label = horizon if isinstance(horizon, str) else format_duration(horizon_s)
    warnings: list[str] = []
    assumptions: list[str] = []
    improve: list[str] = []

    if lacking_level:
        what = {1: "logged propensity", 2: "logging-model samples", 3: ""}[level]
        warnings.append(
            f"{lacking_level:,} of {len(ds):,} decisions have no {what} and were excluded; "
            "the estimate covers only the included decisions"
        )
    if lacking_target:
        warnings.append(
            f"{lacking_target:,} decisions have no samples for {llm_target.name} "  # type: ignore[union-attr]
            "and were excluded"
        )

    if level == 1:
        assumptions.append("Logged propensities are the probabilities actually used when deciding")
        if n_explored:
            assumptions.append(
                "Whether a decision was explored did not depend on its context "
                "(true when agentope.explore made the coin flip)"
            )
        if lacking_level and n_explored < n:
            assumptions.append(
                "Decisions with logged propensities are representative of those without"
            )
        if all(p == 1.0 for p in propensities):
            warnings.append(
                "Every logged propensity is 1: logging was deterministic, so only targets "
                "that agree with it can be evaluated"
            )
    elif level == 2:
        _level2_text(diagnostics["sampling"], alpha, lacking_level, assumptions, warnings, improve)
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
        improve.append(
            "If content capture is on, sample the logging model (agentope sample) → Level 2"
        )

    if llm_target is not None:
        assumptions.append(
            f"The target's probabilities are estimated from its samples on the stored inputs "
            f"({llm_target.name})"
        )
    assumptions.append(_action_map_assumption(action_map))
    assumptions.append(
        f"Only {decision_point} changes; later steps behave as they did under the logging policy"
    )
    if absent_means_default:
        assumptions.append(
            f"No outcome within {horizon_label} means the outcome really was "
            f"{float(default_reward):g} (absence is recorded as the outcome)"
        )
    else:
        assumptions.append(
            f"An outcome missing within {horizon_label} means outcome = {float(default_reward):g}"
        )
    if any(d.candidates_source == "inferred" for d in included):
        assumptions.append(
            "Candidates were inferred from the actions seen in the logs: no other action "
            "was available"
        )
    if shared:
        assumptions.append(
            "Each decision gets the full outcome of its join key, also when other decisions "
            "sharing the key influenced it"
        )
        warnings.append(
            f"{shared:,} decisions share a join key with another decision and get the same outcome"
        )
    if level == 1 and support_check != "exact":
        improve.append(
            "Record full logging distributions (agentope.randomize does) so support is "
            "checked exactly"
        )
    if diagnostics["support_violation_mass"] > 0:
        remedy = (
            "sample more per decision, or keep the target within what the model does"
            if level == 2
            else "include them in exploration, or keep the target within the logged actions"
        )
        improve.append(
            f"The target puts {diagnostics['support_violation_mass']:.1%} of its probability on "
            f"actions the logging policy never takes; {remedy}"
        )
    if (
        level == 1
        and n_explored
        and (ess < thresholds.unreliable_min_ess or ess / n < thresholds.weak_ess_share)
    ):
        improve.append("Collect more explored decisions, or raise ε")
    if not absent_means_default and diagnostics["expired_share"] > thresholds.weak_expired_share:
        improve.append(
            f"{diagnostics['expired_share']:.1%} of decisions expired: check the outcome join "
            f"and whether --horizon {horizon_label} is long enough. If only some outcomes "
            "are ever recorded (e.g. successes), use --absent-means-default"
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
        "alpha": alpha if level == 2 else None,
        "horizon_seconds": horizon_s,
        "default_reward": float(default_reward),
        "absent_means_default": absent_means_default,
        "action_map": action_map,
    }
    return Report(
        decision_point=decision_point,
        target=target_description,
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


def _sampling_diagnostics(
    decisions: Sequence[Decision], records: Sequence[SampleRecord], alpha: float
) -> dict[str, Any]:
    valid = [r.valid for r in records]
    total = sum(valid)
    in_candidates = sum(
        sum(c for a, c in r.counts.items() if a in d.candidates)
        for d, r in zip(decisions, records, strict=True)
    )
    reproduced = sum(r.counts.get(d.chosen, 0) > 0 for d, r in zip(decisions, records, strict=True))
    low = sum(
        r.counts.get(d.chosen, 0) < LOW_COUNT for d, r in zip(decisions, records, strict=True)
    )

    mismatched = 0
    checked = 0
    hash_mismatch = 0
    for d, r in zip(decisions, records, strict=True):
        config = d.logging_config or {}
        expected = config.get("response_model") or config.get("model")
        if expected and r.response_models:
            checked += sum(r.response_models.values())
            mismatched += sum(
                c for m, c in r.response_models.items() if m.lower() != str(expected).lower()
            )
        if d.input_sha256 and r.stored_input_sha256 and d.input_sha256 != r.stored_input_sha256:
            hash_mismatch += 1
    models = sorted({r.model for r in records if r.model})
    return {
        "alpha": alpha,
        "n_median": statistics.median(valid),
        "samples": total,
        "failed_samples": sum(r.failed for r in records),
        "reproduction_rate": reproduced / len(records),
        "low_count_decisions": low,
        "off_candidate_share": (total - in_candidates) / total if total else 0.0,
        "model_mismatch_share": mismatched / checked if checked else None,
        "input_hash_mismatches": hash_mismatch,
        "deterministic": all(len(r.counts) == 1 for r in records),
        "models": models,
    }


def _level2_text(
    s: dict[str, Any],
    alpha: float,
    excluded: int,
    assumptions: list[str],
    warnings: list[str],
    improve: list[str],
) -> None:
    models = ", ".join(s["models"]) or "unknown"
    assumptions.append(
        "The stored inputs are everything the model saw (system prompt, history, tool "
        "definitions, retrieved documents)"
    )
    assumptions.append(
        f"The logging model ({models}) behaves today as it did when logging; the logged "
        f"choice came up again in samples on {s['reproduction_rate']:.0%} of decisions"
    )
    assumptions.append(
        f"{s['n_median']:g} samples per decision (smoothing α={alpha:g}) estimate the "
        f"propensities well enough; {s['low_count_decisions']:,} decisions saw the logged "
        f"choice fewer than {LOW_COUNT} times"
    )
    if excluded:
        assumptions.append("Decisions with stored inputs are representative of those without")
    if s["deterministic"]:
        warnings.append(
            "The logging model gave the same answer in every sample on every decision: "
            "there is no overlap, so only targets that agree with it can be evaluated"
        )
    if s["input_hash_mismatches"]:
        warnings.append(
            f"{s['input_hash_mismatches']:,} stored inputs changed since import "
            "(input_sha256 differs)"
        )
    if s["model_mismatch_share"]:
        warnings.append(
            f"{s['model_mismatch_share']:.1%} of samples were answered by a different model "
            "than the one that logged"
        )
    if s["failed_samples"]:
        warnings.append(f"{s['failed_samples']:,} samples failed and are not counted")
    if s["off_candidate_share"] > 0:
        warnings.append(
            f"{s['off_candidate_share']:.1%} of logging samples chose an action outside the "
            "candidates"
        )
    if s["reproduction_rate"] < 0.5:
        improve.append(
            "Most logged choices never came up again: check that stored inputs are complete "
            "and that the model, its version and its serving settings are unchanged"
        )
    if s["low_count_decisions"]:
        more = max(64, int(s["n_median"]) * 2)
        improve.append(
            f"Sample more per decision (agentope sample --n {more}) to firm up propensities"
        )
