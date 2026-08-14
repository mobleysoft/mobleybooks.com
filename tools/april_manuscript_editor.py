#!/usr/bin/env python3
"""Resumable, immutable-source editorial runner for approved MobleyBooks works."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

try:
    from .manuscript_auditor import audit_text, extract_text
except ImportError:
    from manuscript_auditor import audit_text, extract_text


HOME = Path.home()
CATALOG = HOME / "mobleybooks-com" / "catalog" / "publications.json"
PROJECT_ROOT = HOME / "mobleybooks-com"
OUTPUT_ROOT = HOME / ".local" / "share" / "mobleybooks" / "april-output"
SOURCE_ROOTS = (
    HOME,
    HOME / "reference" / "legacy-roots" / "mascom-prod" / "MASCOM" / "mascom_data",
    HOME / ".local" / "mnt" / "dell-users" / "Owner",
)
AUTHOR = "John Alexander Mobley"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def load_catalog(path: Path = CATALOG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_source(reference: str) -> Path:
    source = Path(reference).expanduser()
    if source.is_absolute() and source.is_file():
        return source
    for root in SOURCE_ROOTS:
        candidate = root / reference
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"source is not hydrated: {reference}")


def normalize_front_matter(text: str, title: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    text = re.sub(r"(?im)^\s*(?:by|author\s*:)\s*[^\n]{1,100}$", f"By {AUTHOR}", text, count=1)
    if not re.search(rf"(?im)^\s*{re.escape(title)}\s*$", text[:1000]):
        text = f"{title}\n\nBy {AUTHOR}\n\n{text}"
    elif AUTHOR.casefold() not in text[:1000].casefold():
        text = re.sub(
            rf"(?im)^(\s*{re.escape(title)}\s*)$",
            rf"\1\n\nBy {AUTHOR}",
            text,
            count=1,
        )
    return text.strip() + "\n"


def chapter_sections(text: str) -> list[str]:
    heading = re.compile(
        r"(?=(?:^|\n|\s{2,})(?:#{1,6}\s*)?Chapter\s+(?:\d+|[IVXLCDM]+)\s*(?::|\n))",
        flags=re.IGNORECASE,
    )
    starts = [match.start() for match in heading.finditer(text)]
    if not starts:
        return [text]
    starts = sorted(set(starts))
    sections = []
    if starts[0] > 0:
        sections.append(text[: starts[0]].strip())
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    return sections


def chunk_section(section: str, max_chars: int = 8_000) -> list[str]:
    if len(section) <= max_chars:
        return [section]
    paragraphs = [item.strip() for item in re.split(r"\n{2,}", section) if item.strip()]
    if len(paragraphs) == 1:
        paragraphs = [item.strip() for item in re.split(r"(?<=[.!?])\s+", section) if item.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for paragraph in paragraphs:
        if current and current_size + len(paragraph) + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0
        current.append(paragraph)
        current_size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def strip_model_wrappers(value: str) -> str:
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE).strip()
    value = re.sub(r"^```(?:markdown|text)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value).strip()
    return value


def validate_edit(source: str, edited: str) -> list[str]:
    failures: list[str] = []
    source_words = len(source.split())
    edited_words = len(edited.split())
    ratio = edited_words / source_words if source_words else 0
    if not 0.72 <= ratio <= 1.18:
        failures.append(f"word_count_ratio_{ratio:.3f}")
    if not edited.strip():
        failures.append("empty_output")
    audit = audit_text(edited)
    if audit["contamination"]:
        failures.append("output_contamination")
    if re.match(r"(?i)^(?:here(?:'|’)s|here is|certainly|of course)\b", edited.strip()):
        failures.append("model_preamble")
    return failures


def invoke_editor(prompt: str, *, port: int, max_tokens: int) -> str:
    mascom = str(HOME / "mascom")
    if mascom not in sys.path:
        sys.path.insert(0, mascom)
    from powerthon_runtime import _pwy_invoke_llm

    return _pwy_invoke_llm(
        prompt=prompt,
        system_prompt=(
            "You are A.P.R.I.L., John Alexander Mobley's conservative line editor. "
            "Preserve plot, scene order, facts, names, point of view, tense, and authorial intent. "
            "Repair grammar, typography, mojibake, accidental word spacing, repetitive phrasing, "
            "assistant-chat residue, and placeholder prose. Do not add a preface, critique, summary, "
            "new scene, or explanation. Return only the edited passage. /no_think"
        ),
        port=port,
        temperature=0.35,
        max_tokens=max_tokens,
    )


def edit_entry(entry: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    source = resolve_source(entry["source_ref"])
    original = normalize_front_matter(extract_text(source), entry["title"])
    source_hash = sha256_text(original)
    output_dir = args.output_root / entry["slug"]
    segment_dir = output_dir / "segments"
    output_dir.mkdir(parents=True, exist_ok=True)

    sections = chapter_sections(original)
    chunks = [chunk for section in sections for chunk in chunk_section(section, args.max_chars)]
    previous_tail = ""
    segment_records: list[dict[str, Any]] = []
    edited_chunks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        destination = segment_dir / f"{index:04d}.md"
        if destination.is_file() and not args.force:
            edited = destination.read_text(encoding="utf-8")
        else:
            prompt = (
                f"BOOK: {entry['title']}\nAUTHOR: {AUTHOR}\n"
                f"PASSAGE: {index} of {len(chunks)}\n"
                f"PREVIOUS CONTINUITY TAIL:\n{previous_tail[-900:]}\n\n"
                f"EDIT THIS PASSAGE:\n{chunk}"
            )
            edited = strip_model_wrappers(
                invoke_editor(prompt, port=args.port, max_tokens=args.max_tokens)
            )
            failures = validate_edit(chunk, edited)
            if failures:
                raise RuntimeError(f"segment {index} rejected: {', '.join(failures)}")
            atomic_write(destination, edited.strip() + "\n")
        previous_tail = edited
        edited_chunks.append(edited.strip())
        segment_records.append(
            {
                "index": index,
                "source_sha256": sha256_text(chunk),
                "output_sha256": sha256_text(edited),
                "source_words": len(chunk.split()),
                "output_words": len(edited.split()),
            }
        )
        atomic_write(
            output_dir / "checkpoint.json",
            json.dumps(
                {
                    "schema": "mobleybooks.april-editor-checkpoint.v1",
                    "title": entry["title"],
                    "author": AUTHOR,
                    "source": str(source),
                    "source_sha256": source_hash,
                    "segments_total": len(chunks),
                    "segments_completed": index,
                    "updated_at": utc_now(),
                },
                indent=2,
            )
            + "\n",
        )

    manuscript = "\n\n".join(edited_chunks).strip() + "\n"
    audit = audit_text(manuscript, source=str(source))
    if not audit["mechanical_gate_passed"]:
        raise RuntimeError("compiled manuscript failed: " + ", ".join(audit["failures"]))
    manuscript_path = output_dir / "manuscript.md"
    atomic_write(manuscript_path, manuscript)
    epub_path = output_dir / f"{entry['slug']}.epub"
    cover_path = PROJECT_ROOT / "assets" / "covers" / f"{entry['slug']}-cover-v1.png"
    command = [
        "pandoc",
        str(manuscript_path),
        "--from=markdown",
        "--to=epub3",
        "--metadata",
        f"title={entry['title']}",
        "--metadata",
        f"author={AUTHOR}",
    ]
    if cover_path.is_file():
        command.extend(["--epub-cover-image", str(cover_path)])
    command.extend(["--output", str(epub_path)])
    subprocess.run(command, check=True)
    release = {
        "schema": "mobleybooks.release-candidate.v1",
        "status": "candidate_pending_final_editorial_review",
        "title": entry["title"],
        "slug": entry["slug"],
        "author": AUTHOR,
        "source": str(source),
        "source_sha256": source_hash,
        "manuscript_sha256": sha256_text(manuscript),
        "epub_sha256": hashlib.sha256(epub_path.read_bytes()).hexdigest(),
        "cover": str(cover_path) if cover_path.is_file() else None,
        "cover_sha256": hashlib.sha256(cover_path.read_bytes()).hexdigest() if cover_path.is_file() else None,
        "segments": segment_records,
        "audit": audit,
        "created_at": utc_now(),
    }
    atomic_write(output_dir / "release-candidate.json", json.dumps(release, indent=2) + "\n")
    return release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--port", type=int, default=18087)
    parser.add_argument("--max-chars", type=int, default=8_000)
    parser.add_argument("--max-tokens", type=int, default=3_072)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    entries = {entry["slug"]: entry for entry in load_catalog(args.catalog)["titles"]}
    unknown = [slug for slug in args.slugs if slug not in entries]
    if unknown:
        parser.error("unknown catalog slugs: " + ", ".join(unknown))
    releases = [edit_entry(entries[slug], args) for slug in args.slugs]
    print(json.dumps(releases, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
