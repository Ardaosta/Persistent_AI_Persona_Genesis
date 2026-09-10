import tempfile
import unittest
from pathlib import Path

from genesis_headlines.resolver import resolve
from genesis_headlines.scaffold import new_cluster, slugify


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_slugify(self):
        self.assertEqual(slugify("Voice / Portal!"), "voice-portal")
        with self.assertRaises(ValueError):
            slugify("!!!")

    def test_creates_well_formed_cluster(self):
        dest = new_cluster(
            "my-thing",
            aliases=["thing", "widget"],
            paths=["repos/thing"],
            title="My Thing",
            today="2026-07-06",
            dir=str(self.dir),
        )
        self.assertTrue(dest.exists())
        text = dest.read_text(encoding="utf-8")
        self.assertIn("cluster: my-thing", text)
        self.assertIn("HEADLINES — My Thing", text)

    def test_scaffold_matches_by_its_aliases(self):
        new_cluster("my-thing", aliases=["widget"], today="2026-07-06", dir=str(self.dir))
        hits = resolve("fix the widget", dir=str(self.dir))
        self.assertEqual([h.slug for h in hits], ["my-thing"])

    def test_refuses_overwrite(self):
        new_cluster("dup", today="2026-07-06", dir=str(self.dir))
        with self.assertRaises(FileExistsError):
            new_cluster("dup", today="2026-07-06", dir=str(self.dir))


if __name__ == "__main__":
    unittest.main()
