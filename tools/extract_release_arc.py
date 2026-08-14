#!/usr/bin/env python3
"""Extract a focused first-edition arc while preserving continuation material."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

try:
    from .april_manuscript_editor import (
        AUTHOR,
        CATALOG,
        chapter_sections,
        load_catalog,
        normalize_front_matter,
        resolve_source,
    )
    from .manuscript_auditor import audit_text, extract_text
except ImportError:
    from april_manuscript_editor import (
        AUTHOR,
        CATALOG,
        chapter_sections,
        load_catalog,
        normalize_front_matter,
        resolve_source,
    )
    from manuscript_auditor import audit_text, extract_text


DEFAULT_OUTPUT_ROOT = Path.home() / ".local" / "share" / "mobleybooks" / "release-arcs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    temporary.replace(path)


def extract_arc(
    entry: dict[str, Any],
    *,
    chapter_count: int,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    if entry.get("author") != AUTHOR:
        raise ValueError(f"{entry.get('slug')}: author must be {AUTHOR}")
    source = resolve_source(str(entry["source_ref"]))
    manuscript = normalize_front_matter(extract_text(source), str(entry["title"]))
    sections = chapter_sections(manuscript)
    has_front_matter = bool(sections and not sections[0].lstrip().casefold().startswith(("chapter", "prologue")))
    offset = 1 if has_front_matter else 0
    available_chapters = len(sections) - offset
    if chapter_count < 1 or chapter_count > available_chapters:
        raise ValueError(
            f"{entry['slug']}: requested {chapter_count} chapters; source has {available_chapters}"
        )

    selected_end = offset + chapter_count
    selected = sections[:selected_end]
    continuation = sections[selected_end:]
    focused = "\n\n".join(section.strip() for section in selected if section.strip()).strip() + "\n"
    retained = "\n\n".join(section.strip() for section in continuation if section.strip()).strip()
    output_dir = output_root / str(entry["slug"])
    manuscript_path = output_dir / "manuscript.md"
    continuation_path = output_dir / "continuation-seeds.md"
    atomic_text(manuscript_path, focused)
    atomic_text(
        continuation_path,
        (
            f"# Continuation seeds retained from {entry['title']}\n\n"
            f"Source: {source}\n\n"
            f"These chapters are excluded from the focused first edition, not deleted.\n\n"
            f"{retained}\n"
        ),
    )
    audit = audit_text(focused, source=str(source))
    record = {
        "schema": "mobleybooks.release-arc.v1",
        "slug": entry["slug"],
        "title": entry["title"],
        "author": AUTHOR,
        "source": str(source),
        "source_sha256": sha256_text(manuscript),
        "selected_chapters": chapter_count,
        "continuation_sections_retained": len(continuation),
        "focused_words": len(focused.split()),
        "continuation_words": len(retained.split()),
        "manuscript": str(manuscript_path),
        "manuscript_sha256": sha256_text(focused),
        "continuation": str(continuation_path),
        "continuation_sha256": sha256_text(retained),
        "audit": audit,
        "created_at": utc_now(),
    }
    atomic_text(output_dir / "arc.json", json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--chapters", type=int, required=True)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    entries = {entry["slug"]: entry for entry in load_catalog(args.catalog)["titles"]}
    if args.slug not in entries:
        parser.error(f"unknown catalog slug: {args.slug}")
    print(
        json.dumps(
            extract_arc(
                entries[args.slug],
                chapter_count=args.chapters,
                output_root=args.output_root,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
