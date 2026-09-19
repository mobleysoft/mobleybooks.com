#!/usr/bin/env python3
"""Reflow a flattened (single-line) manuscript into real paragraphs.

Several MobleyBooks source manuscripts (imported from an external
generation pipeline) lost all paragraph structure - the entire book is
one unbroken line. manuscript_auditor.py correctly flags this
("flattened_layout") since it's genuinely unreadable as delivered.

This is a disclosed, mechanical HEURISTIC, not a reconstruction of the
original author's exact paragraph breaks (those are gone - there is no
way to recover them). Real content (every word) is preserved exactly -
only whitespace/newlines change, verified by asserting the reflowed
text, with all whitespace collapsed, equals the original with all
whitespace collapsed, before any write happens.

Design note: an earlier version of this tool tried to detect where a
chapter TITLE ends and body prose begins (e.g. "Chapter 2: A Day in
Thraedon The dawn was..."), using capitalization heuristics. That's
genuinely ambiguous without external reference (is "The" the last word
of a Title-Case heading, or the first word of the next sentence?) and
risked silently misplacing real words. Deliberately not attempted -
instead, a paragraph break is inserted right at "Chapter N:"/"Epilogue:"
and the title flows into the chapter's opening paragraph unseparated.
Imperfect typesetting, zero risk of relocating content.
"""
import argparse
import re
import sys
from pathlib import Path

CHAPTER_ANCHOR_RE = re.compile(r"(?=\b(?:Chapter\s+\d+|Epilogue)\s*:)")
# Matches sentence CONTENT (including its own terminal punctuation and any
# trailing closing quote/paren) rather than a boundary to discard - a real
# bug in an earlier version used re.split() on a boundary pattern that
# included the closing quote character, which re.split() then silently
# dropped from the output entirely (confirmed the hard way: caught by the
# tool's own before-write content-equality check, not by inspection).
SENTENCE_RE = re.compile(r'\S.*?[.!?]+["\'’”)]*(?=\s|$)', re.DOTALL)
QUOTE_CHARS = set('"“”‘’\'')


def split_sentences(text):
    matches = list(SENTENCE_RE.finditer(text))
    sentences = [m.group().strip() for m in matches]
    # Any trailing fragment with no terminal punctuation (a genuinely
    # unfinished sentence, e.g. a manuscript that just cuts off) - keep it
    # rather than silently drop it.
    last_end = matches[-1].end() if matches else 0
    remainder = text[last_end:].strip()
    if remainder:
        sentences.append(remainder)
    return [s for s in sentences if s]


def is_dialogue(sentence):
    return sentence[:1] in QUOTE_CHARS


def reflow_chunk(text, sentences_per_paragraph=3):
    sentences = split_sentences(text)
    if not sentences:
        return ""
    lines = []
    paragraph = []
    prev_is_dialogue = None
    for sentence in sentences:
        cur_is_dialogue = is_dialogue(sentence)
        if paragraph and (cur_is_dialogue != prev_is_dialogue or len(paragraph) >= sentences_per_paragraph):
            lines.append(" ".join(paragraph))
            lines.append("")
            paragraph = []
        paragraph.append(sentence)
        prev_is_dialogue = cur_is_dialogue
    if paragraph:
        lines.append(" ".join(paragraph))
        lines.append("")
    return "\n".join(lines)


def reflow(text, sentences_per_paragraph=3):
    chunks = [c.strip() for c in CHAPTER_ANCHOR_RE.split(text) if c.strip()]
    out = []
    for chunk in chunks:
        out.append(reflow_chunk(chunk, sentences_per_paragraph))
        out.append("")
    return "\n".join(out).strip() + "\n"


def normalize_for_compare(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--write", action="store_true", help="write result back to the file (default: print only)")
    args = parser.parse_args()

    original = args.path.read_text(encoding="utf-8")
    reflowed = reflow(original)

    if normalize_for_compare(original) != normalize_for_compare(reflowed):
        print("REFUSING to write: reflowed text does not contain exactly the same words as the original.", file=sys.stderr)
        orig_norm = normalize_for_compare(original)
        new_norm = normalize_for_compare(reflowed)
        for i, (a, b) in enumerate(zip(orig_norm, new_norm)):
            if a != b:
                print(f"first diff at char {i}: original={orig_norm[max(0,i-40):i+40]!r}", file=sys.stderr)
                print(f"                        reflowed={new_norm[max(0,i-40):i+40]!r}", file=sys.stderr)
                break
        else:
            print(f"length differs: original={len(orig_norm)} reflowed={len(new_norm)}", file=sys.stderr)
        return 1

    if args.write:
        args.path.write_text(reflowed, encoding="utf-8")
        print(f"wrote {args.path} ({len(reflowed)} chars, content-verified identical modulo whitespace)")
    else:
        print(reflowed[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
