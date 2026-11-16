from __future__ import annotations

import io
import json
import os
import random
from pathlib import Path

import pytest

import agentope as ao
from agentope import DataError, RefusedError
from agentope.cli import main

from . import sim

GOLDEN = Path(__file__).parent / "golden"


def run(decisions, outcomes, **kw):
    kw.setdefault("horizon", "1d")
    kw.setdefault("target", sim.best_action_target)
    kw.setdefault("n_bootstrap", 400)
    return ao.evaluate(decisions, outcomes=outcomes, **kw)


def true_difference(target=sim.best_action_target):
    return sim.true_value(target) - sim.true_value(sim.logging_policy)


def test_level1_logged_recovers_truth():
    decisions, outcomes = sim.simulate(5000, seed=1)
    report = run(decisions, outcomes)
    assert report.level == 1 and report.verdict == "ok"
    assert report.diagnostics["support_check"] == "exact"
    assert report.estimates["snips"] == pytest.approx(
        sim.true_value(sim.best_action_target), abs=0.03
    )
    lo, hi = report.ci95
    assert lo <= true_difference() <= hi


def test_level1_exploration_uses_only_explored_rounds():
    decisions, outcomes = sim.simulate(8000, seed=2, mode="explore", epsilon=0.25)
    report = run(decisions, outcomes)
    explored = sum(1 for d in decisions if d.get("explored"))
    assert report.diagnostics["n"] == explored
    assert report.diagnostics["n_excluded"] == len(decisions) - explored
    assert report.level_detail == "ε-exploration"
    assert report.diagnostics["min_propensity"] == 0.25
    assert report.diagnostics["n_logging_mean"] == len(decisions)

    # The policy that ran is the mix (1-ε)·logging + ε·uniform; the baseline is its value.
    def uniform(c, k):
        return dict.fromkeys(sim.ACTIONS, 0.25)

    mix = 0.75 * sim.true_value(sim.logging_policy) + 0.25 * sim.true_value(uniform)
    lo, hi = report.ci95
    assert lo <= sim.true_value(sim.best_action_target) - mix <= hi
    assert report.estimates["logging_mean"] == pytest.approx(mix, abs=0.02)
    assert any("excluded" in w for w in report.warnings)
    # Exploration rounds are context-independent, so no representativeness assumption.
    assert not any("representative" in a for a in report.assumptions)


def test_level3_needs_acceptance_and_recovers_truth():
    decisions, outcomes = sim.simulate(5000, seed=3, mode="unlogged")
    with pytest.raises(RefusedError, match="cannot be checked"):
        run(decisions, outcomes)
    report = run(decisions, outcomes, accept_unverifiable=True)
    assert report.level == 3 and report.verdict == "weak"
    assert report.diagnostics["propensity_model"]["context_features"] == ["intent", "pro"]
    lo, hi = report.ci95
    assert lo <= true_difference() <= hi
    assert any("agentope.explore" in h for h in report.how_to_improve)


def test_level3_with_empty_context_warns():
    decisions, outcomes = sim.simulate(500, seed=4, mode="unlogged")
    for d in decisions:
        d["context"] = {}
    report = run(
        decisions, outcomes, accept_unverifiable=True, target=lambda c, k: {"lookup_order": 1.0}
    )
    assert any("no usable features" in w for w in report.warnings)
    assert report.diagnostics["propensity_model"]["context_features"] == []


def test_requested_level_without_data_is_refused():
    decisions, outcomes = sim.simulate(50, seed=5, mode="unlogged")
    with pytest.raises(RefusedError, match="no decision has a logged propensity"):
        run(decisions, outcomes, level=1)
    with pytest.raises(RefusedError, match="agentope sample"):
        run(decisions, outcomes, level=2)
    with pytest.raises(DataError, match="v0.4"):
        run(decisions, outcomes, level=4)


def test_support_violation_makes_result_unreliable():
    decisions, outcomes = sim.simulate(3000, seed=6, mode="explore", epsilon=0.3)
    for d in decisions:
        d["safe_candidates"] = ["search", "lookup_order", "__none__"]
        if d.get("explored") and d["chosen"] == "escalate":
            d["chosen"] = "search"
    report = run(decisions, outcomes, target=lambda c, k: {"escalate": 0.5, "search": 0.5})
    assert report.diagnostics["support_violation_mass"] == pytest.approx(0.5)
    assert report.verdict == "unreliable"
    assert not report.estimates["trustworthy"]
    assert "no trustworthy estimate" in str(report)


def test_target_that_never_agrees():
    decisions, outcomes = sim.simulate(200, seed=7)
    for d in decisions:
        d["chosen"] = "search"
        d["logging_probs"] = {"search": 1.0}
        d["propensity"] = 1.0
    report = run(decisions, outcomes, target=lambda c, k: {"escalate": 1.0})
    assert report.estimates["snips"] is None and report.verdict == "unreliable"
    assert any("deterministic" in w for w in report.warnings)


def test_coverage_of_interval():
    true_diff = true_difference()
    hits = 0
    reps = 120
    for seed in range(reps):
        decisions, outcomes = sim.simulate(400, seed=1000 + seed)
        lo, hi = run(decisions, outcomes, n_bootstrap=300, seed=seed).ci95
        hits += lo <= true_diff <= hi
    assert 0.88 <= hits / reps <= 0.995


def test_shared_join_keys_and_expiry():
    decisions, outcomes = sim.simulate(400, seed=8)
    for i, d in enumerate(decisions):
        d["join_key"] = f"conv-{i // 2}"
    report = run(decisions, outcomes, horizon="1h")  # outcomes arrive after 12h
    assert report.diagnostics["shared_join_key_decisions"] == 400
    assert report.diagnostics["expired_share"] == 1.0
    assert report.verdict == "unreliable"
    assert any("join key" in a for a in report.assumptions)


def test_several_decision_points_need_a_choice():
    decisions, outcomes = sim.simulate(100, seed=9)
    decisions[0]["decision_point"] = "router"
    with pytest.raises(DataError, match="several decision points"):
        run(decisions, outcomes)
    assert run(decisions[1:], outcomes, decision_point="tool_choice").diagnostics["n"] == 99


def test_report_json_is_deterministic(tmp_path):
    decisions, outcomes = sim.simulate(800, seed=10, mode="unlogged")
    d_path, o_path = tmp_path / "d.jsonl", tmp_path / "o.jsonl"
    d_path.write_text("".join(json.dumps(d) + "\n" for d in decisions))
    o_path.write_text("".join(json.dumps(o) + "\n" for o in outcomes))
    kw = {"accept_unverifiable": True, "target": "tests.sim:best_action_target"}
    first = run(d_path, o_path, **kw).to_json()
    second = run(d_path, o_path, **kw).to_json()
    assert first == second
    parsed = json.loads(first)
    assert set(parsed) >= {
        "level",
        "estimates",
        "diagnostics",
        "verdict",
        "assumptions",
        "how_to_improve",
        "inputs",
    }
    assert set(parsed["inputs"]["files"]) == {str(d_path), str(o_path)}


def test_helpers_produce_level1_logs(tmp_path):
    log = tmp_path / "decisions.jsonl"
    rng = random.Random(0)
    outcomes = []
    for i in range(3000):
        ctx = {"intent": rng.choice(sim.INTENTS), "pro": rng.random() < sim.P_PRO}
        if i % 2:
            chosen = ao.randomize(
                "tool_choice",
                sim.ACTIONS,
                [0.4, 0.3, 0.2, 0.1],
                context=ctx,
                join_key=f"c{i}",
                log=log,
                t=float(i),
                rng=rng,
                decision_id=f"r{i}",
            )
        else:
            llm = max(sim.ACTIONS, key=lambda a: sim.q(ctx, a))
            chosen = ao.explore(
                "tool_choice",
                llm,
                safe_candidates=sim.ACTIONS,
                epsilon=0.3,
                context=ctx,
                join_key=f"c{i}",
                log=log,
                t=float(i),
                rng=rng,
                decision_id=f"e{i}",
            )
        value = 1 if rng.random() < sim.q(ctx, chosen) else 0
        outcomes.append({"join_key": f"c{i}", "t": float(i), "value": value})

    decisions = ao.load_decisions(log)
    explored = [d for d in decisions if d.explored]
    randomized = [d for d in decisions if d.decision_id.startswith("r")]
    assert 0.25 < len(explored) / 1500 < 0.35
    assert all(d.propensity == 0.25 for d in explored)
    assert all(d.logging_probs is not None for d in randomized)
    assert sum(d.chosen == "search" for d in randomized) / 1500 == pytest.approx(0.4, abs=0.04)

    report = run(log, outcomes)
    assert report.level_detail == "logged, incl. ε-exploration"
    assert report.diagnostics["support_check"] == "exact"


def test_explore_never_leaves_safe_candidates():
    buf = io.StringIO()
    rng = random.Random(1)
    for i in range(500):
        choice = ao.explore(
            "tool_choice",
            "escalate",
            ["search", "__none__"],
            1.0,
            join_key=str(i),
            log=buf,
            rng=rng,
        )
        assert choice in {"search", "__none__"}
    records = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert records[0]["candidates"] == ["search", "__none__", "escalate"]
    with pytest.raises(DataError):
        ao.explore("tool_choice", "a", ["b"], 1.5, join_key="k", log=buf)


def test_cli_exit_codes_and_output(tmp_path, capsys):
    decisions, outcomes = sim.simulate(600, seed=12, mode="unlogged")
    d_path, o_path = tmp_path / "d.jsonl", tmp_path / "o.csv"
    d_path.write_text("".join(json.dumps(d) + "\n" for d in decisions))
    o_path.write_text(
        "join_key,t,value\n" + "".join(f"{o['join_key']},{o['t']},{o['value']}\n" for o in outcomes)
    )
    base = [
        str(d_path),
        "--outcomes",
        str(o_path),
        "--horizon",
        "1d",
        "--target",
        "tests.sim:best_action_target",
        "--bootstrap",
        "200",
    ]

    assert main(["eval", *base]) == 1
    assert "--accept-unverifiable" in capsys.readouterr().err

    out_json = tmp_path / "report.json"
    assert main(["eval", *base, "--accept-unverifiable", "-o", str(out_json)]) == 0
    text = capsys.readouterr().out
    assert "L3 Estimated" in text and "This estimate assumes:" in text
    assert json.loads(out_json.read_text())["level"]["level"] == 3

    assert main(["eval", *base, "--horizon", "soon"]) == 2
    assert "invalid duration" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        main(["eval", str(d_path)])
    assert exc.value.code == 2


def test_golden_text_report():
    decisions, outcomes = sim.simulate(1500, seed=13, mode="explore", epsilon=0.3)
    text = str(run(decisions, outcomes, target=sim.best_action_target)) + "\n"
    path = GOLDEN / "report_explore.txt"
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    assert text == path.read_text()
