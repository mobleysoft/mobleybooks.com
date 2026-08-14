from __future__ import annotations

import unittest

from tools import april_manuscript_editor as editor


class AprilManuscriptEditorTests(unittest.TestCase):
    def test_normalizes_author_without_overwriting_story(self) -> None:
        text = "Example Book\nBy Old Pen Name\n\nChapter 1: Start\nThe story begins."
        normalized = editor.normalize_front_matter(text, "Example Book")
        self.assertIn("By John Alexander Mobley", normalized)
        self.assertIn("The story begins.", normalized)

    def test_splits_large_section_without_losing_text(self) -> None:
        source = " ".join(f"Sentence {index} is deliberately distinct." for index in range(300))
        chunks = editor.chunk_section(source, max_chars=800)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(source.split()), " ".join(" ".join(chunks).split()))

    def test_rejects_truncated_model_output(self) -> None:
        source = "One complete sentence. " * 200
        failures = editor.validate_edit(source, "Too short.")
        self.assertTrue(any(item.startswith("word_count_ratio_") for item in failures))


if __name__ == "__main__":
    unittest.main()
