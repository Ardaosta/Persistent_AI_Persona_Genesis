import unittest

from genesis_backend import AnthropicBackend, BackendCaps, GeminiBackend, OpenAIBackend, ToolCall
from genesis_backend.anthropic_backend import parse_response as parse_anthropic
from genesis_backend.openai_backend import parse_response as parse_openai
from genesis_backend.gemini_backend import _extract_parts, _history_to_contents


class TestBackendParse(unittest.TestCase):
    def test_anthropic_joins_text_blocks_and_usage(self):
        c = parse_anthropic({
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}],
            "usage": {"input_tokens": 10, "output_tokens": 2},
        })
        self.assertEqual(c.text, "hello world")
        self.assertEqual(c.model, "claude-sonnet-4-6")
        self.assertEqual(c.input_tokens, 10)
        self.assertEqual(c.output_tokens, 2)

    def test_openai_pulls_message_and_usage(self):
        c = parse_openai({
            "model": "gpt-x",
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        })
        self.assertEqual(c.text, "hi")
        self.assertEqual(c.model, "gpt-x")
        self.assertEqual(c.input_tokens, 5)
        self.assertEqual(c.output_tokens, 1)

    def test_caps_report_provider_and_tools(self):
        a = AnthropicBackend("sk-test").caps()
        self.assertEqual(a.provider, "anthropic")
        self.assertTrue(a.supports_tools)
        o = OpenAIBackend("sk-test", default_model="gpt-x").caps()
        self.assertEqual(o.provider, "openai")
        self.assertEqual(o.default_model, "gpt-x")
        self.assertIsInstance(a, BackendCaps)
        g = GeminiBackend("AQ.test", default_model="gemini-2.5-flash").caps()
        self.assertEqual(g.provider, "gemini")
        self.assertTrue(g.supports_tools)
        self.assertEqual(g.default_model, "gemini-2.5-flash")


class TestGeminiWire(unittest.TestCase):
    def test_extract_text_and_function_call(self):
        text, calls = _extract_parts({
            "candidates": [{"content": {"parts": [
                {"text": "sure"},
                {"functionCall": {"name": "set_palette", "args": {"base": "#0A1128", "accent": "#0077B6"}}},
            ]}}],
        })
        self.assertEqual(text, "sure")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "set_palette")
        self.assertEqual(calls[0].input["accent"], "#0077B6")
        self.assertTrue(calls[0].id)  # synthesized, non-empty

    def test_extract_empty_response(self):
        text, calls = _extract_parts({"candidates": [{}]})
        self.assertEqual(text, "")
        self.assertEqual(calls, [])

    def test_history_roles_and_function_response_name(self):
        history = [
            {"role": "user", "text": "hi"},
            {"role": "assistant", "text": "", "tool_calls": [ToolCall(id="set_palette-1", name="set_palette", input={"base": "#000", "accent": "#fff"})]},
            {"role": "tool", "results": [{"id": "set_palette-1", "content": "applied: setPalette"}]},
        ]
        contents = _history_to_contents(history)
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[1]["role"], "model")
        self.assertIn("functionCall", contents[1]["parts"][0])
        # tool result becomes a user content carrying functionResponse keyed by NAME
        self.assertEqual(contents[2]["role"], "user")
        fr = contents[2]["parts"][0]["functionResponse"]
        self.assertEqual(fr["name"], "set_palette")
        self.assertEqual(fr["response"]["result"], "applied: setPalette")


if __name__ == "__main__":
    unittest.main()
