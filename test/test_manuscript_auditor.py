from __future__ import annotations

import unittest

from tools import manuscript_auditor


class ManuscriptAuditorTests(unittest.TestCase):
    def test_blocks_assistant_transcript_contamination(self) -> None:
        text = ("Chapter 1: Arrival\n" + "A complete sentence about a character. " * 1_000)
        text += "\nCopilot\nIf you'd like to continue, please let me know how to proceed."
        report = manuscript_auditor.audit_text(text)
        self.assertFalse(report["mechanical_gate_passed"])
        self.assertIn("assistant_or_rendering_contamination", report["failures"])

    def test_clean_structured_manuscript_reaches_editorial_gate(self) -> None:
        chapters = []
        for chapter in range(1, 5):
            prose = " ".join(
                f"Character {chapter} makes consequential choice number {index}."
                for index in range(250)
            )
            chapters.append(f"Chapter {chapter}: Movement\n{prose}")
        report = manuscript_auditor.audit_text("\n".join(chapters))
        self.assertTrue(report["mechanical_gate_passed"])
        self.assertTrue(report["editorial_review_still_required"])

    def test_blocks_mojibake_and_truncated_ending(self) -> None:
        text = "Chapter 1: Flood\n" + ("The city\u00e2\u0080\u0099s lights moved under water. " * 1_000)
        text += "What if we find"
        report = manuscript_auditor.audit_text(text)
        self.assertFalse(report["mechanical_gate_passed"])
        self.assertIn("assistant_or_rendering_contamination", report["failures"])
        self.assertIn("incomplete_ending_marker", report["failures"])

    def test_blocks_book_length_payload_flattened_to_one_line(self) -> None:
        chapters = " ".join(
            f"Chapter {chapter}: Movement " + ("A complete sentence follows. " * 400)
            for chapter in range(1, 6)
        )
        report = manuscript_auditor.audit_text(chapters)
        self.assertFalse(report["mechanical_gate_passed"])
        self.assertIn("flattened_layout", report["failures"])
        self.assertEqual(1, report["nonempty_lines"])

    def test_counts_bare_heading_followed_by_quoted_dialogue(self) -> None:
        chapters = []
        for chapter in range(1, 4):
            prose = '"No," the investigator said. ' * 400
            chapters.append(f"Chapter {chapter}\n\n{prose}")
        report = manuscript_auditor.audit_text("\n\n".join(chapters))
        self.assertEqual(3, report["chapters_detected"])
        self.assertTrue(report["mechanical_gate_passed"])


if __name__ == "__main__":
    unittest.main()
