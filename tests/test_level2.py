import json
from pathlib import Path

import pytest

import agentope as ao
from agentope import DataError, RefusedError
from agentope.cli import main
from agentope.sampling import load_llm_target

from . import sim
from .mock_llm import MockLLM

FAST = {"backoff": 0.001}


def context_of(body: dict) -> dict:
    user = next(m["content"] for m in body["messages"] if m["role"] == "user")
    fields = dict(part.split("=") for part in user.split())
    return {"intent": fields["intent"], "pro": fields["pro"] == "True"}


def system_of(body: dict) -> str:
    return next((m["content"] for m in body["messages"] if m["role"] == "system"), "")


def uniform(ctx, cands):
    return dict.fromkeys(sim.ACTIONS, 0.25)


def v2_policy(ctx, cands):
    """What the model does with the v2 prompt: mostly the best action."""
    best = sim.best_action_target(ctx, cands)
    return {a: 0.8 * best.get(a, 0.0) + 0.05 for a in sim.ACTIONS}


def llm_policy(body: dict) -> dict[str, float]:
    ctx = context_of(body)
    if system_of(body) == "v2":
        return v2_policy(ctx, sim.ACTIONS)
    return sim.logging_policy(ctx, sim.ACTIONS)


def write_dataset(tmp: Path, n: int, seed: int) -> tuple[Path, list[dict]]:
    """Unlogged decisions (Level 3 data) plus stored inputs, as trace import writes them."""
    decisions, outcomes = sim.simulate(n, seed=seed, mode="unlogged")
    (tmp / "inputs").mkdir()
    for d in decisions:
        body = {
            "model": "qwen2.5-7b-instruct",
            "messages": [
                {"role": "system", "content": "v1"},
                {
                    "role": "user",
                    "content": f"intent={d['context']['intent']} pro={d['context']['pro']}",
                },
            ],
            "tools": [{"type": "function", "function": {"name": a}} for a in sim.ACTIONS[:3]],
            "temperature": 0.7,
        }
        ref = f"inputs/{d['decision_id']}.json"
        (tmp / ref).write_text(json.dumps(body))
        d |= {
            "input_ref": ref,
            "input_sha256": ao.io.canonical_sha256(body),
            "logging_config": {"model": "qwen2.5-7b-instruct", "temperature": 0.7},
        }
    path = tmp / "decisions.jsonl"
    path.write_text("".join(json.dumps(d) + "\n" for d in decisions))
    return path, outcomes


def run_eval(decisions, outcomes, **kw):
    kw.setdefault("horizon", "1d")
    kw.setdefault("n_bootstrap", 400)
    return ao.evaluate(decisions, outcomes=outcomes, **kw)


def test_level2_recovers_truth_for_callable_and_llm_targets(tmp_path):
    decisions, outcomes = write_dataset(tmp_path, 1500, seed=31)
    target_file = tmp_path / "v2.yaml"
    target_file.write_text("type: llm\nname: v2\nsystem_prompt: v2\n")
    samples = tmp_path / "samples.jsonl"
    with MockLLM(llm_policy) as llm:
        summary = ao.sample(
            decisions,
            output=samples,
            n=64,
            n_per_request=64,
            targets=[target_file],
            base_url=llm.base_url,
            endpoint_options=FAST,
        )
        assert llm.requests == 3000
        assert {system_of(b) for b in llm.bodies} == {"v1", "v2"}
    assert summary.written == 3000 and summary.failed_samples == 0

    report = run_eval(decisions, outcomes, target=sim.best_action_target, samples=samples)
    assert report.level == 2 and report.level_detail == "N=64, α=0.5"
    assert report.verdict == "ok"
    s = report.diagnostics["sampling"]
    assert s["reproduction_rate"] > 0.9 and s["input_hash_mismatches"] == 0
    assert s["model_mismatch_share"] == 0
    lo, hi = report.ci95
    true_diff = sim.true_value(sim.best_action_target) - sim.true_value(sim.logging_policy)
    assert lo <= true_diff <= hi
    assert "logged choice reproduced in samples" in str(report)
    assert any("stored inputs are everything" in a for a in report.assumptions)

    llm_report = run_eval(decisions, outcomes, target=target_file, samples=samples)
    assert llm_report.target == "LLM policy v2" and llm_report.level == 2
    lo, hi = llm_report.ci95
    assert lo <= sim.true_value(v2_policy) - sim.true_value(sim.logging_policy) <= hi
    assert str(target_file) in llm_report.inputs["files"]


def test_resume_and_cache_keys(tmp_path):
    decisions, _ = write_dataset(tmp_path, 40, seed=2)
    samples = tmp_path / "samples.jsonl"
    with MockLLM(llm_policy) as llm:
        common = {"output": samples, "base_url": llm.base_url, "endpoint_options": FAST}
        assert ao.sample(decisions, n=4, **common).written == 40
        again = ao.sample(decisions, n=4, **common)
        assert again.written == 0 and again.cached == 40
        assert ao.sample(decisions, n=8, **common).written == 40  # N changed → resample
        assert ao.sample(decisions, n=8, model="other-model", **common).written == 40
    latest = ao.load_samples(samples)
    assert len(latest) == 40 and all(r.n == 8 and r.model == "other-model" for r in latest.values())


def test_retries_and_failures(tmp_path):
    decisions, _ = write_dataset(tmp_path, 10, seed=3)
    with MockLLM(llm_policy, fail_first=3) as llm:
        s = ao.sample(
            decisions,
            output=tmp_path / "a.jsonl",
            n=2,
            base_url=llm.base_url,
            endpoint_options=FAST,
            concurrency=1,
        )
        assert s.failed_samples == 0 and llm.requests == 23
    with MockLLM(llm_policy, fail_first=10**6, fail_status=400) as llm:
        s = ao.sample(
            decisions,
            output=tmp_path / "b.jsonl",
            n=2,
            base_url=llm.base_url,
            endpoint_options=FAST,
        )
        assert s.failed_samples == 20 and "HTTP 400" in s.render("b.jsonl")
    records = ao.load_samples(tmp_path / "b.jsonl")
    assert all(r.valid == 0 and r.failed == 2 for r in records.values())


def test_changed_model_is_flagged(tmp_path):
    decisions, outcomes = write_dataset(tmp_path, 800, seed=4)
    samples = tmp_path / "samples.jsonl"
    with MockLLM(lambda body: {"lookup_order": 1.0}, model="qwen3-8b") as llm:
        ao.sample(
            decisions,
            output=samples,
            n=16,
            n_per_request=16,
            base_url=llm.base_url,
            endpoint_options=FAST,
        )
    report = run_eval(
        decisions, outcomes, target=lambda c, k: {"lookup_order": 1.0}, samples=samples
    )
    s = report.diagnostics["sampling"]
    assert s["reproduction_rate"] < 0.5 and s["deterministic"]
    assert s["model_mismatch_share"] == 1.0
    assert report.verdict != "ok"
    assert any("reproduction" in r or "came up again" in r for r in report.verdict_reasons)
    assert any("different model" in w for w in report.warnings)
    assert any("same answer in every sample" in w for w in report.warnings)


def test_level2_guards_and_selection(tmp_path):
    decisions, outcomes = write_dataset(tmp_path, 50, seed=5)
    with pytest.raises(RefusedError, match="agentope sample"):
        run_eval(decisions, outcomes, target=sim.best_action_target, level=2)
    target_file = tmp_path / "v2.yaml"
    target_file.write_text("type: llm\nsystem_prompt: v2\n")
    assert load_llm_target(target_file).name == "v2"
    with pytest.raises(DataError, match="no samples for LLM target"):
        run_eval(decisions, outcomes, target=target_file, level=3, accept_unverifiable=True)
    bad = tmp_path / "bad.yaml"
    bad.write_text("type: llm\nmessages_hook: x\n")
    with pytest.raises(DataError, match="needs the Python API"):
        load_llm_target(bad)


def test_llm_policy_render_and_overrides():
    stored = {
        "model": "a",
        "messages": [{"role": "system", "content": "old"}, {"role": "user", "content": "hi"}],
    }
    policy = ao.LLMPolicy("p", model="b", system_prompt="new", temperature=0.1)
    body = policy.request(stored)
    assert body["model"] == "b" and body["temperature"] == 0.1
    assert body["messages"][0] == {"role": "system", "content": "new"}
    assert stored["messages"][0]["content"] == "old"  # not mutated
    rendered = ao.LLMPolicy("r", render=lambda b: {**b, "messages": b["messages"][1:]})
    assert rendered.request(stored)["messages"] == [{"role": "user", "content": "hi"}]
    with pytest.raises(DataError):
        ao.LLMPolicy("logging")


def test_check_report(tmp_path):
    decisions, _ = write_dataset(tmp_path, 1500, seed=6)
    text = str(ao.check(decisions, n_samples=32, llm_target=True))
    assert "Level 1 Logged     ✗" in text
    assert (
        "Level 2 Sampled    ✓  stored inputs: 1,500/1,500 · logging model: qwen2.5-7b-instruct"
        in text
    )
    assert "48k calls (logging) + 48k (LLM target)" in text
    assert "Level 3 Estimated  ✓  context has 2 features: intent, pro" in text
    assert "Best available: Level 2" in text

    explored, _ = sim.simulate(200, seed=1, mode="explore")
    report = ao.check(explored)
    assert report.points[0].best == 1
    assert "Without stored inputs" in str(report)


def test_cli_sample_check_eval(tmp_path, capsys, monkeypatch):
    decisions, outcomes = write_dataset(tmp_path, 300, seed=7)
    o_path = tmp_path / "o.jsonl"
    o_path.write_text("".join(json.dumps(o) + "\n" for o in outcomes))
    samples = tmp_path / "samples.jsonl"

    assert main(["check", str(decisions)]) == 0
    assert "Best available: Level 2" in capsys.readouterr().out

    with MockLLM(llm_policy) as llm:
        monkeypatch.setenv("AGENTOPE_BASE_URL", llm.base_url)
        args = ["sample", str(decisions), "-o", str(samples), "--n", "8", "--n-per-request", "8"]
        assert main(args) == 1  # not a terminal and no --yes
        assert "--yes" in capsys.readouterr().err
        assert main([*args, "--yes"]) == 0
        assert "sampled 300 (decision, policy) pairs" in capsys.readouterr().out

    assert (
        main(
            [
                "eval",
                str(decisions),
                "--outcomes",
                str(o_path),
                "--horizon",
                "1d",
                "--target",
                "tests.sim:best_action_target",
                "--samples",
                str(samples),
                "--bootstrap",
                "200",
            ]
        )
        == 0
    )
    assert "L2 Sampled (N=8, α=0.5)" in capsys.readouterr().out


def test_from_traces_with_content_to_level2(tmp_path):
    from .otlp import Builder, genai

    decisions, outcomes = sim.simulate(300, seed=9, mode="unlogged")
    b = Builder()
    for i, d in enumerate(decisions):
        trace = f"{i + 1:032x}"
        user = f"intent={d['context']['intent']} pro={d['context']['pro']}"
        attrs = genai(
            "chat",
            **{
                "gen_ai.conversation.id": d["join_key"],
                "gen_ai.request.model": "qwen2.5-7b-instruct",
                "gen_ai.request.temperature": 0.7,
                "app.intent": d["context"]["intent"],
                "app.pro": d["context"]["pro"],
                "gen_ai.input.messages": json.dumps(
                    [{"role": "user", "parts": [{"type": "text", "content": user}]}]
                ),
                "gen_ai.output.messages": json.dumps(
                    [
                        {
                            "role": "assistant",
                            "parts": (
                                []
                                if d["chosen"] == "__none__"
                                else [
                                    {
                                        "type": "tool_call",
                                        "id": "c",
                                        "name": d["chosen"],
                                        "arguments": {},
                                    }
                                ]
                            ),
                        }
                    ]
                ),
            },
        )
        b.span(trace, "chat qwen2.5-7b-instruct", d["t"], attrs)
    traces = b.write(tmp_path / "traces.jsonl")
    out = tmp_path / "decisions.jsonl"
    assert (
        main(
            [
                "import",
                "--traces",
                str(traces),
                "--context",
                "intent=app.intent,pro=app.pro",
                "-o",
                str(out),
            ]
        )
        == 0
    )
    records = ao.load_decisions(out)
    assert all(r.input_ref and (tmp_path / r.input_ref).exists() for r in records)

    samples = tmp_path / "samples.jsonl"
    with MockLLM(llm_policy) as llm:
        ao.sample(
            out, output=samples, n=8, n_per_request=8, base_url=llm.base_url, endpoint_options=FAST
        )
    report = run_eval(out, outcomes, target=sim.best_action_target, samples=samples)
    assert report.level == 2 and report.diagnostics["sampling"]["input_hash_mismatches"] == 0
