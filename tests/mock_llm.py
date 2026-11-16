"""A local OpenAI-compatible /v1/chat/completions server for tests.

``policy(body) -> {action: probability}`` decides the answer distribution; tool
actions come back as tool calls, ``__none__`` as a plain text answer.
"""

from __future__ import annotations

import json
import random
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

type Policy = Callable[[dict[str, Any]], dict[str, float]]


class MockLLM:
    def __init__(
        self,
        policy: Policy,
        *,
        seed: int = 0,
        model: str | None = None,
        fail_first: int = 0,
        fail_status: int = 429,
    ):
        self.policy = policy
        self.model = model
        self.fail_first = fail_first
        self.fail_status = fail_status
        self.requests = 0
        self.bodies: list[dict[str, Any]] = []
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_POST(self) -> None:
                length = int(self.headers.get("content-length", 0))
                body = json.loads(self.rfile.read(length))
                status, payload = mock.handle(self.path, body)
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                if status == 429:
                    self.send_header("retry-after", "0")
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def __enter__(self) -> MockLLM:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def handle(self, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if path != "/v1/chat/completions":
            return 404, {"error": "not found"}
        with self._lock:
            self.requests += 1
            self.bodies.append(body)
            if self.requests <= self.fail_first:
                return self.fail_status, {"error": {"message": "try again"}}
            probs = self.policy(body)
            actions = list(probs)
            weights = [probs[a] for a in actions]
            picks = [
                self._rng.choices(actions, weights=weights)[0] for _ in range(int(body.get("n", 1)))
            ]
        choices = []
        for i, action in enumerate(picks):
            if action == "__none__":
                message = {"role": "assistant", "content": "Here is the answer."}
                finish = "stop"
            else:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {"name": action, "arguments": "{}"},
                        }
                    ],
                }
                finish = "tool_calls"
            choices.append({"index": i, "message": message, "finish_reason": finish})
        return 200, {
            "id": "cmpl-test",
            "object": "chat.completion",
            "model": self.model or body.get("model"),
            "choices": choices,
        }
