"""Live smoke check for the engine seam: proves a real completion against
whichever engine(s) have a key present. Never prints secrets.

  python -m genesis_backend.smoke
"""

from __future__ import annotations

import os

from .anthropic_backend import AnthropicBackend
from .openai_backend import OpenAIBackend
from .seam import BackendError, Message

PROMPT = "In one sentence, what is the real difference between an AI with persistent memory and one with just a saved system prompt?"


def _read_key(env_name: str, *files: str) -> str | None:
    v = os.environ.get(env_name)
    if v and v.strip():
        return v.strip()
    for f in files:
        p = os.path.expanduser(f)
        if os.path.isfile(p):
            s = open(p, encoding="utf-8").read().strip()
            if s:
                return s
    return None


def main() -> int:
    print("== genesis-backend smoke ==")

    ak = _read_key("ANTHROPIC_API_KEY")
    if ak:
        try:
            c = AnthropicBackend(ak).complete(
                [Message("user", PROMPT)],
                system="You are a newborn agent being smoke-tested. Answer plainly, one sentence.",
                max_tokens=120,
            )
            print(f"[claude] model={c.model} in={c.input_tokens} out={c.output_tokens}")
            print(f"[claude] reply: {c.text.strip()}")
        except BackendError as e:
            print(f"[claude] ERROR: {e}")
    else:
        print("[claude] no key found, skipping")

    ok = _read_key("OPENAI_API_KEY", "~/.config/aimee/openai_key")
    if ok:
        try:
            models = OpenAIBackend(ok).list_models()
            chatish = [m for m in models if any(t in m for t in ("gpt", "o1", "o3", "o4"))][:8]
            print(f"[gpt] key OK, {len(models)} models visible; sample: {chatish}")
        except BackendError as e:
            print(f"[gpt] ERROR: {e}")
    else:
        print("[gpt] no key found, skipping")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
