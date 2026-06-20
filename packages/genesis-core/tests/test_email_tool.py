"""Tests for email_tool.py (no SMTP calls; dry-run path only)."""

import json
import tempfile
import unittest
from pathlib import Path

from genesis_core.email_tool import (
    DAILY_CAP,
    EMAIL_CONFIRM_TOOL,
    EMAIL_DRAFT_TOOL,
    _increment_sent,
    get_sent_today,
    load_draft,
    save_draft,
    tool_email_confirm,
    tool_email_draft,
)


ALLOWED = ["help@example.com"]


class TestDailyLedger(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_zero_before_any_send(self):
        self.assertEqual(get_sent_today(self.root), 0)

    def test_increment_returns_new_count(self):
        self.assertEqual(_increment_sent(self.root), 1)
        self.assertEqual(_increment_sent(self.root), 2)
        self.assertEqual(get_sent_today(self.root), 2)


class TestDraftQueue(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_save_and_load(self):
        did = save_draft(self.root, "help@example.com", "Hi", "Hello there")
        draft = load_draft(self.root, did)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["to"], "help@example.com")
        self.assertEqual(draft["subject"], "Hi")
        self.assertEqual(draft["body"], "Hello there")

    def test_missing_draft_returns_none(self):
        self.assertIsNone(load_draft(self.root, "nonexistent"))


class TestToolEmailDraft(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_allowed_recipient_drafts_ok(self):
        result = tool_email_draft(
            "help@example.com", "Test", "Body text", ALLOWED, self.root
        )
        self.assertIn("Draft saved", result)
        self.assertIn("id:", result)
        self.assertIn("Test", result)

    def test_blocked_recipient_denied(self):
        result = tool_email_draft(
            "stranger@evil.com", "Test", "Body", ALLOWED, self.root
        )
        self.assertIn("denied", result)
        self.assertIn("allowed", result.lower())

    def test_empty_subject_rejected(self):
        result = tool_email_draft(
            "help@example.com", "", "Body", ALLOWED, self.root
        )
        self.assertIn("error", result)

    def test_empty_body_rejected(self):
        result = tool_email_draft(
            "help@example.com", "Subj", "", ALLOWED, self.root
        )
        self.assertIn("error", result)

    def test_daily_cap_enforced(self):
        # Exhaust the cap
        for _ in range(DAILY_CAP):
            _increment_sent(self.root)
        result = tool_email_draft(
            "help@example.com", "Over cap", "Body", ALLOWED, self.root
        )
        self.assertIn("denied", result)
        self.assertIn("cap", result)

    def test_draft_preview_shows_recipient_and_subject(self):
        result = tool_email_draft(
            "help@example.com", "Hello there", "Body", ALLOWED, self.root
        )
        self.assertIn("help@example.com", result)
        self.assertIn("Hello there", result)


class TestToolEmailConfirm(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.secrets = Path(tempfile.mkdtemp()) / "secrets"
        self.secrets.mkdir()

    def test_missing_draft_returns_error(self):
        result = tool_email_confirm("badid123", self.root, self.secrets)
        self.assertIn("error", result)
        self.assertIn("badid123", result)

    def test_no_smtp_config_returns_helpful_message(self):
        # Save a draft but provide no smtp config
        did = save_draft(self.root, "help@example.com", "Sub", "Body")
        # Patch load_draft to return a draft
        from genesis_core import email_tool as et
        orig = et.load_draft
        et.load_draft = lambda r, d: {"id": d, "to": "a@b.com", "subject": "S", "body": "B"}
        try:
            result = tool_email_confirm("fakeid", self.root, self.secrets)
        finally:
            et.load_draft = orig
        self.assertIn("SMTP not configured", result)


class TestToolSpecs(unittest.TestCase):
    def test_specs_exist(self):
        for spec in [EMAIL_DRAFT_TOOL, EMAIL_CONFIRM_TOOL]:
            self.assertIsNotNone(spec.name)
            self.assertIn("properties", spec.input_schema)


if __name__ == "__main__":
    unittest.main()
