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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentope",
        description="Offline evaluation of LLM agent decisions, without logprobs.",
    )
    parser.add_argument("--version", action="version", version=f"agentope {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    e = sub.add_parser(
        "eval",
        help="estimate how a target policy would have done on logged decisions",
        description="Estimate how a target policy would have done on logged decisions.",
    )
    e.add_argument("decisions", help="decisions.jsonl (optionally gzipped)")
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
        "--map",
        dest="action_map",
        default="tool",
        help="the action map that produced `chosen`, for the report (default: tool)",
    )
    e.add_argument("--seed", type=int, default=0, help="seed for the bootstrap and folds (0)")
    e.add_argument("--bootstrap", type=int, default=2000, help="bootstrap resamples (2000)")
    e.add_argument("--folds", type=int, default=5, help="cross-fitting folds at Level 3 (5)")
    e.add_argument("--json", action="store_true", help="print the report as JSON")
    e.add_argument("-o", "--output", help="also write the JSON report to this file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate(
            args.decisions,
            outcomes=args.outcomes,
            horizon=args.horizon,
            target=args.target,
            level=args.level,
            accept_unverifiable=args.accept_unverifiable,
            default_reward=args.default_reward,
            action_map=args.action_map,
            decision_point=args.decision_point,
            seed=args.seed,
            n_bootstrap=args.bootstrap,
            folds=args.folds,
        )
    except RefusedError as e:
        print(f"agentope: refused\n\n{e}", file=sys.stderr)
        return 1
    except DataError as e:
        print(f"agentope: error: {e}", file=sys.stderr)
        return 2
    except AgentopeError as e:
        print(f"agentope: error: {e}", file=sys.stderr)
        return 1

    print(report.to_json() if args.json else report)
    if args.output:
        Path(args.output).write_text(report.to_json() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
