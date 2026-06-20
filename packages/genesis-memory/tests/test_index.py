import unittest

from genesis_memory import Fact, index


def _facts(n, desc_len=120):
    return [Fact(id=f"f{i:03d}", kind="reference", description="x" * desc_len) for i in range(n)]


class TestIndex(unittest.TestCase):
    def test_build_one_line_per_fact(self):
        text = index.build(_facts(5, 20))
        self.assertEqual(len(text.splitlines()), 5)

    def test_budget_never_drops_an_entry(self):
        text, shrunk = index.enforce_budget(_facts(40, 200), max_bytes=3000)
        self.assertTrue(shrunk)
        self.assertEqual(len(text.splitlines()), 40)  # clip descriptions, never drop pointers
        self.assertLessEqual(len(text.encode("utf-8")), 3000)

    def test_under_budget_untouched(self):
        text, shrunk = index.enforce_budget(_facts(3, 20), max_bytes=24_000)
        self.assertFalse(shrunk)
        self.assertNotIn("…", text)

    def test_entry_line_is_link_safe(self):
        # brackets + newline in a description must not break the markdown link
        f = Fact(id="t", kind="user", description="loves ] brackets [ and\nnewlines")
        line = index.entry_line(f)
        self.assertEqual(len(line.splitlines()), 1)  # single line
        self.assertEqual(line.count("["), 1)  # only the link's own opener
        self.assertEqual(line.count("]"), 1)  # only the link's own closer


if __name__ == "__main__":
    unittest.main()
