"""The `agentope` command.

Exit codes: 0 report produced · 1 refused (a guard fired, or sampling declined) · 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .checks import check
from .errors import AgentopeError, DataError, RefusedError
from .evaluate import evaluate
from .importer import import_traces, write_decisions
from .sampling import load_samples, plan_sampling, resolve_llm_target, run_sampling


def _add_import_options(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("trace import")
    g.add_argument(
        "--map",
        dest="action_map",
        default=None,
        help="action map: tool (default), toolset, tool+args:<fields>, or module:function",
    )
    g.add_argument(
        "--context",
        help="context features from span attributes, e.g. intent=app.intent,tier=app.tier",
    )
    g.add_argument(
        "--join-key",
        help="attribute holding the outcome key (default: gen_ai.conversation.id, session.id, "
        "then the trace id)",
    )
    g.add_argument(
        "--decisions",
        dest="decisions_mode",
        choices=("first", "all"),
        default="first",
        help="first model call per agent run (default), or every model call",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentope",
        description="Offline evaluation of LLM agent decisions, without logprobs.",
    )
    parser.add_argument("--version", action="version", version=f"agentope {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser(
        "check",
        help="what can be evaluated with this data (no LLM calls, no outcomes)",
        description="Readiness report: which evidence levels the data supports, and what to "
        "log next. Makes no LLM calls and needs no outcomes.",
    )
    c.add_argument("decisions", nargs="?", help="decisions.jsonl")
    c.add_argument("--traces", help="check an OTLP JSON export instead")
    c.add_argument("--decision-point", help="only this decision point")
    c.add_argument("--n", type=int, default=32, help="samples per decision for the cost (32)")
    c.add_argument("--target", help="an LLM target (target.yaml), to include its sampling cost")
    c.add_argument("--json", action="store_true", help="print the report as JSON")
    _add_import_options(c)

    imp = sub.add_parser(
        "import",
        help="turn OTLP JSON traces into decisions.jsonl",
        description="Turn an OTLP JSON trace export (OpenTelemetry GenAI or OpenInference) "
        "into decisions.jsonl.",
    )
    imp.add_argument("--traces", required=True, help="OTLP JSON export (optionally gzipped)")
    imp.add_argument("-o", "--output", required=True, help="decisions.jsonl to write")
    imp.add_argument(
        "--decision-point", default="tool_choice", help="name for the decisions (tool_choice)"
    )
    imp.add_argument(
        "--inputs-dir",
        help="where to write stored model inputs when content was captured "
        "(default: inputs/ next to the output)",
    )
    _add_import_options(imp)

    s = sub.add_parser(
        "sample",
        help="Level 2: sample the logging model (and LLM targets) on stored inputs",
        description="Ask the logging model, and optionally LLM target policies, for N "
        "responses per decision on its stored input. The only step that calls an LLM. "
        "Appends to the output and skips what is already there.",
    )
    s.add_argument("decisions", help="decisions.jsonl with stored inputs (input_ref)")
    s.add_argument("-o", "--output", required=True, help="samples.jsonl (appended to)")
    s.add_argument("--n", type=int, default=32, help="samples per decision and policy (32)")
    s.add_argument(
        "--target",
        action="append",
        default=[],
        help="an LLM target (target.yaml with type: llm) to sample as well; repeatable",
    )
    s.add_argument("--no-logging", action="store_true", help="only sample the targets")
    s.add_argument("--base-url", help="OpenAI-compatible endpoint (or AGENTOPE_BASE_URL)")
    s.add_argument("--model", help="logging model name on this endpoint, if it differs")
    s.add_argument("--concurrency", type=int, default=8, help="parallel requests (8)")
    s.add_argument(
        "--n-per-request",
        type=int,
        default=1,
        help="samples per request via the `n` parameter, if the server supports it (1)",
    )
    s.add_argument("--sample", type=int, dest="subset", help="only a random subset of decisions")
    s.add_argument("--seed", type=int, default=0, help="seed for --sample (0)")
    s.add_argument("--decision-point", help="only this decision point")
    s.add_argument("--yes", action="store_true", help="don't ask before calling the LLM")

    e = sub.add_parser(
        "eval",
        help="estimate how a target policy would have done on logged decisions",
        description="Estimate how a target policy would have done on logged decisions.",
    )
    e.add_argument("decisions", nargs="?", help="decisions.jsonl (optionally gzipped)")
    e.add_argument("--traces", help="evaluate straight from an OTLP JSON export instead")
    e.add_argument("--outcomes", required=True, help="outcomes as JSONL or CSV")
    e.add_argument(
        "--horizon", required=True, help="how long an outcome still counts, e.g. 7d, 12h, 30m"
    )
    e.add_argument(
        "--target",
        required=True,
        help="target.jsonl, an LLM target (target.yaml), or a Python callable as "
        "module:function or path/to/file.py:function",
    )
    e.add_argument("--samples", help="samples.jsonl from `agentope sample` (Level 2, LLM targets)")
    e.add_argument("--alpha", type=float, default=0.5, help="Level 2 smoothing (0.5)")
    e.add_argument("--decision-point", help="required when decisions cover several points")
    e.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3, 4),
        help="evidence level (default: the strongest the data supports)",
    )
    e.add_argument(
        "--accept-unverifiable",
        action="store_true",
        help="accept the untestable no-unmeasured-confounding assumption of Level 3",
    )
    e.add_argument("--default-reward", type=float, default=0.0, help="reward when expired (0)")
    e.add_argument(
        "--absent-means-default",
        action="store_true",
        help="no outcome really means the default reward (e.g. only successes are recorded)",
    )
    e.add_argument("--seed", type=int, default=0, help="seed for the bootstrap and folds (0)")
    e.add_argument("--bootstrap", type=int, default=2000, help="bootstrap resamples (2000)")
    e.add_argument("--folds", type=int, default=5, help="cross-fitting folds at Level 3 (5)")
    e.add_argument("--json", action="store_true", help="print the report as JSON")
    e.add_argument("-o", "--output", help="also write the JSON report to this file")
    _add_import_options(e)
    return parser


def _decisions_source(args: argparse.Namespace, parser: argparse.ArgumentParser) -> object:
    if (args.decisions is None) == (args.traces is None):
        parser.error(f"{args.command} needs either a decisions file or --traces, not both")
    if not args.traces:
        return args.decisions
    imported = import_traces(
        args.traces,
        decision_point=args.decision_point or "tool_choice",
        action_map=args.action_map or "tool",
        context=args.context,
        join_key=args.join_key,
        decisions=args.decisions_mode,
    )
    return imported


def _run_check(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    source = _decisions_source(args, parser)
    llm_target = resolve_llm_target(args.target) is not None if args.target else False
    if args.target and not llm_target:
        raise DataError(f"{args.target} is not an LLM target (target.yaml with type: llm)")
    report = check(
        source,
        n_samples=args.n,
        llm_target=llm_target,
        decision_point=args.decision_point if not args.traces else None,
        source=Path(args.traces or args.decisions).name,
    )
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) if args.json else report)
    return 0


def _run_import(args: argparse.Namespace) -> int:
    output = Path(args.output)
    inputs_dir = Path(args.inputs_dir) if args.inputs_dir else output.parent / "inputs"
    records = import_traces(
        args.traces,
        decision_point=args.decision_point,
        action_map=args.action_map or "tool",
        context=args.context,
        join_key=args.join_key,
        decisions=args.decisions_mode,
        inputs_dir=inputs_dir,
        inputs_base=output.parent,
    )
    if not records:
        print(records.summary.render(), file=sys.stderr)
        raise DataError("no decisions found in the traces")
    write_decisions(records, output)
    print(records.summary.render(str(output)))
    return 0


def _run_sample(args: argparse.Namespace) -> int:
    targets = []
    for spec in args.target:
        policy = resolve_llm_target(spec)
        if policy is None:
            raise DataError(f"{spec} is not an LLM target (target.yaml with type: llm)")
        targets.append(policy)
    if args.no_logging and not targets:
        raise DataError("--no-logging needs at least one --target")
    plan = plan_sampling(
        args.decisions,
        n=args.n,
        targets=targets,
        include_logging=not args.no_logging,
        existing=load_samples(args.output),
        model=args.model,
        n_per_request=args.n_per_request,
        subset=args.subset,
        seed=args.seed,
        decision_point=args.decision_point,
    )
    policies = (["logging"] if not args.no_logging else []) + [t.name for t in targets]
    print(
        f"sampling {', '.join(policies)} · {len(plan.units):,} (decision, policy) pairs × "
        f"N={plan.n} → {plan.requests:,} requests"
        + (f" · {plan.skipped_cached:,} already in {args.output}" if plan.skipped_cached else "")
        + (
            f" · {plan.without_input:,} decisions without stored inputs"
            if plan.without_input
            else ""
        ),
        file=sys.stderr,
    )
    if not plan.units:
        print("nothing to sample", file=sys.stderr)
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            raise RefusedError("this calls the LLM; pass --yes to confirm")
        if input("proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            raise RefusedError("sampling cancelled")

    step = max(1, len(plan.units) // 20)

    def progress(done: int, total: int) -> None:
        if done % step == 0 or done == total:
            print(f"  {done:,}/{total:,}", file=sys.stderr)

    summary = run_sampling(
        plan, args.output, base_url=args.base_url, concurrency=args.concurrency, progress=progress
    )
    print(summary.render(args.output))
    return 0


def _run_eval(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    source = _decisions_source(args, parser)
    if args.traces:
        print(source.summary.render() + "\n", file=sys.stderr)  # type: ignore[attr-defined]
    report = evaluate(
        source,
        outcomes=args.outcomes,
        horizon=args.horizon,
        target=args.target,
        level=args.level,
        accept_unverifiable=args.accept_unverifiable,
        default_reward=args.default_reward,
        absent_means_default=args.absent_means_default,
        action_map=args.action_map,
        decision_point=args.decision_point,
        samples=args.samples,
        alpha=args.alpha,
        seed=args.seed,
        n_bootstrap=args.bootstrap,
        folds=args.folds,
    )
    print(report.to_json() if args.json else report)
    if args.output:
        Path(args.output).write_text(report.to_json() + "\n", encoding="utf-8")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _run_check(args, parser)
        if args.command == "import":
            return _run_import(args)
        if args.command == "sample":
            return _run_sample(args)
        return _run_eval(args, parser)
    except RefusedError as e:
        print(f"agentope: refused\n\n{e}", file=sys.stderr)
        return 1
    except DataError as e:
        print(f"agentope: error: {e}", file=sys.stderr)
        return 2
    except AgentopeError as e:
        print(f"agentope: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
