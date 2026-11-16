"""Run the support-agent example end to end.

    uv run python examples/support_agent/run.py

Two scenarios from the same simulated world, each in its own folder under runs/:

- sampled: the agent is unchanged and its traces include the messages. agentope asks
  the model again (a local stand-in for the model server) to learn how likely each
  choice was: Level 2. This is the landing page's example.
- explored: the agent lets 10% of conversations try a random safe option: Level 1.
  This is the docs' worked example.

Every command and its output is saved to site/src/content/example/, which the website
shows as-is, together with the true answers (known because the world is simulated).
"""

import contextlib
import gzip
import io
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[1] / "site" / "src" / "content" / "example"
sys.path.insert(0, str(HERE))

import policies  # noqa: E402
import world  # noqa: E402
from model_server import serve  # noqa: E402
from simulate import CONVERSATIONS, DAYS, EPSILON, MODEL, simulate  # noqa: E402

from agentope.cli import main  # noqa: E402

CONTEXT = "intent=app.intent,has_order_number=app.has_order_number,customer_tier=app.customer_tier"
SHOWN_BASE_URL = "http://localhost:8000/v1"


def agentope(
    display: str,
    extra: list[str] | None = None,
    *,
    expect: int = 0,
    base_url: str | None = None,
) -> dict:
    """Run one CLI command (as shown on the site) and capture what it prints."""
    argv = shlex.split(display.replace("\\\n", " "))[1:]
    if base_url:
        argv = [base_url if a == SHOWN_BASE_URL else a for a in argv]
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv + (extra or []))
    if code != expect:
        raise SystemExit(f"{display!r} exited {code}:\n{err.getvalue()}")
    text = out.getvalue() if expect == 0 else err.getvalue()
    return {"command": display, "output": text.rstrip("\n")}


def resolved_by_conversation() -> dict[str, bool]:
    with open("helpdesk.csv") as f:
        next(f)
        return {key: value == "1" for key, _, value in (line.strip().split(",") for line in f)}


def rule_action(d: dict) -> str:
    return next(iter(policies.lookup_when_order_number(d["context"], d["candidates"])))


def row(d: dict, resolved: dict[str, bool], **extra) -> dict:
    return {
        "conversation": d["join_key"],
        "intent": d["context"]["intent"],
        "has_order_number": d["context"]["has_order_number"],
        "agent_did": d["chosen"],
        "rule_would": rule_action(d),
        "resolved": resolved[d["join_key"]],
        **extra,
    }


def truths(running: float) -> dict:
    t = {
        "running": running,
        "lookup_when_order_number": world.value(policies.lookup_when_order_number),
        "escalate_pro": world.value(policies.escalate_pro),
    }
    t["lookup_difference"] = t["lookup_when_order_number"] - running
    t["escalate_difference"] = t["escalate_pro"] - running
    return t


def meta() -> dict:
    return {
        "conversations": CONVERSATIONS,
        "days": DAYS,
        "epsilon": EPSILON,
        "model": MODEL,
        "safe_candidates": world.SAFE,
        "actions": world.ACTIONS,
    }


def run_dir(name: str) -> Path:
    path = HERE / "runs" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    shutil.copy(HERE / "policies.py", path / "policies.py")
    os.chdir(path)
    return path


# ── Scenario 1: traces with messages, no exploration (Level 2) ─────────────


def sampled() -> dict:
    path = run_dir("sampled")
    print("sampled: simulating two weeks of traces …", file=sys.stderr)
    simulate(path, explore=False, capture_content=True)
    steps = {
        "check": agentope(
            f"agentope check --traces traces.otlp.json.gz --n 64 \\\n    --context {CONTEXT}"
        ),
        "import": agentope(
            f"agentope import --traces traces.otlp.json.gz \\\n    --context {CONTEXT} \\\n"
            "    -o decisions.jsonl"
        ),
    }
    print("sampled: asking the model again …", file=sys.stderr)
    with serve() as base_url:
        steps["sample"] = agentope(
            "agentope sample decisions.jsonl -o samples.jsonl --n 64 --n-per-request 64 \\\n"
            f"    --base-url {SHOWN_BASE_URL} --yes",
            base_url=base_url,
        )
    steps["eval"] = agentope(
        "agentope eval decisions.jsonl --samples samples.jsonl \\\n"
        "    --outcomes helpdesk.csv --horizon 3d --target policies.py:lookup_when_order_number",
        ["-o", "report-lookup.json"],
    )
    # The same question from logged context alone (Level 3), as if the traces had no
    # messages: it only runs with explicit acceptance of its untestable assumption.
    steps["estimated"] = agentope(
        "agentope eval decisions.jsonl --level 3 --accept-unverifiable \\\n"
        "    --outcomes helpdesk.csv --horizon 3d --target policies.py:lookup_when_order_number",
        ["-o", "report-estimated.json"],
    )
    # Without the samples or that acceptance, agentope refuses.
    steps["refused"] = agentope(
        "agentope eval decisions.jsonl \\\n"
        "    --outcomes helpdesk.csv --horizon 3d --target policies.py:lookup_when_order_number",
        expect=1,
    )

    resolved = resolved_by_conversation()
    samples = {}
    with open("samples.jsonl") as f:
        for line in f:
            s = json.loads(line)
            samples[s["decision_id"]] = s
    rows = []
    matched = total = 0
    with open("decisions.jsonl") as f:
        for line in f:
            d = json.loads(line)
            total += 1
            matched += d["chosen"] == rule_action(d)
            if len(rows) < 8:
                s = samples[d["decision_id"]]
                rows.append(
                    row(d, resolved, model_picks=s["counts"].get(d["chosen"], 0), n=s["n"])
                )

    return {
        "meta": meta(),
        "steps": steps,
        "report": json.loads(Path("report-lookup.json").read_text()),
        "estimated": json.loads(Path("report-estimated.json").read_text()),
        "truth": truths(world.value(lambda ctx, cands: world.model_policy(ctx))),
        "picture": {"rows": rows, "total": total, "matched": matched},
    }


# ── Scenario 2: a little exploration (Level 1) ──────────────────────────────


def sample_trace() -> dict:
    """The first explored conversation, for the "what the traces contain" step."""
    with gzip.open("traces.otlp.json.gz", "rt") as f:
        for line in f:
            spans = json.loads(line)["resourceSpans"][0]["scopeSpans"][0]["spans"]
            chat = spans[1]
            attrs = {a["key"]: a["value"] for a in chat["attributes"]}
            if attrs.get("agentope.explored", {}).get("boolValue") and len(spans) == 4:
                break
    keep = [
        "gen_ai.operation.name",
        "gen_ai.request.model",
        "gen_ai.request.temperature",
        "gen_ai.response.finish_reasons",
        "agentope.decision_id",
        "agentope.explored",
        "agentope.propensity",
        "agentope.llm_choice",
        "agentope.chosen",
        "agentope.safe_candidates",
    ]
    trimmed = {k: v for k, v in chat.items() if k not in ("attributes", "endTimeUnixNano")}
    trimmed["attributes"] = [a for a in chat["attributes"] if a["key"] in keep]

    def attr(span, key):
        for a in span["attributes"]:
            if a["key"] == key:
                return next(iter(a["value"].values()))
        return None

    root = spans[0]
    return {
        "span": trimmed,
        "llm_choice": attr(spans[1], "agentope.llm_choice"),
        "chosen": attr(spans[1], "agentope.chosen"),
        "tree": [
            {
                "name": root["name"],
                "notes": [
                    f"gen_ai.conversation.id={attr(root, 'gen_ai.conversation.id')}",
                    f"app.intent={attr(root, 'app.intent')} · "
                    f"app.has_order_number={str(attr(root, 'app.has_order_number')).lower()} · "
                    f"app.customer_tier={attr(root, 'app.customer_tier')}",
                ],
            },
            {
                "name": spans[1]["name"],
                "role": "the decision",
                "notes": [
                    f"model wanted {attr(spans[1], 'agentope.llm_choice')} · "
                    f"agentope.explored=true · agentope.propensity="
                    f"{attr(spans[1], 'agentope.propensity'):.3f}",
                ],
            },
            {"name": spans[2]["name"], "role": "what ran", "notes": []},
            {"name": spans[3]["name"], "role": "final answer", "notes": []},
        ],
    }


def explored() -> dict:
    path = run_dir("explored")
    print("explored: simulating two weeks of traces …", file=sys.stderr)
    simulate(path, explore=True, capture_content=False)
    steps = {
        "check": agentope(f"agentope check --traces traces.otlp.json.gz \\\n    --context {CONTEXT}"),
        "import": agentope(
            f"agentope import --traces traces.otlp.json.gz \\\n    --context {CONTEXT} \\\n"
            "    -o decisions.jsonl"
        ),
        "eval": agentope(
            "agentope eval decisions.jsonl --outcomes helpdesk.csv --horizon 3d \\\n"
            "    --target policies.py:lookup_when_order_number",
            ["-o", "report-lookup.json"],
        ),
        "refused": agentope(
            "agentope eval decisions.jsonl --outcomes helpdesk.csv --horizon 3d \\\n"
            "    --target policies.py:escalate_pro",
            ["-o", "report-escalate.json"],
        ),
    }
    resolved = resolved_by_conversation()
    rows = []
    total = matched = 0
    with open("decisions.jsonl") as f:
        for line in f:
            d = json.loads(line)
            if not d.get("explored"):
                continue
            total += 1
            matched += d["chosen"] == rule_action(d)
            if len(rows) < 8:
                rows.append(row(d, resolved))
    return {
        "meta": meta(),
        "steps": steps,
        "report": json.loads(Path("report-lookup.json").read_text()),
        "refused": json.loads(Path("report-escalate.json").read_text()),
        "truth": truths(world.value(world.deployed(EPSILON))),
        "trace": sample_trace(),
        "policies": (HERE / "policies.py").read_text(),
        "outcomes_head": Path("helpdesk.csv").read_text().splitlines()[:4],
        "picture": {"rows": rows, "total": total, "matched": matched},
    }


def write(name: str, data: dict) -> None:
    (SITE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    r = data["report"]
    lo, hi = r["estimates"]["ci95"]
    print(
        f"{name}: L{r['level']['level']} difference {r['estimates']['difference']:+.3f} "
        f"[{lo:+.3f}, {hi:+.3f}] · true {data['truth']['lookup_difference']:+.3f} · "
        f"verdict {r['verdict']}",
        file=sys.stderr,
    )


def main_example() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    write("support-agent-sampled.json", sampled())
    write("support-agent.json", explored())
    fence = '```python title="policies.py"\n'
    policies_source = (HERE / "policies.py").read_text().rstrip()
    (SITE / "policies.mdx").write_text(fence + policies_source + "\n```\n")


if __name__ == "__main__":
    main_example()
