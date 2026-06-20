import tempfile
import unittest
from pathlib import Path

from genesis_core.agent import dispatch, parse_tool_calls
from genesis_core.config import GenesisConfig
from genesis_memory import Vault


class TestProtocol(unittest.TestCase):
    def test_parses_tool_block(self):
        text = 'sure\n```tool\n{"tool":"remember","args":{"id":"x","kind":"user","description":"d"}}\n```'
        calls = parse_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "remember")

    def test_plain_text_has_no_calls(self):
        self.assertEqual(parse_tool_calls("just talking, no tools"), [])

    def test_bad_json_is_ignored(self):
        self.assertEqual(parse_tool_calls("```tool\nnot json\n```"), [])


class TestDispatch(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.v = Vault(Path(self._t.name))

    def tearDown(self):
        self._t.cleanup()

    def test_remember_then_recall_by_id(self):
        out = dispatch({"tool": "remember", "args": {"id": "dog-biscuit", "kind": "user", "description": "his dog Biscuit"}}, self.v)
        self.assertIn("saved", out)
        self.assertEqual(self.v.get("dog-biscuit").description, "his dog Biscuit")
        self.assertIn("Biscuit", dispatch({"tool": "recall", "args": {"id": "dog-biscuit"}}, self.v))

    def test_recall_by_query(self):
        dispatch({"tool": "remember", "args": {"id": "dog-biscuit", "kind": "user", "description": "Golden Retriever named Biscuit"}}, self.v)
        self.assertIn("dog-biscuit", dispatch({"tool": "recall", "args": {"query": "retriever"}}, self.v))

    def test_bad_kind_errors_gracefully(self):
        out = dispatch({"tool": "remember", "args": {"id": "x", "kind": "bogus", "description": "d"}}, self.v)
        self.assertIn("error", out)

    def test_remember_refused_on_training_engine(self):
        cfg = GenesisConfig(root=Path(self._t.name), provider="gemini")  # trains by default
        out = dispatch(
            {"tool": "remember", "args": {"id": "dog-biscuit", "kind": "user", "description": "his dog Biscuit"}},
            self.v, cfg,
        )
        self.assertIn("not saved", out)
        self.assertIsNone(self.v.get("dog-biscuit"))  # nothing written

    def test_remember_allowed_on_private_engine(self):
        cfg = GenesisConfig(root=Path(self._t.name), provider="anthropic")  # does not train
        out = dispatch(
            {"tool": "remember", "args": {"id": "dog-biscuit", "kind": "user", "description": "his dog Biscuit"}},
            self.v, cfg,
        )
        self.assertIn("saved", out)
        self.assertIsNotNone(self.v.get("dog-biscuit"))

    def test_recall_still_works_on_training_engine(self):
        # recall (reading existing memory) is fine; only writing is gated.
        priv = GenesisConfig(root=Path(self._t.name), provider="anthropic")
        dispatch({"tool": "remember", "args": {"id": "dog-biscuit", "kind": "user", "description": "Biscuit"}}, self.v, priv)
        train = GenesisConfig(root=Path(self._t.name), provider="gemini")
        self.assertIn("Biscuit", dispatch({"tool": "recall", "args": {"id": "dog-biscuit"}}, self.v, train))


class TestEngineTrains(unittest.TestCase):
    def test_defaults_by_provider(self):
        td = tempfile.mkdtemp()
        self.assertTrue(GenesisConfig(root=Path(td), provider="gemini").engine_trains)
        self.assertFalse(GenesisConfig(root=Path(td), provider="anthropic").engine_trains)
        self.assertFalse(GenesisConfig(root=Path(td), provider="openai").engine_trains)

    def test_unknown_provider_fails_closed(self):
        td = tempfile.mkdtemp()
        self.assertTrue(GenesisConfig(root=Path(td), provider="mystery").engine_trains)

    def test_explicit_override(self):
        td = tempfile.mkdtemp()
        # a user on a paid/non-training Gemini tier can override to private
        self.assertFalse(GenesisConfig(root=Path(td), provider="gemini", trains=False).engine_trains)


if __name__ == "__main__":
    unittest.main()
