"""Does a document obey the rules it itself declares?

An em-dash was authored into the TITLE of an operating manual whose own text
bans em-dashes. It was only ever noticed because it turned into mojibake on a
Windows console, which is to say it was found by accident.
"""

import tempfile
import unittest
from pathlib import Path

from genesis_memory import selflint

EM = "—"


class TestTheIncident(unittest.TestCase):
    def test_a_title_breaking_the_documents_own_rule(self):
        doc = f"# The operating manual {EM} how I work\n\nNo emdashes. Use commas instead.\n"
        r = selflint.lint_text(doc)
        self.assertIn("em-dash", r["declared"])
        self.assertEqual([v["line"] for v in r["violations"]], [1])

    def test_the_rule_must_be_declared_to_be_enforced(self):
        """No opinions. A document that never bans em-dashes may use them."""
        doc = f"# A title {EM} with a dash\n\nNothing here forbids anything.\n"
        r = selflint.lint_text(doc)
        self.assertEqual(r["declared"], [])
        self.assertEqual(r["violations"], [])

    def test_mojibake_risk_is_reported_even_with_no_rule(self):
        doc = f"# A title {EM} with a dash\n"
        self.assertTrue(selflint.lint_text(doc)["non_ascii"])


class TestQuoteAwareness(unittest.TestCase):
    """A checker that cannot tell the statement of a rule from a breach of it
    reports the rulebook as the offender, and then people route around it."""

    def test_the_line_declaring_the_rule_is_not_itself_a_violation(self):
        doc = f"# Manual\n\nNo em-dashes ({EM}). Use commas instead.\n"
        r = selflint.lint_text(doc)
        self.assertIn("em-dash", r["declared"])
        self.assertEqual(r["violations"], [], "the rule quoting its own example is not a breach")

    def test_but_a_real_violation_elsewhere_still_lands(self):
        doc = f"# Manual\n\nNo em-dashes ({EM}). Use commas.\n\nI care {EM} a lot.\n"
        r = selflint.lint_text(doc)
        self.assertEqual([v["line"] for v in r["violations"]], [5])

    def test_a_banned_word_declaration_may_name_the_word(self):
        doc = 'Never use the word "utilize".\n'
        r = selflint.lint_text(doc)
        self.assertIn("word:utilize", r["declared"])
        self.assertEqual(r["violations"], [])


class TestItDoesNotCryWolf(unittest.TestCase):
    def test_code_blocks_are_exempt_from_prose_rules(self):
        doc = 'No exclamation marks.\n\n```sh\necho "done!"\n```\n'
        r = selflint.lint_text(doc)
        self.assertIn("exclamation", r["declared"])
        self.assertEqual(r["violations"], [], "an ! in a shell snippet is not a tone violation")

    def test_prose_exclamation_still_lands_when_declared(self):
        doc = "No exclamation marks.\n\nGreat news!\n"
        self.assertEqual([v["line"] for v in selflint.lint_text(doc)["violations"]], [3])

    def test_an_unquoted_word_ban_is_not_inferred(self):
        """Without quotes it cannot be told from ordinary prose about words."""
        doc = "Never use jargon when a plain word will do.\n\nWe use jargon here.\n"
        self.assertEqual(selflint.lint_text(doc)["declared"], [])

    def test_a_clean_document_passes(self):
        doc = 'No emdashes. No emoji.\n\nPlain prose, commas only, nothing fancy.\n'
        r = selflint.lint_text(doc)
        self.assertEqual(len(r["declared"]), 2)
        self.assertEqual(r["violations"], [])
        self.assertEqual(r["non_ascii"], [])


class TestOverAVault(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_findings_name_the_document(self):
        (self.vault / "soul").mkdir(parents=True)
        (self.vault / "soul" / "manual.md").write_text(
            f"# Manual {EM} here\n\nNo emdashes.\n", encoding="utf-8")
        r = selflint.lint_vault(self.vault)
        self.assertEqual(r["docs"], 1)
        self.assertEqual(r["violations"][0]["doc"], "soul/manual.md")
        self.assertIn("soul/manual.md:1", selflint.render(r))

    def test_an_empty_vault_is_not_an_error(self):
        r = selflint.lint_vault(self.vault)
        self.assertEqual((r["docs"], r["violations"]), (0, []))


if __name__ == "__main__":
    unittest.main()
