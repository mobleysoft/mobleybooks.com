#!/usr/bin/env python3
"""Mechanically gate manuscripts before editorial review or publication."""

from __future__ import annotations

import argparse
from collections import Counter
import html
import json
from pathlib import Path
import re
import zipfile


CONTAMINATION_PATTERNS = {
    "assistant_transcript": (
        r"\bCopilot\b",
        r"\bChatGPT\b",
        r"\bClaude can make mistakes\b",
        r"\bmessages remaining until\b",
        r"\bSend Message\b",
        r"\bYou\s+Continue(?:\s+with)?\b",
    ),
    "assistant_meta_prose": (
        r"\bIf you(?:'|’)d like to continue\b",
        r"\bplease let me know how to proceed\b",
        r"\bThe chapter ends with\b",
        r"\bChapter\s+\d+\s+(?:depicts|reflects|brings|culminates|concludes|unveils)\b",
        r"\bwould be generated here\b",
    ),
    "rendering_artifact": (
        r"\ufffd",
        r"(?:\u00e2\u0080|\u00c3[\u0080-\u00bf])",
        r"<x-extension-template\b",
        r"chrome-extension://",
    ),
}


def extract_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            payload = archive.read("word/document.xml").decode("utf-8", errors="replace")
        payload = re.sub(r"</w:p>", "\n", payload)
        payload = re.sub(r"<w:tab[^>]*/>", "\t", payload)
        payload = re.sub(r"<[^>]+>", "", payload)
        return html.unescape(payload)
    return html.unescape(path.read_text(encoding="utf-8", errors="replace"))


def normalized_sentence(sentence: str) -> str:
    return re.sub(r"[^a-z0-9']+", " ", sentence.casefold()).strip()


def split_sentences(text: str) -> list[str]:
    return [
        normalized
        for sentence in re.split(r"(?<=[.!?])(?:[\"'\u201d\u2019)]*)\s+", text)
        if len(normalized := normalized_sentence(sentence)) >= 40
    ]


def audit_text(text: str, *, source: str = "") -> dict:
    words = re.findall(r"\b[\w]+(?:['\u2019-][\w]+)*\b", text, flags=re.UNICODE)
    sentences = split_sentences(text)
    sentence_counts = Counter(sentences)
    duplicate_instances = sum(count - 1 for count in sentence_counts.values() if count > 1)
    duplicate_ratio = duplicate_instances / len(sentences) if sentences else 0.0

    contamination: dict[str, int] = {}
    for category, patterns in CONTAMINATION_PATTERNS.items():
        count = sum(len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in patterns)
        if count:
            contamination[category] = count

    chapter_matches = re.findall(
        r"(?:^|\n|\s)(?:#{1,6}\s*)?Chapter\s+(?:\d+|[IVXLCDM]+)(?=\s*[:\-]|\s+[A-Z])",
        text,
        flags=re.IGNORECASE,
    )
    stripped = text.rstrip()
    incomplete_ending = bool(
        re.search(r"(?:\bYou\s+continue\b|\bto be continued\b|\[CONTINUE\]|\.{3})\s*$", stripped, re.I)
        or (stripped and stripped[-1] not in ".!?\"'\u2019\u201d)]}")
    )

    failures: list[str] = []
    if len(words) < 1_000:
        failures.append("insufficient_manuscript_length")
    if contamination:
        failures.append("assistant_or_rendering_contamination")
    if duplicate_ratio > 0.05:
        failures.append("excessive_exact_sentence_repetition")
    if len(words) >= 5_000 and len(chapter_matches) < 3:
        failures.append("insufficient_detectable_structure")
    if incomplete_ending:
        failures.append("incomplete_ending_marker")

    return {
        "schema": "mobleybooks.manuscript-audit.v1",
        "source": source,
        "words": len(words),
        "sentences": len(sentences),
        "chapters_detected": len(chapter_matches),
        "exact_duplicate_sentence_instances": duplicate_instances,
        "exact_duplicate_sentence_ratio": round(duplicate_ratio, 4),
        "contamination": contamination,
        "incomplete_ending_marker": incomplete_ending,
        "mechanical_gate_passed": not failures,
        "failures": failures,
        "editorial_review_still_required": True,
    }


def audit_path(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return audit_text(extract_text(path), source=str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    reports = [audit_path(path) for path in args.paths]
    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        for report in reports:
            state = "PASS" if report["mechanical_gate_passed"] else "BLOCK"
            print(
                f"{state}\t{report['words']} words\t{report['chapters_detected']} chapters\t"
                f"{report['exact_duplicate_sentence_ratio']:.1%} duplicate sentences\t"
                f"{report['source']}"
            )
            for failure in report["failures"]:
                print(f"  - {failure}")
    return 0 if all(report["mechanical_gate_passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
