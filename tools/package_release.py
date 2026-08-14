#!/usr/bin/env python3
"""Package mechanically clean MobleyBooks manuscripts without rewriting sources."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

try:
    from .april_manuscript_editor import AUTHOR, CATALOG, PROJECT_ROOT, load_catalog, normalize_front_matter, resolve_source
    from .manuscript_auditor import audit_text, extract_text
except ImportError:
    from april_manuscript_editor import AUTHOR, CATALOG, PROJECT_ROOT, load_catalog, normalize_front_matter, resolve_source
    from manuscript_auditor import audit_text, extract_text


DEFAULT_OUTPUT_ROOT = Path.home() / ".local" / "share" / "mobleybooks" / "releases"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    temporary.replace(path)


def package_entry(entry: dict[str, Any], output_root: Path) -> dict[str, Any]:
    if entry.get("author") != AUTHOR:
        raise ValueError(f"{entry.get('slug')}: author must be {AUTHOR}")
    if "complete manuscript" not in str(entry.get("status", "")).casefold():
        raise ValueError(f"{entry.get('slug')}: catalog status is not Complete manuscript")

    source = resolve_source(str(entry["source_ref"]))
    manuscript = normalize_front_matter(extract_text(source), str(entry["title"]))
    audit = audit_text(manuscript, source=str(source))
    if not audit["mechanical_gate_passed"]:
        raise ValueError(f"{entry['slug']}: mechanical gate failed: {', '.join(audit['failures'])}")

    cover = PROJECT_ROOT / "assets" / "covers" / f"{entry['slug']}-cover-v1.png"
    if not cover.is_file():
        raise FileNotFoundError(f"{entry['slug']}: approved cover not found: {cover}")

    release_dir = output_root / str(entry["slug"])
    manuscript_path = release_dir / "manuscript.md"
    epub_path = release_dir / f"{entry['slug']}.epub"
    atomic_write(manuscript_path, manuscript.encode("utf-8"))
    release_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pandoc",
            str(manuscript_path),
            "--from=markdown",
            "--to=epub3",
            "--metadata",
            f"title={entry['title']}",
            "--metadata",
            f"author={AUTHOR}",
            "--epub-cover-image",
            str(cover),
            "--output",
            str(epub_path),
        ],
        check=True,
    )

    record = {
        "schema": "mobleybooks.release-candidate.v1",
        "status": "candidate_pending_final_editorial_review",
        "slug": entry["slug"],
        "title": entry["title"],
        "author": AUTHOR,
        "source": str(source),
        "source_sha256": sha256_bytes(source.read_bytes()),
        "normalized_manuscript_sha256": sha256_bytes(manuscript.encode("utf-8")),
        "epub": str(epub_path),
        "epub_sha256": sha256_bytes(epub_path.read_bytes()),
        "epub_bytes": epub_path.stat().st_size,
        "cover": str(cover),
        "cover_sha256": sha256_bytes(cover.read_bytes()),
        "audit": audit,
        "created_at": utc_now(),
    }
    atomic_write(
        release_dir / "release-candidate.json",
        (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    entries = {item["slug"]: item for item in load_catalog(args.catalog)["titles"]}
    unknown = [slug for slug in args.slugs if slug not in entries]
    if unknown:
        parser.error("unknown catalog slugs: " + ", ".join(unknown))
    records = [package_entry(entries[slug], args.output_root) for slug in args.slugs]
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
