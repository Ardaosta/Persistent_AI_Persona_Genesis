"""GPT adapter for the OpenAI Responses API (/v1/responses), stdlib HTTP only.

The chat/completions adapter (openai_backend.py) works for gpt-4.x, but the
gpt-5.x reasoning models (gpt-5.1+, gpt-5.6-sol/luna/terra, the codex family)
DO NOT support function tools on chat/completions at all — they require the
Responses API. This adapter speaks that endpoint through the SAME neutral seam
(run_turn -> TurnResult with tool_calls; tool results replayed as
function_call_output items), so genesis_core.Session drives a gpt-5.x brain with
shell_run/file_read/file_write exactly like any other engine.

Verified against gpt-5.6-sol (2026-07-20): function_call items carry call_id +
name + arguments; text arrives as message items with output_text content.
Reasoning is stored server-side; a stateless full-input replay of
function_call / function_call_output items is sufficient for the tool loop.
"""

from __future__ import annotations

import json

from .seam import (
    BackendCaps,
    Completion,
    Message,
    ToolCall,
    ToolSpec,
    TurnResult,
    http_get_json,
    http_post_json,
)

RESPONSES_API = "https://api.openai.com/v1/responses"
MODELS_API = "https://api.openai.com/v1/models"

# Reasoning models spend output tokens on hidden reasoning before the answer, so
# a 1024 ceiling can starve the visible reply. Floor the budget generously.
_MIN_OUTPUT_TOKENS = 4096


def _history_to_input(history: list[dict]) -> list[dict]:
    """Map the neutral history into Responses `input` items. Assistant tool calls
    become `function_call` items; tool results become `function_call_output`
    items keyed by the same call_id, so the round-trip is stateless."""
    items: list[dict] = []
    for h in history:
        role = h.get("role")
        if role == "user":
            items.append({"role": "user", "content": h["text"]})
        elif role == "assistant":
            if h.get("text"):
                items.append({"role": "assistant", "content": h["text"]})
            for tc in h.get("tool_calls") or []:
                items.append({
                    "type": "function_call",
                    "call_id": tc.id,
                    "name": tc.name,
                    "arguments": json.dumps(tc.input),
                })
        elif role == "tool":
            for r in h["results"]:
                items.append({
                    "type": "function_call_output",
                    "call_id": r["id"],
                    "output": r["content"],
                })
    return items


def _extract(data: dict) -> tuple[str, list[ToolCall]]:
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for item in data.get("output") or []:
        t = item.get("type")
        if t == "function_call":
            try:
                args = json.loads(item.get("arguments") or "{}")
            except Exception:
                args = {}
            calls.append(ToolCall(id=item.get("call_id", ""), name=item.get("name", ""), input=args))
        elif t == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    text_parts.append(c["text"])
    return "".join(text_parts), calls


class ResponsesBackend:
    def __init__(self, api_key: str, default_model: str | None = None):
        if not api_key:
            raise ValueError("ResponsesBackend requires an api_key")
        self._key = api_key
        self._model = default_model

    def caps(self) -> BackendCaps:
        return BackendCaps(
            provider="openai-responses",
            default_model=self._model or "(unset)",
            supports_tools=True,
            supports_streaming=False,
        )

    def _headers(self) -> dict:
        return {"authorization": f"Bearer {self._key}"}

    def list_models(self) -> list[str]:
        data = http_get_json(MODELS_API, self._headers())
        return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))

    def _require_model(self, model: str | None) -> str:
        chosen = model or self._model
        if not chosen:
            raise ValueError("ResponsesBackend: no model set (pass model= or set default_model)")
        return chosen

    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,   # accepted for seam parity; not sent (5.x fixes it)
    ) -> Completion:
        inp = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": self._require_model(model),
            "input": inp,
            "max_output_tokens": max(max_tokens, _MIN_OUTPUT_TOKENS),
        }
        if system:
            payload["instructions"] = system
        data = http_post_json(RESPONSES_API, self._headers(), payload)
        text, _ = _extract(data)
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            model=data.get("model", ""),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

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
            "model": self._require_model(model),
            "input": _history_to_input(history),
            "max_output_tokens": max(max_tokens, _MIN_OUTPUT_TOKENS),
        }
        if system:
            payload["instructions"] = system
        if tools:
            # Responses tools are FLAT (name/description/parameters at top level),
            # unlike chat/completions' nested {"function": {...}}.
            payload["tools"] = [
                {"type": "function", "name": t.name,
                 "description": t.description, "parameters": t.input_schema}
                for t in tools
            ]
        data = http_post_json(RESPONSES_API, self._headers(), payload)
        text, calls = _extract(data)
        usage = data.get("usage") or {}
        return TurnResult(
            text=text,
            tool_calls=calls,
            stop_reason=data.get("status", ""),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
