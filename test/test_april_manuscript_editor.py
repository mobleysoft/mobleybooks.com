from __future__ import annotations

import unittest

from tools import april_manuscript_editor as editor


class AprilManuscriptEditorTests(unittest.TestCase):
    def test_normalizes_author_without_overwriting_story(self) -> None:
        text = "Example Book\nBy Old Pen Name\n\nChapter 1: Start\nThe story begins."
        normalized = editor.normalize_front_matter(text, "Example Book")
        self.assertIn("By John Alexander Mobley", normalized)
        self.assertIn("The story begins.", normalized)

    def test_epub_markdown_adds_navigable_story_headings(self) -> None:
        source = "Book\n\nBy John Alexander Mobley\n\nChapter 1: Arrival\n\nText.\n\nEpilogue: Home\n\nEnd.\n"
        formatted = editor.epub_markdown(source)
        self.assertIn("# Chapter 1\n", formatted)
        self.assertIn("# Epilogue\n", formatted)
        self.assertIn("Arrival", formatted)
        self.assertIn("Home", formatted)
        self.assertIn("By John Alexander Mobley", formatted)

    def test_splits_flattened_single_line_chapters(self) -> None:
        source = (
            "Book by Author Chapter 1: Arrival The first scene unfolds. "
            "Chapter 2: Departure The second scene unfolds. "
            "Epilogue: Home The story closes."
        )
        sections = editor.chapter_sections(source)
        self.assertEqual(4, len(sections))
        self.assertTrue(sections[1].startswith("Chapter 1:"))
        self.assertTrue(sections[2].startswith("Chapter 2:"))
        self.assertTrue(sections[3].startswith("Epilogue:"))

        formatted = editor.epub_markdown(source)
        self.assertIn("# Chapter 1\n", formatted)
        self.assertIn("# Chapter 2\n", formatted)
        self.assertIn("# Epilogue\n", formatted)

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
