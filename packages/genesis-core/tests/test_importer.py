"""Seed-pack import: facts land through the blessed write path; soul is refused."""

import tempfile
import unittest
from pathlib import Path

from genesis_core.importer import import_pack
from genesis_memory import Vault


class TestImport(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        base = Path(self._td.name)
        self.vault = base / "vault"
        self.pack = base / "pack"
        self.pack.mkdir()

    def tearDown(self):
        self._td.cleanup()

    def _w(self, name, text):
        (self.pack / name).write_text(text, encoding="utf-8")

    def test_imports_and_refuses_soul(self):
        self._w("what.md", "---\nid: proj-what\nkind: project\ndescription: what the project is\n---\nBody.\n")
        self._w("README.md", "# not a fact\n")
        self._w("self.md", "---\nid: me\nkind: soul\ndescription: a shipped self\n---\nno\n")
        self._w("nodesc.md", "---\nid: x\nkind: reference\n---\nbody\n")
        out = import_pack(self.vault, self.pack)
        self.assertEqual(out["written"], ["project/proj-what"])
        reasons = dict(out["skipped"])
        self.assertIn("cannot author a self", reasons["self.md"])
        self.assertIn("missing description", reasons["nodesc.md"])
        self.assertNotIn("README.md", reasons)
        f = Vault(self.vault).get("proj-what")
        self.assertEqual(f.description, "what the project is")
        self.assertIn("Body", f.body)

    def test_rerun_updates_not_duplicates(self):
        self._w("a.md", "---\nid: a\nkind: reference\ndescription: v1\n---\n")
        import_pack(self.vault, self.pack)
        self._w("a.md", "---\nid: a\nkind: reference\ndescription: v2\n---\n")
        import_pack(self.vault, self.pack)
        facts = list(Vault(self.vault).iter_facts())
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].description, "v2")

    def test_missing_dir_is_reported_not_raised(self):
        out = import_pack(self.vault, self.pack / "nope")
        self.assertEqual(out["written"], [])
        self.assertEqual(len(out["skipped"]), 1)


if __name__ == "__main__":
    unittest.main()
