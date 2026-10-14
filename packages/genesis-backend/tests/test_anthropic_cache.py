import copy
import unittest
from unittest import mock

from genesis_backend import AnthropicBackend, ToolCall, ToolSpec
from genesis_backend import anthropic_backend as ab

EPHEMERAL = {"type": "ephemeral"}


def _breakpoints(payload: dict) -> list[tuple]:
    """Every (location, index) carrying cache_control anywhere in the request."""
    found = []
    sys = payload.get("system")
    if isinstance(sys, list):
        found += [("system", i) for i, b in enumerate(sys) if "cache_control" in b]
    found += [("tools", i) for i, t in enumerate(payload.get("tools", [])) if "cache_control" in t]
    for mi, m in enumerate(payload["messages"]):
        if isinstance(m["content"], list):
            found += [("messages", mi, bi) for bi, b in enumerate(m["content"]) if "cache_control" in b]
    if "cache_control" in payload:
        found.append(("top",))
    return found


class TestAnthropicHistoryCache(unittest.TestCase):
    def _run(self, history):
        captured = {}

        def fake_post(url, headers, payload):
            captured["payload"] = copy.deepcopy(payload)
            return {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
                    "usage": {"input_tokens": 7, "output_tokens": 1,
                              "cache_creation_input_tokens": 100, "cache_read_input_tokens": 2000}}

        tools = [ToolSpec("remember", "save a fact", {"type": "object", "properties": {}})]
        with mock.patch.object(ab, "http_post_json", side_effect=fake_post):
            r = AnthropicBackend("sk-test").run_turn(history, system="SYS", tools=tools)
        return captured["payload"], r

    def test_single_breakpoint_on_last_user_text(self):
        history = [
            {"role": "user", "text": "hi"},
            {"role": "assistant", "text": "hello", "tool_calls": []},
            {"role": "user", "text": "tell me more"},
        ]
        before = copy.deepcopy(history)
        payload, r = self._run(history)
        self.assertEqual(_breakpoints(payload), [("messages", 2, 0)])
        last = payload["messages"][-1]["content"]
        self.assertEqual(last, [{"type": "text", "text": "tell me more", "cache_control": EPHEMERAL}])
        # earlier turns keep their original shape (prefix stays byte-identical turn to turn)
        self.assertEqual(payload["messages"][0]["content"], "hi")
        # system stays a plain string, ahead of history, untouched
        self.assertEqual(payload["system"], "SYS")
        # stored history is never mutated
        self.assertEqual(history, before)
        self.assertEqual(r.cache_creation_input_tokens, 100)
        self.assertEqual(r.cache_read_input_tokens, 2000)

    def test_breakpoint_on_trailing_tool_result(self):
        history = [
            {"role": "user", "text": "remember I like tea"},
            {"role": "assistant", "text": "", "tool_calls": [ToolCall(id="t1", name="remember", input={})]},
            {"role": "tool", "results": [{"id": "a", "content": "saved"}, {"id": "t1", "content": "saved"}]},
        ]
        payload, _ = self._run(history)
        self.assertEqual(_breakpoints(payload), [("messages", 2, 1)])
        self.assertEqual(payload["messages"][-1]["content"][1]["type"], "tool_result")
        # earlier assistant block untouched
        self.assertNotIn("cache_control", payload["messages"][1]["content"][0])

    def test_prefix_of_next_turn_matches_this_turn(self):
        # Turn N's messages (minus the marker) must equal the first N messages of turn N+1.
        h1 = [{"role": "user", "text": "a"}]
        p1, _ = self._run(h1)
        h2 = h1 + [{"role": "assistant", "text": "b", "tool_calls": []}, {"role": "user", "text": "c"}]
        p2, _ = self._run(h2)
        self.assertEqual(p1["system"], p2["system"])
        self.assertEqual(p1["tools"], p2["tools"])
        m1 = p1["messages"][0]["content"][0]
        self.assertEqual(m1.pop("cache_control"), EPHEMERAL)
        self.assertEqual([m1], [{"type": "text", "text": p2["messages"][0]["content"]}])

    def test_empty_history_passthrough(self):
        self.assertEqual(ab._with_history_cache([]), [])


if __name__ == "__main__":
    unittest.main()
