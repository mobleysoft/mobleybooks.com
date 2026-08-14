from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import extract_release_arc


class ExtractReleaseArcTests(unittest.TestCase):
    def test_extracts_focused_arc_and_retains_continuation(self) -> None:
        source_text = (
            "Example\n\nBy John Alexander Mobley\n\n"
            "Chapter 1:\n\n" + "one " * 100 + "\n\n"
            "Chapter 2:\n\n" + "two " * 100 + "\n\n"
            "Chapter 3:\n\n" + "three " * 100
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.txt"
            source.write_text(source_text, encoding="utf-8")
            output = Path(directory) / "output"
            entry = {
                "slug": "example",
                "title": "Example",
                "author": extract_release_arc.AUTHOR,
                "source_ref": "source.txt",
            }
            with patch.object(extract_release_arc, "resolve_source", return_value=source):
                record = extract_release_arc.extract_arc(entry, chapter_count=2, output_root=output)

            focused = (output / "example" / "manuscript.md").read_text(encoding="utf-8")
            continuation = (output / "example" / "continuation-seeds.md").read_text(encoding="utf-8")
            self.assertIn("Chapter 2", focused)
            self.assertNotIn("Chapter 3", focused)
            self.assertIn("Chapter 3", continuation)
            self.assertEqual(1, record["continuation_sections_retained"])
            self.assertEqual(extract_release_arc.AUTHOR, record["author"])


if __name__ == "__main__":
    unittest.main()
