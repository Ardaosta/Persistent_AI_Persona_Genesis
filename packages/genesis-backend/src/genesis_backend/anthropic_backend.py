"""Claude adapter (Anthropic Messages API), stdlib HTTP only.

Implements both `complete` (one-shot) and `run_turn` (native tool use via the
`tools` param + `tool_use`/`tool_result` content blocks). Model ids come from
configuration, not guesswork.
"""

from __future__ import annotations

from .seam import (
    BackendCaps,
    Completion,
    Message,
    ToolCall,
    ToolSpec,
    TurnResult,
    http_post_json,
)

API = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"


def parse_response(data: dict) -> Completion:
    text = "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )
    usage = data.get("usage") or {}
    return Completion(
        text=text,
        model=data.get("model", ""),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
    )


def _history_to_messages(history: list[dict]) -> list[dict]:
    msgs: list[dict] = []
    for h in history:
        role = h["role"]
        if role == "user":
            msgs.append({"role": "user", "content": h["text"]})
        elif role == "assistant":
            content: list[dict] = []
            if h.get("text"):
                content.append({"type": "text", "text": h["text"]})
            for tc in h.get("tool_calls", []):
                content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
            msgs.append({"role": "assistant", "content": content or [{"type": "text", "text": " "}]})
        elif role == "tool":
            msgs.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": r["id"], "content": r["content"]}
                    for r in h["results"]
                ],
            })
    return msgs


def _with_history_cache(msgs: list[dict]) -> list[dict]:
    """Return `msgs` with one prompt-cache breakpoint on the final content block.

    The request renders tools -> system -> messages, and the cache matches the
    exact prefix up to a breakpoint. Marking the LAST block caches the whole
    conversation so far; next turn (or next tool step) re-sends the identical
    prefix plus a delta, and reads everything before the delta from cache. The
    system prompt is built once per Session, so it stays byte-identical across
    turns and never invalidates the history behind it.

    Works on copies: the caller's message dicts (and the neutral history they
    came from) are never mutated. Prefixes under the model's minimum (1,024
    tokens on Sonnet 4.6) are simply not cached; the API accepts the marker.
    """
    if not msgs:
        return msgs
    out = list(msgs)
    last = dict(out[-1])
    content = last["content"]
    if isinstance(content, str):
        blocks = [{"type": "text", "text": content}]
    else:
        blocks = [dict(b) for b in content]
    if not blocks:
        return msgs
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    last["content"] = blocks
    out[-1] = last
    return out


class AnthropicBackend:
    def __init__(self, api_key: str, default_model: str = DEFAULT_MODEL):
        if not api_key:
            raise ValueError("AnthropicBackend requires an api_key")
        self._key = api_key
        self._model = default_model

    def caps(self) -> BackendCaps:
        return BackendCaps(
            provider="anthropic",
            default_model=self._model,
            supports_tools=True,
            supports_streaming=True,
        )

    def _headers(self) -> dict:
        return {"x-api-key": self._key, "anthropic-version": API_VERSION}

    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> Completion:
        payload: dict = {
            "model": model or self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            payload["system"] = system
        return parse_response(http_post_json(API, self._headers(), payload))

    def run_turn(
        self,
        history: list[dict],
        *,
        system: str = "",
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> TurnResult:
        payload: dict = {
            "model": model or self._model,
            "max_tokens": max_tokens,
            "messages": _with_history_cache(_history_to_messages(history)),
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        data = http_post_json(API, self._headers(), payload)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        calls = [
            ToolCall(id=b["id"], name=b["name"], input=b.get("input", {}))
            for b in data.get("content", [])
            if b.get("type") == "tool_use"
        ]
        usage = data.get("usage") or {}
        return TurnResult(
            text=text,
            tool_calls=calls,
            stop_reason=data.get("stop_reason", ""),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens"),
            cache_read_input_tokens=usage.get("cache_read_input_tokens"),
        )
