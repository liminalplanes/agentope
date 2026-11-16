"""agentope: offline evaluation of LLM agent decisions, without logprobs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agentope")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

from .checks import CheckReport, check  # noqa: E402
from .decisions import Decision, load_decisions  # noqa: E402
from .errors import AgentopeError, DataError, RefusedError  # noqa: E402
from .evaluate import evaluate  # noqa: E402
from .helpers import explore, randomize, span_attributes  # noqa: E402
from .importer import ImportedDecisions, import_traces  # noqa: E402
from .outcomes import Outcome, load_outcomes  # noqa: E402
from .report import Report  # noqa: E402
from .sampling import LLMPolicy, SampleRecord, load_samples, sample  # noqa: E402
from .targets import Target, callable_target, load_target_jsonl  # noqa: E402
from .verdict import VerdictThresholds  # noqa: E402

__all__ = [
    "SampleRecord",
    "LLMPolicy",
    "CheckReport",
    "AgentopeError",
    "DataError",
    "Decision",
    "ImportedDecisions",
    "Outcome",
    "RefusedError",
    "Report",
    "Target",
    "VerdictThresholds",
    "__version__",
    "callable_target",
    "sample",
    "load_samples",
    "check",
    "evaluate",
    "explore",
    "import_traces",
    "load_decisions",
    "load_outcomes",
    "load_target_jsonl",
    "randomize",
    "span_attributes",
]
