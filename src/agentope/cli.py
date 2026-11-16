"""The `agentope` command (spec §7.1).

Exit codes: 0 report produced · 1 refused (a guard fired) · 2 usage error.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .errors import AgentopeError, DataError, RefusedError
from .evaluate import evaluate
from .importer import import_traces, write_decisions


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
        help="target.jsonl, or a Python callable as module:function or path/to/file.py:function",
    )
    e.add_argument("--decision-point", help="required when decisions cover several points")
    e.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3, 4),
        help="evidence level (default: 1 if any logged propensities, else 3)",
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


def _run_eval(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if (args.decisions is None) == (args.traces is None):
        parser.error("eval needs either a decisions file or --traces, not both")
    source: object = args.decisions
    if args.traces:
        source = import_traces(
            args.traces,
            decision_point=args.decision_point or "tool_choice",
            action_map=args.action_map or "tool",
            context=args.context,
            join_key=args.join_key,
            decisions=args.decisions_mode,
        )
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
        if args.command == "import":
            return _run_import(args)
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
