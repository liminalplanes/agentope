"""A small client for OpenAI-compatible chat-completions endpoints (spec §5.2).

Works with vLLM, Ollama, llama.cpp's server and hosted APIs. Needs the ``llm``
extra (``httpx``). The endpoint comes from ``--base-url`` / ``base_url``, else
``AGENTOPE_BASE_URL`` or ``OPENAI_BASE_URL``; the key from ``AGENTOPE_API_KEY``
or ``OPENAI_API_KEY`` (optional for local servers).
"""

import contextlib
import os
import random
import time
from dataclasses import dataclass
from typing import Any

from .errors import AgentopeError, DataError

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class LLMRequestError(AgentopeError):
    """A request failed for good (after retries, or with a non-retryable status)."""


def _httpx() -> Any:
    try:
        import httpx
    except ImportError:  # pragma: no cover
        raise AgentopeError(
            "LLM sampling needs the llm extra: pip install 'agentope[llm]' "
            "(or uv add 'agentope[llm]')"
        ) from None
    return httpx


@dataclass(frozen=True, slots=True)
class Endpoint:
    base_url: str
    api_key: str | None = None
    timeout: float = 120.0
    max_retries: int = 6
    backoff: float = 1.0
    """First retry delay in seconds; doubles per attempt, up to 60 s."""

    @classmethod
    def resolve(cls, base_url: str | None = None, **kw: Any) -> Endpoint:
        url = base_url or os.environ.get("AGENTOPE_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        if not url:
            raise DataError(
                "no LLM endpoint: pass --base-url (e.g. http://localhost:8000/v1) or set "
                "AGENTOPE_BASE_URL"
            )
        key = os.environ.get("AGENTOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        return cls(base_url=url.rstrip("/"), api_key=key, **kw)


class ChatClient:
    """Thread-safe; share one client across worker threads."""

    def __init__(self, endpoint: Endpoint, concurrency: int = 8):
        httpx = _httpx()
        headers = {"Content-Type": "application/json"}
        if endpoint.api_key:
            headers["Authorization"] = f"Bearer {endpoint.api_key}"
        self.endpoint = endpoint
        self._httpx = httpx
        self._client = httpx.Client(
            base_url=endpoint.base_url,
            headers=headers,
            timeout=endpoint.timeout,
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
        )
        self._rng = random.Random()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ChatClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def complete(self, body: dict[str, Any]) -> dict[str, Any]:
        delay = self.endpoint.backoff
        last = "no attempt"
        for attempt in range(self.endpoint.max_retries + 1):
            try:
                response = self._client.post("/chat/completions", json=body)
            except self._httpx.TransportError as e:
                last = f"{type(e).__name__}: {e}"
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError:
                        raise LLMRequestError("endpoint returned invalid JSON") from None
                last = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code not in RETRY_STATUS:
                    raise LLMRequestError(last)
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    with contextlib.suppress(ValueError):
                        delay = max(delay, float(retry_after))
            if attempt < self.endpoint.max_retries:
                time.sleep(delay * (0.5 + self._rng.random()))
                delay = min(delay * 2, 60.0)
        raise LLMRequestError(f"giving up after {self.endpoint.max_retries + 1} attempts: {last}")
