import unittest

from genesis_memory import frontmatter


class TestFrontmatter(unittest.TestCase):
    def test_roundtrip_scalars(self):
        meta = {"id": "x", "description": "a thing", "kind": "user", "status": "active"}
        parsed, body = frontmatter.parse(frontmatter.serialize(meta, "body here"))
        self.assertEqual(parsed["id"], "x")
        self.assertEqual(parsed["description"], "a thing")
        self.assertEqual(parsed["kind"], "user")
        self.assertEqual(body, "body here")

    def test_no_frontmatter_is_all_body(self):
        meta, body = frontmatter.parse("just a body, no fences")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just a body, no fences")

    def test_tolerant_preserves_colonless_line(self):
        meta, body = frontmatter.parse("---\nid: x\nweird line without colon\n---\nbody")
        self.assertEqual(meta["id"], "x")
        self.assertIn("weird line without colon", meta.get("_raw", []))
        self.assertEqual(body, "body")

    def test_multiline_scalar_is_folded_not_orphaned(self):
        # the verified corruption: a newline in a value used to orphan the 2nd line
        meta = {"id": "x", "description": "line one\nline two", "kind": "user"}
        parsed, _ = frontmatter.parse(frontmatter.serialize(meta, "b"))
        self.assertNotIn("\n", parsed["description"])
        self.assertIn("line one", parsed["description"])
        self.assertIn("line two", parsed["description"])
        self.assertNotIn("_raw", parsed)  # nothing got orphaned


if __name__ == "__main__":
    unittest.main()
