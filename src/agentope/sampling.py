"""Level 2: estimate propensities by re-running the logging model.

``sample`` is the only step that calls an LLM. For each decision with a stored
input, it asks the logging model (and optionally LLM target policies) for N
responses, applies the decision's action map to each, and appends one line per
(decision, policy) to ``samples.jsonl``:

    {"decision_id": "conv-8812:3", "policy": "logging", "model": "qwen2.5-7b-instruct",
     "params": {"temperature": 0.7}, "input_sha256": "…", "stored_input_sha256": "…",
     "action_map": "tool", "n": 32, "counts": {"lookup_order": 21, "__none__": 4, …},
     "failed": 0, "response_models": {"qwen2.5-7b-instruct": 32}}

``counts`` are raw (smoothing happens at evaluation). ``failed`` samples errored
and are not in ``counts``. A rerun skips lines whose decision, policy, model,
parameters, request and action map are unchanged, so an interrupted run resumes.
"""

from __future__ import annotations

import hashlib
import json
import random
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .action_maps import ToolCall, resolve_action_map
from .decisions import Decision, load_decisions
from .errors import AgentopeError, DataError
from .io import PathArg, canonical_sha256, is_path, read_jsonl
from .llm import ChatClient, Endpoint, LLMRequestError

LOGGING = "logging"
SAMPLING_PARAMS = ("temperature", "top_p", "max_tokens", "seed")


# ── samples.jsonl ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SampleRecord:
    decision_id: str
    policy: str
    model: str | None
    params: dict[str, Any]
    input_sha256: str
    action_map: str
    n: int
    counts: dict[str, int]
    failed: int = 0
    stored_input_sha256: str | None = None
    response_models: dict[str, int] = field(default_factory=dict)

    @property
    def valid(self) -> int:
        return sum(self.counts.values())

    def key(self) -> tuple[Any, ...]:
        return (
            self.decision_id,
            self.policy,
            self.model,
            json.dumps(self.params, sort_keys=True),
            self.input_sha256,
            self.action_map,
            self.n,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "policy": self.policy,
            "model": self.model,
            "params": self.params,
            "input_sha256": self.input_sha256,
            "stored_input_sha256": self.stored_input_sha256,
            "action_map": self.action_map,
            "n": self.n,
            "counts": self.counts,
            "failed": self.failed,
            "response_models": self.response_models,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any], where: str) -> SampleRecord:
        try:
            counts = {str(a): int(c) for a, c in d["counts"].items()}
            record = cls(
                decision_id=str(d["decision_id"]),
                policy=str(d["policy"]),
                model=d.get("model"),
                params=dict(d.get("params") or {}),
                input_sha256=str(d["input_sha256"]),
                action_map=str(d.get("action_map") or "tool"),
                n=int(d["n"]),
                counts=counts,
                failed=int(d.get("failed") or 0),
                stored_input_sha256=d.get("stored_input_sha256"),
                response_models={
                    str(k): int(v) for k, v in (d.get("response_models") or {}).items()
                },
            )
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise DataError(f"{where}: invalid sample record ({e})") from None
        if any(c < 0 for c in counts.values()) or record.valid + record.failed > record.n:
            raise DataError(f"{where}: counts and failed exceed n")
        return record


class Samples(dict[tuple[str, str], SampleRecord]):
    """(decision_id, policy) → the latest record. ``source`` is the file it came from."""

    source: str | None = None

    def policies(self) -> set[str]:
        return {policy for _, policy in self}


def load_samples(source: object) -> Samples:
    out = Samples()
    if source is None:
        return out
    if isinstance(source, Samples):
        return source
    if is_path(source):
        if not Path(source).exists():  # type: ignore[arg-type]
            return out
        out.source = str(source)
        rows: Iterable[tuple[str, Any]] = (
            (f"{source}:{n}", obj)
            for n, obj in read_jsonl(source)  # type: ignore[arg-type]
        )
    else:
        rows = ((f"sample #{i}", obj) for i, obj in enumerate(source, 1))  # type: ignore[call-overload]
    for where, obj in rows:
        record = obj if isinstance(obj, SampleRecord) else SampleRecord.from_dict(obj, where)
        out[(record.decision_id, record.policy)] = record
    return out


# ── policies to sample ───────────────────────────────────────────────────────


def load_stored_input(decision: Decision, base: Path) -> dict[str, Any]:
    if not decision.input_ref:
        raise DataError(f"decision {decision.decision_id} has no stored input (input_ref)")
    path = Path(decision.input_ref)
    if not path.is_absolute():
        path = base / path
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DataError(f"stored input {path} not found") from None
    except json.JSONDecodeError as e:
        raise DataError(f"stored input {path}: invalid JSON ({e.msg})") from None
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise DataError(f"stored input {path} is not a chat-completions request body")
    return body


def _replace_system(messages: list[dict[str, Any]], prompt: str) -> list[dict[str, Any]]:
    rest = [m for m in messages if m.get("role") not in ("system", "developer")]
    return [{"role": "system", "content": prompt}, *rest]


class LLMPolicy:
    """An LLM target policy, sampled on each decision's stored input.

    Either give ``render(stored_input) -> request body`` or the simple overrides:
    ``model``, ``system_prompt`` (replaces the system message), ``temperature``,
    ``top_p``, ``max_tokens``, ``tools`` (a list of tool definitions).
    """

    def __init__(
        self,
        name: str,
        *,
        render: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        source_files: dict[str, str] | None = None,
    ):
        if not name or name == LOGGING:
            raise DataError(f"an LLM target needs a name other than {LOGGING!r}")
        self.name = name
        self.render = render
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.tools = tools
        self.source_files = source_files or {}

    @property
    def description(self) -> str:
        return f"LLM policy {self.name}" + (f" ({self.model})" if self.model else "")

    def request(self, stored: dict[str, Any]) -> dict[str, Any]:
        body = json.loads(json.dumps(stored))
        if self.render is not None:
            body = self.render(body)
            if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
                raise DataError(f"render() of {self.name} must return a request body with messages")
        if self.system_prompt is not None:
            body["messages"] = _replace_system(body["messages"], self.system_prompt)
        if self.tools is not None:
            body["tools"] = self.tools
        for key in ("model", "temperature", "top_p", "max_tokens"):
            value = getattr(self, key)
            if value is not None:
                body[key] = value
        return body


def load_llm_target(path: PathArg) -> LLMPolicy:
    """Read target.yaml / target.json."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise AgentopeError(
                "target.yaml needs the llm extra: pip install 'agentope[llm]'"
            ) from None
        spec = yaml.safe_load(text)
    else:
        spec = json.loads(text)
    if not isinstance(spec, dict) or spec.get("type") != "llm":
        raise DataError(f"{path}: expected an LLM target with `type: llm`")
    files = {str(p): hashlib.sha256(text.encode()).hexdigest()}

    def resolve_text(value: Any) -> str | None:
        if value is None:
            return None
        candidate = p.parent / str(value)
        if candidate.is_file():
            content = candidate.read_text(encoding="utf-8")
            files[str(candidate)] = hashlib.sha256(content.encode()).hexdigest()
            return content
        return str(value)

    tools = spec.get("tools", "unchanged")
    tool_defs = None
    if tools not in (None, "unchanged"):
        tools_text = resolve_text(tools)
        try:
            tool_defs = json.loads(tools_text or "")
        except json.JSONDecodeError:
            raise DataError(
                f"{path}: tools must be 'unchanged' or a JSON file of definitions"
            ) from None
    known = {
        "type",
        "name",
        "decision_point",
        "endpoint",
        "model",
        "system_prompt",
        "temperature",
        "top_p",
        "max_tokens",
        "tools",
    }
    unknown = set(spec) - known
    if unknown:
        raise DataError(
            f"{path}: unknown fields {', '.join(sorted(unknown))}; anything beyond model, "
            "system_prompt, temperature, top_p, max_tokens and tools needs the Python API"
        )
    return LLMPolicy(
        name=str(spec.get("name") or p.stem),
        model=spec.get("model"),
        system_prompt=resolve_text(spec.get("system_prompt")),
        temperature=spec.get("temperature"),
        top_p=spec.get("top_p"),
        max_tokens=spec.get("max_tokens"),
        tools=tool_defs,
        source_files=files,
    )


def is_llm_target_file(target: object) -> bool:
    if not is_path(target):
        return False
    p = Path(str(target))
    if not p.is_file() or p.suffix not in (".yaml", ".yml", ".json"):
        return False
    if p.suffix == ".json":
        try:
            return json.loads(p.read_text()).get("type") == "llm"
        except (json.JSONDecodeError, AttributeError):
            return False
    return True


def resolve_llm_target(target: object) -> LLMPolicy | None:
    if isinstance(target, LLMPolicy):
        return target
    if is_llm_target_file(target):
        return load_llm_target(target)  # type: ignore[arg-type]
    return None


def logging_request(
    stored: dict[str, Any], decision: Decision, model: str | None = None
) -> dict[str, Any]:
    body = json.loads(json.dumps(stored))
    config = decision.logging_config or {}
    if model:
        body["model"] = model
    elif not body.get("model") and config.get("model"):
        body["model"] = config["model"]
    for key in SAMPLING_PARAMS:
        if key not in body and key in config:
            body[key] = config[key]
    if not body.get("model"):
        raise DataError(
            f"decision {decision.decision_id}: no logging model in the stored input or "
            "logging_config; pass --model"
        )
    return body


def response_tool_calls(choice: Mapping[str, Any]) -> list[ToolCall]:
    message = choice.get("message") or {}
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = (tc or {}).get("function") or {}
        if fn.get("name"):
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = None
            calls.append(ToolCall(str(fn["name"]), args if isinstance(args, dict) else None))
    return calls


# ── the sample step ──────────────────────────────────────────────────────────


@dataclass
class SamplePlan:
    units: list[tuple[Decision, str, dict[str, Any], str]]
    """(decision, policy name, request body, stored input sha) still to sample."""
    skipped_cached: int
    without_input: int
    requests: int
    n: int
    n_per_request: int

    @property
    def samples(self) -> int:
        return len(self.units) * self.n


@dataclass
class SampleSummary:
    written: int = 0
    cached: int = 0
    without_input: int = 0
    failed_samples: int = 0
    total_samples: int = 0
    errors: Counter[str] = field(default_factory=Counter)

    def render(self, output: str) -> str:
        lines = [
            f"sampled {self.written:,} (decision, policy) pairs → {output}",
            f"  reused        {self.cached:,} already in {output}",
        ]
        if self.without_input:
            lines.append(f"  no input      {self.without_input:,} decisions without a stored input")
        if self.failed_samples:
            lines.append(
                f"  failed        {self.failed_samples:,} of {self.total_samples:,} samples "
                "(excluded from counts)"
            )
            for err, count in self.errors.most_common(3):
                lines.append(f"    {count:,}× {err}")
        return "\n".join(lines)


def _decisions_and_base(decisions: object, base: PathArg | None) -> tuple[list[Decision], Path]:
    loaded = load_decisions(decisions)
    if base is not None:
        return loaded, Path(base)
    if is_path(decisions):
        return loaded, Path(str(decisions)).parent
    return loaded, Path.cwd()


def plan_sampling(
    decisions: object,
    *,
    n: int = 32,
    targets: Sequence[LLMPolicy] = (),
    include_logging: bool = True,
    existing: Samples | None = None,
    model: str | None = None,
    n_per_request: int = 1,
    subset: int | None = None,
    seed: int = 0,
    decision_point: str | None = None,
    base: PathArg | None = None,
) -> SamplePlan:
    if n < 1 or n_per_request < 1:
        raise DataError("n and n_per_request must be at least 1")
    ds, base_dir = _decisions_and_base(decisions, base)
    if decision_point is not None:
        ds = [d for d in ds if d.decision_point == decision_point]
    with_input = [d for d in ds if d.input_ref]
    without = len(ds) - len(with_input)
    if subset is not None and subset < len(with_input):
        with_input = sorted(random.Random(seed).sample(with_input, subset), key=lambda d: d.t)
    existing = existing or Samples()

    units = []
    cached = 0
    for d in with_input:
        stored = load_stored_input(d, base_dir)
        stored_sha = canonical_sha256(stored)
        bodies: list[tuple[str, dict[str, Any]]] = []
        if include_logging:
            bodies.append((LOGGING, logging_request(stored, d, model)))
        bodies.extend((t.name, t.request(stored)) for t in targets)
        for policy, body in bodies:
            record = existing.get((d.decision_id, policy))
            key = (
                d.decision_id,
                policy,
                body.get("model"),
                json.dumps({k: body[k] for k in SAMPLING_PARAMS if k in body}, sort_keys=True),
                canonical_sha256(body),
                d.action_map or "tool",
                n,
            )
            if record is not None and record.key() == key:
                cached += 1
                continue
            units.append((d, policy, body, stored_sha))
    per_unit = -(-n // n_per_request)
    return SamplePlan(
        units=units,
        skipped_cached=cached,
        without_input=without,
        requests=len(units) * per_unit,
        n=n,
        n_per_request=n_per_request,
    )


def run_sampling(
    plan: SamplePlan,
    output: PathArg,
    *,
    base_url: str | None = None,
    concurrency: int = 8,
    progress: Callable[[int, int], None] | None = None,
    endpoint_options: Mapping[str, Any] | None = None,
) -> SampleSummary:
    summary = SampleSummary(cached=plan.skipped_cached, without_input=plan.without_input)
    if not plan.units:
        return summary
    endpoint = Endpoint.resolve(base_url, **(endpoint_options or {}))
    lock = threading.Lock()
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    action_maps = {}

    def one(unit: tuple[Decision, str, dict[str, Any], str]) -> SampleRecord:
        decision, policy, body, stored_sha = unit
        name = decision.action_map or "tool"
        amap = action_maps.get(name)
        if amap is None:
            amap = action_maps.setdefault(name, resolve_action_map(name))
        counts: Counter[str] = Counter()
        models: Counter[str] = Counter()
        failed = 0
        errors: Counter[str] = Counter()
        remaining = plan.n
        while remaining > 0:
            k = min(plan.n_per_request, remaining)
            remaining -= k
            request = dict(body, n=k) if k > 1 else dict(body)
            try:
                response = client.complete(request)
            except LLMRequestError as e:
                failed += k
                errors[str(e)[:120]] += 1
                continue
            choices = response.get("choices") or []
            for choice in choices[:k]:
                try:
                    counts[amap.fn(response_tool_calls(choice))] += 1
                except Exception as e:  # noqa: BLE001 - an unmappable response is a failed sample
                    failed += 1
                    errors[f"action map: {type(e).__name__}"] += 1
            failed += max(0, k - len(choices))
            if response.get("model"):
                models[str(response["model"])] += min(k, len(choices))
        with lock:
            summary.errors.update(errors)
        return SampleRecord(
            decision_id=decision.decision_id,
            policy=policy,
            model=body.get("model"),
            params={k: body[k] for k in SAMPLING_PARAMS if k in body},
            input_sha256=canonical_sha256(body),
            stored_input_sha256=stored_sha,
            action_map=name,
            n=plan.n,
            counts=dict(sorted(counts.items())),
            failed=failed,
            response_models=dict(models),
        )

    with (
        ChatClient(endpoint, concurrency) as client,
        out_path.open("a", encoding="utf-8") as f,
        ThreadPoolExecutor(max_workers=concurrency) as pool,
    ):
        futures = [pool.submit(one, u) for u in plan.units]
        for done, future in enumerate(as_completed(futures), 1):
            record = future.result()
            with lock:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
                f.flush()
                summary.written += 1
                summary.failed_samples += record.failed
                summary.total_samples += record.n
            if progress:
                progress(done, len(futures))
    return summary


def sample(
    decisions: object,
    *,
    output: PathArg,
    n: int = 32,
    targets: Sequence[LLMPolicy | PathArg] = (),
    include_logging: bool = True,
    base_url: str | None = None,
    model: str | None = None,
    concurrency: int = 8,
    n_per_request: int = 1,
    subset: int | None = None,
    seed: int = 0,
    decision_point: str | None = None,
    base: PathArg | None = None,
    endpoint_options: Mapping[str, Any] | None = None,
) -> SampleSummary:
    """Sample the logging model (and LLM targets) on stored inputs; append to ``output``.

    ``endpoint_options`` go to :class:`agentope.llm.Endpoint` (timeout, max_retries, backoff).
    """
    policies = []
    for t in targets:
        policy = resolve_llm_target(t)
        if policy is None:
            raise DataError(
                f"{t!r} is not an LLM target (target.yaml with type: llm, or LLMPolicy)"
            )
        policies.append(policy)
    plan = plan_sampling(
        decisions,
        n=n,
        targets=policies,
        include_logging=include_logging,
        existing=load_samples(output),
        model=model,
        n_per_request=n_per_request,
        subset=subset,
        seed=seed,
        decision_point=decision_point,
        base=base,
    )
    return run_sampling(
        plan,
        output,
        base_url=base_url,
        concurrency=concurrency,
        endpoint_options=endpoint_options,
    )
