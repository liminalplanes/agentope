"""A stand-in for the vLLM server that runs the agent's model.

It speaks the OpenAI chat-completions API and answers the way the simulated model
chooses (world.model_policy), reading the situation from the messages it is sent.
Answers are seeded from the request, so a run is reproducible.
"""

import hashlib
import json
import random
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from world import ACTIONS, model_policy, situation


def _answer(body: dict) -> dict:
    messages = body["messages"]
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    probs = model_policy(situation(system, user))
    n = int(body.get("n", 1))
    seed = hashlib.sha256(json.dumps([messages, n], sort_keys=True).encode()).hexdigest()
    rng = random.Random(seed)
    picks = rng.choices(ACTIONS, weights=[probs[a] for a in ACTIONS], k=n)
    choices = []
    for i, action in enumerate(picks):
        if action == "__none__":
            message = {"role": "assistant", "content": "Here's what you can do: …"}
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
    return {
        "id": f"chatcmpl-{seed[:12]}",
        "object": "chat.completion",
        "model": body.get("model"),
        "choices": choices,
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        data = json.dumps(_answer(body)).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@contextmanager
def serve() -> Iterator[str]:
    """Run the server on a free local port; yields its base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        server.server_close()
