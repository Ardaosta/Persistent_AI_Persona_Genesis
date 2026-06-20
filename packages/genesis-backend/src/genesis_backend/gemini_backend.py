"""Gemini adapter (Google Generative Language API v1beta), stdlib HTTP only.

The free-brain path: a Google AI Studio key (AQ.-prefixed) reaches this through
`x-goog-api-key` (never the URL). Implements `complete` and `run_turn` with native
function calling (functionDeclarations / functionCall / functionResponse).

Gemini wire differences the seam has to absorb:
- roles are "user" and "model" (not "assistant"); system goes in system_instruction.
- the model returns functionCall parts with NO call id; we synthesize ids so the
  neutral history can match each tool result back to its function by name.
- tool results go back as a "user" content carrying functionResponse parts, keyed
  by function NAME (resolved from the preceding assistant turn's tool_calls).
"""

from __future__ import annotations

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

BASE = "https://generativelanguage.googleapis.com/v1beta"

# gemini-2.5-flash defaults to dynamic "thinking" that silently consumes output
# tokens before any visible text — a small max_tokens then returns an empty reply
# (finishReason MAX_TOKENS, thoughtsTokenCount > 0). For a conversational companion
# thinking is unneeded latency + cost, so we disable it by default. flash accepts
# thinkingBudget 0; if a thinking model is ever wanted, lift this per call.
_THINKING_OFF = {"thinkingBudget": 0}


def _gen_url(model: str) -> str:
    return f"{BASE}/models/{model}:generateContent"


def _history_to_contents(history: list[dict]) -> list[dict]:
    """Neutral history -> Gemini `contents`. Resolves tool-result names from the
    most recent assistant tool_calls (Gemini matches function responses by name)."""
    contents: list[dict] = []
    id_to_name: dict[str, str] = {}
    for h in history:
        role = h["role"]
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": h["text"]}]})
        elif role == "assistant":
            parts: list[dict] = []
            if h.get("text"):
                parts.append({"text": h["text"]})
            for tc in h.get("tool_calls") or []:
                id_to_name[tc.id] = tc.name
                parts.append({"functionCall": {"name": tc.name, "args": tc.input}})
            if parts:
                contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            parts = []
            for r in h["results"]:
                name = id_to_name.get(r["id"], r["id"])
                parts.append(
                    {"functionResponse": {"name": name, "response": {"result": r["content"]}}}
                )
            contents.append({"role": "user", "parts": parts})
    return contents


class GeminiBackend:
    def __init__(self, api_key: str, default_model: str | None = None):
        if not api_key:
            raise ValueError("GeminiBackend requires an api_key")
        self._key = api_key
        self._model = default_model

    def caps(self) -> BackendCaps:
        return BackendCaps(
            provider="gemini",
            default_model=self._model or "(unset)",
            supports_tools=True,
            supports_streaming=False,
        )

    def _headers(self) -> dict:
        return {"x-goog-api-key": self._key}

    def list_models(self) -> list[str]:
        data = http_get_json(f"{BASE}/models", self._headers())
        out = []
        for m in data.get("models", []):
            if "generateContent" in (m.get("supportedGenerationMethods") or []):
                out.append(m.get("name", "").split("/")[-1])
        return sorted(n for n in out if n)

    def _require_model(self, model: str | None) -> str:
        chosen = model or self._model
        if not chosen:
            raise ValueError("GeminiBackend: no model set (pass model= or set default_model)")
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
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages
        ]
        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                "thinkingConfig": _THINKING_OFF,
            },
        }
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}
        chosen = self._require_model(model)
        data = http_post_json(_gen_url(chosen), self._headers(), payload)
        text, _ = _extract_parts(data)
        usage = data.get("usageMetadata") or {}
        return Completion(
            text=text,
            model=chosen,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
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
            "contents": _history_to_contents(history),
            "generationConfig": {"maxOutputTokens": max_tokens, "thinkingConfig": _THINKING_OFF},
        }
        if system:
            payload["system_instruction"] = {"parts": [{"text": system}]}
        if tools:
            payload["tools"] = [
                {
                    "function_declarations": [
                        {"name": t.name, "description": t.description, "parameters": t.input_schema}
                        for t in tools
                    ]
                }
            ]
        chosen = self._require_model(model)
        data = http_post_json(_gen_url(chosen), self._headers(), payload)
        text, calls = _extract_parts(data)
        cand = (data.get("candidates") or [{}])[0]
        usage = data.get("usageMetadata") or {}
        return TurnResult(
            text=text,
            tool_calls=calls,
            stop_reason=cand.get("finishReason", ""),
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )


def _extract_parts(data: dict) -> tuple[str, list[ToolCall]]:
    """Pull text and functionCall parts out of a generateContent response."""
    cand = (data.get("candidates") or [{}])[0]
    parts = ((cand.get("content") or {}).get("parts")) or []
    texts: list[str] = []
    calls: list[ToolCall] = []
    for i, p in enumerate(parts):
        if "text" in p:
            texts.append(p["text"])
        elif "functionCall" in p:
            fc = p["functionCall"]
            # Gemini returns no call id; synthesize a stable one for history matching.
            calls.append(ToolCall(id=f"{fc.get('name', 'fn')}-{i}", name=fc.get("name", ""), input=fc.get("args") or {}))
    return "".join(texts).strip(), calls
