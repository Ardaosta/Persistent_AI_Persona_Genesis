"""The claude-cli provider: a sub-billed engine that needs no API key, and is
treated as non-training so the agent will deepen into private memory on it."""

from __future__ import annotations

import json

from genesis_backend import ClaudeCLIBackend
from genesis_core import config as cfgmod


def _cfg(tmp_path, **extra):
    (tmp_path / "config.json").write_text(json.dumps({"provider": "claude-cli", **extra}))
    return cfgmod.load(tmp_path)


def test_build_backend_needs_no_key(tmp_path):
    cfg = _cfg(tmp_path)
    be = cfg.build_backend()  # must NOT raise "no key"
    assert isinstance(be, ClaudeCLIBackend)
    assert be.caps().provider == "claude-cli"


def test_claude_cli_is_non_training(tmp_path):
    cfg = _cfg(tmp_path)
    assert cfg.engine_trains is False


def test_model_passes_through(tmp_path):
    cfg = _cfg(tmp_path, model="claude-opus-4-8")
    be = cfg.build_backend()
    assert be.caps().default_model == "claude-opus-4-8"
