import random

import pytest

from agentope import DataError, load_decisions
from agentope.estimators import bootstrap_difference_ci, effective_sample_size, ips, snips
from agentope.propensity_model import FeatureEncoder, assign_folds, fit_logging_policy
from agentope.targets import callable_target, load_target_jsonl, resolve_target

from . import sim


def test_ips_snips_ess():
    w, r = [2.0, 0.0, 1.0, 1.0], [1.0, 1.0, 0.0, 1.0]
    assert ips(w, r) == pytest.approx(3 / 4)
    assert snips(w, r) == pytest.approx(3 / 4)
    assert effective_sample_size(w) == pytest.approx(16 / 6)
    assert snips([0.0, 0.0], [1.0, 1.0]) is None
    assert effective_sample_size([0.0]) == 0.0


def test_bootstrap_is_deterministic_and_clustered():
    rng = random.Random(1)
    w = [rng.random() * 2 for _ in range(200)]
    r = [float(rng.random() < 0.5) for _ in range(200)]
    clusters = [f"c{i // 2}" for i in range(200)]
    a = bootstrap_difference_ci(w, r, clusters, 500, seed=3)
    b = bootstrap_difference_ci(w, r, clusters, 500, seed=3)
    c = bootstrap_difference_ci(w, r, clusters, 500, seed=4)
    assert a == b and a != c
    (lo, hi), undefined = a
    assert lo < hi and undefined == 0


def test_feature_encoder():
    enc = FeatureEncoder(
        [
            {"intent": "a", "pro": True, "turn": 1, "const": 5},
            {"intent": "b", "pro": False, "turn": 3, "const": 5},
            {"intent": "a", "pro": None, "turn": 2, "const": 5},
        ]
    )
    assert enc.feature_keys == ["intent", "pro", "turn"]  # const dropped
    assert enc.n_features == 2 + 1 + 1 + 1  # intent one-hot, pro, pro-null, turn
    # unseen category → no feature; a missing key counts as null
    assert enc.encode({"intent": "zzz"}) == ((3, 1.0),)


def test_folds_keep_join_keys_together():
    keys = ["a", "a", "b", "c", "c", "d"]
    folds = assign_folds(keys, 3, seed=0)
    assert folds[0] == folds[1] and folds[3] == folds[4]
    assert assign_folds(["x", "x"], 5, 0) == [0, 0]


def test_logit_recovers_logging_policy():
    decisions = load_decisions(sim.simulate(6000, seed=11, mode="unlogged")[0])
    result = fit_logging_policy(decisions, folds=5, seed=0)
    assert result.converged and result.folds == 5
    errors = [
        abs(result.distributions[i][a] - sim.logging_policy(d.context, sim.ACTIONS)[a])
        for i, d in enumerate(decisions)
        for a in sim.ACTIONS
    ]
    # The true policy has an intent × pro interaction the additive logit can't represent
    # exactly, so allow some misspecification.
    assert sum(errors) / len(errors) < 0.02
    assert max(errors) < 0.1
    assert result.log_loss < result.baseline_log_loss
    assert result.calibration_error < 0.03


def test_target_validation(tmp_path):
    d = load_decisions([sim.simulate(1, seed=0)[0][0]])[0]
    assert callable_target(lambda c, k: {"search": 1.0}).probs(d)["escalate"] == 0.0
    with pytest.raises(DataError, match="not a candidate"):
        callable_target(lambda c, k: {"teleport": 1.0}).probs(d)
    with pytest.raises(DataError, match="sum to"):
        callable_target(lambda c, k: {"search": 0.5}).probs(d)

    path = tmp_path / "target.jsonl"
    path.write_text('{"decision_id": "d0", "probs": {"search": 0.25, "escalate": 0.75}}\n')
    assert load_target_jsonl(path).probs(d)["escalate"] == 0.75
    other = load_decisions([sim.simulate(2, seed=0)[0][1]])[0]
    with pytest.raises(DataError, match="no target probabilities"):
        load_target_jsonl(path).probs(other)


def test_target_from_file_spec(tmp_path):
    module = tmp_path / "policy.py"
    module.write_text("def always_search(ctx, cands):\n    return {'search': 1.0}\n")
    target = resolve_target(f"{module}:always_search")
    d = load_decisions([sim.simulate(1, seed=0)[0][0]])[0]
    assert target.probs(d)["search"] == 1.0
    assert str(module) in target.files
    with pytest.raises(DataError):
        resolve_target(f"{module}:missing")
