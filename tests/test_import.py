from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

import agentope as ao
from agentope import DataError
from agentope.cli import main

from . import sim
from .otlp import Builder, genai, traces_from_simulation

CONTEXT = "intent=app.intent,pro=app.pro"


def run_eval(decisions, outcomes, **kw):
    kw.setdefault("horizon", "1d")
    kw.setdefault("target", sim.best_action_target)
    kw.setdefault("n_bootstrap", 300)
    return ao.evaluate(decisions, outcomes=outcomes, **kw)


@pytest.mark.parametrize("mode", ["explore", "logged", "unlogged"])
def test_import_then_eval_matches_direct_eval(tmp_path, mode):
    decisions, outcomes = sim.simulate(1500, seed=21, mode=mode, epsilon=0.3)
    path = traces_from_simulation(decisions).write(tmp_path / "traces.jsonl")
    imported = ao.import_traces(path, context=CONTEXT)

    assert len(imported) == len(decisions)
    assert imported.summary.n_traces == len(decisions)
    by_key = {r["join_key"]: r for r in imported}
    for d in decisions:
        r = by_key[d["join_key"]]
        assert r["chosen"] == d["chosen"]
        assert r["context"] == d["context"]
        assert r["t"] == pytest.approx(d["t"] + 0.01)

    kw = {"accept_unverifiable": True} if mode == "unlogged" else {}
    direct, via_traces = run_eval(decisions, outcomes, **kw), run_eval(imported, outcomes, **kw)
    assert via_traces.level == direct.level
    assert via_traces.estimates["snips"] == pytest.approx(direct.estimates["snips"])
    assert via_traces.ci95 == pytest.approx(direct.ci95)
    assert via_traces.diagnostics["n"] == direct.diagnostics["n"]
    assert str(path) in via_traces.inputs["files"]
    if mode == "unlogged":
        assert any("inferred" in a for a in via_traces.assumptions)


def test_summary_text(tmp_path):
    decisions, _ = sim.simulate(400, seed=3, mode="explore", epsilon=0.25)
    path = traces_from_simulation(decisions).write(tmp_path / "t.jsonl.gz", gz=True)
    imported = ao.import_traces(path, context=CONTEXT + ",region=app.region")
    text = imported.summary.render("decisions.jsonl")
    explored = sum(1 for d in decisions if d.get("explored"))
    none = sum(1 for d in decisions if d["chosen"] == "__none__")
    assert "t.jsonl.gz · 400 traces" in text
    assert f"{400 - none:,} from execute_tool spans · {none:,} __none__ (no tool call)" in text
    assert f"{explored:,} explored · {400 - explored:,} without" in text
    assert "region missing on 400" in text
    assert "none (content capture off) → Levels 1 and 3 available" in text
    assert text.endswith("wrote decisions.jsonl")


def test_span_attributes_round_trip(tmp_path):
    rng = random.Random(0)
    b = Builder()
    for i in range(200):
        trace = f"{i + 1:032x}"
        attrs = genai("chat", **{"gen_ai.conversation.id": f"c{i}", "app.tier": "pro"})
        ao.explore(
            "tool_choice",
            "escalate",
            ["search", "__none__"],
            0.5,
            join_key=f"c{i}",
            candidates=["search", "escalate", "__none__"],
            rng=rng,
            log=lambda r, a=attrs: a.update(ao.span_attributes(r)),
        )
        b.span(trace, "chat m", 1000.0 + i, attrs)
    imported = ao.import_traces(b.write(tmp_path / "t.json", per_trace_lines=False))
    explored = [r for r in imported if r.get("explored")]
    assert 70 < len(explored) < 130
    assert all(r["propensity"] == 0.5 and r["chosen"] in {"search", "__none__"} for r in explored)
    assert all(r["candidates"] == ["search", "escalate", "__none__"] for r in imported)
    assert imported.summary.chosen_from["agentope.chosen"] == len(imported)
    assert all(not r["decision_id"].startswith("0000") for r in imported)  # explore's id kept


def test_content_capture_genai(tmp_path):
    b = Builder()
    tools = [
        {"type": "function", "name": "lookup_order", "parameters": {"type": "object"}},
        {"type": "function", "name": "search_kb"},
    ]
    b.span(
        "a" * 32,
        "chat m",
        50.0,
        genai(
            "chat",
            **{
                "gen_ai.request.model": "qwen2.5-7b-instruct",
                "gen_ai.request.temperature": 0.2,
                "gen_ai.conversation.id": "conv-1",
                "gen_ai.system_instructions": json.dumps([{"type": "text", "content": "Be kind."}]),
                "gen_ai.input.messages": json.dumps(
                    [{"role": "user", "parts": [{"type": "text", "content": "Where is #123?"}]}]
                ),
                "gen_ai.output.messages": json.dumps(
                    [
                        {
                            "role": "assistant",
                            "parts": [
                                {
                                    "type": "tool_call",
                                    "id": "call_1",
                                    "name": "lookup_order",
                                    "arguments": {"order_id": "123"},
                                }
                            ],
                        }
                    ]
                ),
                "gen_ai.tool.definitions": json.dumps(tools),
            },
        ),
    )
    path = b.write(tmp_path / "t.jsonl")
    imported = ao.import_traces(path, inputs_dir=tmp_path / "inputs", inputs_base=tmp_path)
    (r,) = imported
    assert r["chosen"] == "lookup_order"
    assert r["candidates"] == ["lookup_order", "search_kb", "__none__"]
    assert r["candidates_source"] == "tool definitions"
    assert r["input_ref"] == "inputs/" + r["decision_id"].replace(":", "_") + ".json"
    body = json.loads((tmp_path / r["input_ref"]).read_text())
    assert body["model"] == "qwen2.5-7b-instruct" and body["temperature"] == 0.2
    assert body["messages"] == [
        {"role": "system", "content": "Be kind."},
        {"role": "user", "content": "Where is #123?"},
    ]
    assert body["tools"][0] == {
        "type": "function",
        "function": {"name": "lookup_order", "parameters": {"type": "object"}},
    }
    assert imported.summary.chosen_from == {"response content": 1}
    assert imported.summary.stored_inputs == 1
    assert "Level 2 after agentope sample" in imported.summary.render()

    with_args = ao.import_traces(path, action_map="tool+args:order_id")
    assert with_args[0]["chosen"] == 'lookup_order(order_id="123")'
    assert with_args[0]["candidates_source"] == "inferred"


def test_openinference(tmp_path):
    b = Builder()
    trace = "b" * 32
    agent = b.span(trace, "agent", 10.0, {"openinference.span.kind": "AGENT", "session.id": "s-9"})
    b.span(
        trace,
        "ChatCompletion",
        10.1,
        {
            "openinference.span.kind": "LLM",
            "llm.model_name": "llama-3.1-8b-instruct",
            "llm.invocation_parameters": json.dumps({"temperature": 0.5}),
            "llm.input_messages.0.message.role": "user",
            "llm.input_messages.0.message.content": "refund please",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.tool_calls.0.tool_call.function.name": "refund",
            "llm.output_messages.0.message.tool_calls.0.tool_call.function.arguments": "{}",
            "llm.tools.0.tool.json_schema": json.dumps(
                {"type": "function", "function": {"name": "refund"}}
            ),
            "llm.tools.1.tool.json_schema": json.dumps(
                {"type": "function", "function": {"name": "search"}}
            ),
        },
        parent=agent,
    )
    b.span(trace, "refund", 10.2, {"openinference.span.kind": "TOOL", "tool.name": "refund"}, agent)
    (r,) = ao.import_traces(b.write(tmp_path / "t.jsonl"), inputs_dir=tmp_path / "in")
    assert r["chosen"] == "refund" and r["join_key"] == "s-9"
    assert r["candidates"] == ["refund", "search", "__none__"]
    assert r["logging_config"] == {"model": "llama-3.1-8b-instruct", "temperature": 0.5}
    body = json.loads(Path(r["input_ref"]).read_text())
    assert body["messages"] == [{"role": "user", "content": "refund please"}]


def test_first_vs_all_and_parallel_calls(tmp_path):
    b = Builder()
    trace = "c" * 32
    agent = b.span(trace, "invoke_agent a", 0.0, genai("invoke_agent"))
    b.span(trace, "chat m", 1.0, genai("chat"), agent)
    b.span(
        trace,
        "execute_tool search",
        2.0,
        genai("execute_tool", **{"gen_ai.tool.name": "search"}),
        agent,
    )
    b.span(
        trace,
        "execute_tool lookup",
        2.1,
        genai("execute_tool", **{"gen_ai.tool.name": "lookup"}),
        agent,
    )
    b.span(trace, "chat m", 3.0, genai("chat"), agent)
    path = b.write(tmp_path / "t.jsonl")

    first = ao.import_traces(path)
    assert [r["chosen"] for r in first] == ["search"]
    assert first.summary.parallel == 1
    assert "consider --map toolset" in first.summary.render()

    every = ao.import_traces(path, decisions="all", action_map="toolset")
    assert [r["chosen"] for r in every] == ["lookup+search", "__none__"]
    assert [r["context"]["llm_call_index"] for r in every] == [0, 1]
    assert every[0]["join_key"] == trace  # no conversation id → trace id


def test_requested_tool_that_never_ran(tmp_path):
    b = Builder()
    b.span(
        "d" * 32, "chat m", 0.0, genai("chat", **{"gen_ai.response.finish_reasons": ["tool_calls"]})
    )
    b.span("e" * 32, "execute_tool x", 0.0, genai("execute_tool", **{"gen_ai.tool.name": "x"}))
    imported = ao.import_traces(b.write(tmp_path / "t.jsonl"))
    assert imported[0]["chosen"] == "__none__"
    assert imported.summary.requested_not_run == 1


def test_undecidable_spans_are_skipped(tmp_path):
    b = Builder()
    b.span("f" * 32, "chat m", 0.0, genai("chat"))
    b.span(
        "1" * 32, "chat m", 1.0, genai("chat", **{"gen_ai.response.finish_reasons": ["tool_calls"]})
    )
    b.span("2" * 32, "chat m", 2.0, genai("chat", **{"gen_ai.response.finish_reasons": ["stop"]}))
    imported = ao.import_traces(b.write(tmp_path / "t.jsonl"))
    assert [r["chosen"] for r in imported] == ["__none__"]
    assert sum(imported.summary.skipped.values()) == 2
    assert "skipped 1: a tool was called but its name was not recorded" in imported.summary.render()


def test_context_lookup_and_bad_files(tmp_path):
    b = Builder(resource={"service.name": "svc", "deployment.region": "eu"})
    agent = b.span("9" * 32, "invoke_agent", 0.0, genai("invoke_agent", **{"app.tier": "pro"}))
    b.span(
        "9" * 32, "chat", 1.0, genai("chat", **{"gen_ai.response.finish_reasons": ["stop"]}), agent
    )
    (r,) = ao.import_traces(
        b.write(tmp_path / "t.jsonl"), context={"tier": "app.tier", "region": "deployment.region"}
    )
    assert r["context"] == {"tier": "pro", "region": "eu"}

    bad = tmp_path / "bad.json"
    bad.write_text('{"spans": []}')
    with pytest.raises(DataError, match="no resourceSpans"):
        ao.import_traces(bad)
    with pytest.raises(DataError, match="name=attribute"):
        ao.import_traces(tmp_path / "t.jsonl", context="=x")


def test_cli_import_and_eval_from_traces(tmp_path, capsys):
    decisions, outcomes = sim.simulate(800, seed=5, mode="explore", epsilon=0.3)
    traces = traces_from_simulation(decisions).write(tmp_path / "traces.jsonl")
    o_path = tmp_path / "o.jsonl"
    o_path.write_text("".join(json.dumps(o) + "\n" for o in outcomes))
    out = tmp_path / "decisions.jsonl"

    assert main(["import", "--traces", str(traces), "--context", CONTEXT, "-o", str(out)]) == 0
    assert "800 decisions" in capsys.readouterr().out
    assert len(ao.load_decisions(out)) == 800

    common = [
        "--outcomes",
        str(o_path),
        "--horizon",
        "1d",
        "--target",
        "tests.sim:best_action_target",
        "--bootstrap",
        "200",
    ]
    assert main(["eval", str(out), *common]) == 0
    from_file = capsys.readouterr().out
    assert main(["eval", "--traces", str(traces), "--context", CONTEXT, *common]) == 0
    captured = capsys.readouterr()
    assert "800 traces" in captured.err
    assert captured.out.split("Difference")[1] == from_file.split("Difference")[1]

    with pytest.raises(SystemExit) as exc:
        main(["eval", str(out), "--traces", str(traces), *common])
    assert exc.value.code == 2


def test_absent_means_default():
    decisions, outcomes = sim.simulate(3000, seed=8)
    successes = [o for o in outcomes if o["value"] == 1.0]
    strict = run_eval(decisions, successes)
    assert strict.diagnostics["expired_share"] > 0.2 and strict.verdict != "ok"
    assert any("--absent-means-default" in h for h in strict.how_to_improve)

    lenient = run_eval(decisions, successes, absent_means_default=True)
    assert lenient.verdict == "ok"
    assert any("absence is recorded as the outcome" in a for a in lenient.assumptions)
    assert "none recorded" in str(lenient)
    # Same numbers: explicit zeros and absent outcomes mean the same thing here.
    assert lenient.estimates["snips"] == pytest.approx(
        run_eval(decisions, outcomes).estimates["snips"]
    )
