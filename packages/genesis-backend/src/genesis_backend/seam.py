"""The one model-agnostic seam, plus tiny stdlib HTTP helpers.

No third-party SDKs: the providers' REST APIs are simple enough that urllib keeps
the dependency surface at zero and the seam genuinely portable. The agent loop
lives above this seam (in genesis-core); each backend translates a NEUTRAL
conversation history + neutral tool specs into its provider's native tool-use
wire format. That keeps "Claude or GPT, your choice" a one-line config flip and
never leaks a vendor shape upward.

Neutral history is a list of dicts:
  {"role": "user", "text": str}
  {"role": "assistant", "text": str, "tool_calls": [ToolCall, ...]}
  {"role": "tool", "results": [{"id": str, "content": str}, ...]}
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict  # JSON Schema (object)


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class TurnResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class BackendCaps:
    provider: str
    default_model: str
    supports_tools: bool = False
    supports_streaming: bool = False


class BackendError(RuntimeError):
    pass


@runtime_checkable
class Backend(Protocol):
    def caps(self) -> BackendCaps: ...

    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> Completion: ...

    def run_turn(
        self,
        history: list[dict],
        *,
        system: str = "",
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> TurnResult: ...


def _read_json(resp) -> dict:
    return json.loads(resp.read().decode("utf-8"))


def http_post_json(url: str, headers: dict, payload: dict, *, timeout: float = 120.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={**headers, "content-type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _read_json(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise BackendError(f"HTTP {e.code} from {url}: {detail[:600]}") from e
    except urllib.error.URLError as e:
        raise BackendError(f"network error to {url}: {e.reason}") from e


def http_get_json(url: str, headers: dict, *, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _read_json(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise BackendError(f"HTTP {e.code} from {url}: {detail[:600]}") from e
    except urllib.error.URLError as e:
        raise BackendError(f"network error to {url}: {e.reason}") from e
