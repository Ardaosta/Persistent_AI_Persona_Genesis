"""GPT adapter (OpenAI Chat Completions API), stdlib HTTP only.

Implements `complete` and `run_turn` (native function calling via the `tools`
param + `tool_calls` / role:"tool" messages). No hardcoded frontier model id:
the current GPT model id is set in config (verified live), never guessed here.
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

CHAT_API = "https://api.openai.com/v1/chat/completions"
MODELS_API = "https://api.openai.com/v1/models"


def parse_response(data: dict) -> Completion:
    choice = (data.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content")) or ""
    usage = data.get("usage") or {}
    return Completion(
        text=text,
        model=data.get("model", ""),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )


def _history_to_messages(history: list[dict], system: str) -> list[dict]:
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})
    for h in history:
        role = h["role"]
        if role == "user":
            msgs.append({"role": "user", "content": h["text"]})
        elif role == "assistant":
            m: dict = {"role": "assistant", "content": h.get("text") or None}
            if h.get("tool_calls"):
                m["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.input)},
                    }
                    for tc in h["tool_calls"]
                ]
            msgs.append(m)
        elif role == "tool":
            for r in h["results"]:
                msgs.append({"role": "tool", "tool_call_id": r["id"], "content": r["content"]})
    return msgs


class OpenAIBackend:
    def __init__(self, api_key: str, default_model: str | None = None):
        if not api_key:
            raise ValueError("OpenAIBackend requires an api_key")
        self._key = api_key
        self._model = default_model

    def caps(self) -> BackendCaps:
        return BackendCaps(
            provider="openai",
            default_model=self._model or "(unset)",
            supports_tools=True,
            supports_streaming=True,
        )

    def _headers(self) -> dict:
        return {"authorization": f"Bearer {self._key}"}

    def list_models(self) -> list[str]:
        data = http_get_json(MODELS_API, self._headers())
        return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))

    def _require_model(self, model: str | None) -> str:
        chosen = model or self._model
        if not chosen:
            raise ValueError("OpenAIBackend: no model set (pass model= or set default_model)")
        return chosen

    def complete(
        self,
        messages: list[Message],
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> Completion:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend({"role": m.role, "content": m.content} for m in messages)
        payload = {"model": self._require_model(model), "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        return parse_response(http_post_json(CHAT_API, self._headers(), payload))

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
            "messages": _history_to_messages(history, system),
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
                for t in tools
            ]
        data = http_post_json(CHAT_API, self._headers(), payload)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), input=args))
        usage = data.get("usage") or {}
        return TurnResult(
            text=text,
            tool_calls=calls,
            stop_reason=choice.get("finish_reason", ""),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
