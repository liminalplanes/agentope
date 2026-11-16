"""agentope: offline evaluation of LLM agent decisions, without logprobs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentope")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

from .decisions import Decision, load_decisions  # noqa: E402
from .errors import AgentopeError, DataError, RefusedError  # noqa: E402
from .evaluate import evaluate  # noqa: E402
from .helpers import explore, randomize  # noqa: E402
from .outcomes import Outcome, load_outcomes  # noqa: E402
from .report import Report  # noqa: E402
from .targets import Target, callable_target, load_target_jsonl  # noqa: E402
from .verdict import VerdictThresholds  # noqa: E402

__all__ = [
    "AgentopeError",
    "DataError",
    "Decision",
    "Outcome",
    "RefusedError",
    "Report",
    "Target",
    "VerdictThresholds",
    "__version__",
    "callable_target",
    "evaluate",
    "explore",
    "load_decisions",
    "load_outcomes",
    "load_target_jsonl",
    "randomize",
]
