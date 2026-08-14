#!/usr/bin/env python3
"""Apply a checkpointed developmental revision to a reviewed manuscript."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

try:
    from .april_manuscript_editor import (
        AUTHOR,
        CATALOG,
        chapter_sections,
        chunk_section,
        load_catalog,
        normalize_front_matter,
        resolve_source,
        strip_model_wrappers,
    )
    from .editorial_gate import parse_json_response, parse_source_overrides
    from .manuscript_auditor import audit_text, extract_text
except ImportError:
    from april_manuscript_editor import (
        AUTHOR,
        CATALOG,
        chapter_sections,
        chunk_section,
        load_catalog,
        normalize_front_matter,
        resolve_source,
        strip_model_wrappers,
    )
    from editorial_gate import parse_json_response, parse_source_overrides
    from manuscript_auditor import audit_text, extract_text


DEFAULT_REVIEW_ROOT = Path.home() / ".local" / "share" / "mobleybooks" / "editorial-reviews-arcs"
DEFAULT_OUTPUT_ROOT = Path.home() / ".local" / "share" / "mobleybooks" / "developmental-output"


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


def atomic_json(path: Path, payload: object) -> None:
    atomic_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def invoke_model(
    prompt: str,
    *,
    system_prompt: str,
    port: int,
    max_tokens: int,
    temperature: float,
) -> str:
    mascom = str(Path.home() / "mascom")
    if mascom not in sys.path:
        sys.path.insert(0, mascom)
    from powerthon_runtime import _pwy_invoke_llm

    return _pwy_invoke_llm(
        prompt=prompt,
        system_prompt=system_prompt + " /no_think",
        port=port,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def section_digest(section: str, index: int) -> dict[str, Any]:
    words = section.split()
    return {
        "section": index,
        "words": len(words),
        "opening": " ".join(words[:120]),
        "ending": " ".join(words[-120:]),
    }


def normalize_plan(payload: dict[str, Any], section_count: int) -> dict[str, Any]:
    supplied = {}
    for item in payload.get("section_plans", []):
        try:
            index = int(item.get("section"))
        except (AttributeError, TypeError, ValueError):
            continue
        if 1 <= index <= section_count:
            supplied[index] = item
    section_plans = []
    for index in range(1, section_count + 1):
        item = supplied.get(index, {})
        section_plans.append(
            {
                "section": index,
                "purpose": str(item.get("purpose", "Preserve this section's role in the existing arc.")),
                "preserve": [str(value) for value in item.get("preserve", [])][:12],
                "repair": [str(value) for value in item.get("repair", [])][:12],
                "transition_out": str(item.get("transition_out", "Maintain causal continuity into the next section.")),
            }
        )
    return {
        "premise": str(payload.get("premise", "")),
        "genre_contract": str(payload.get("genre_contract", "")),
        "protagonist_arc": str(payload.get("protagonist_arc", "")),
        "central_conflict": str(payload.get("central_conflict", "")),
        "ending_contract": str(payload.get("ending_contract", "")),
        "global_repairs": [str(value) for value in payload.get("global_repairs", [])][:20],
        "section_plans": section_plans,
    }


def validate_revision(source: str, revised: str) -> list[str]:
    failures: list[str] = []
    source_words = len(source.split())
    revised_words = len(revised.split())
    ratio = revised_words / source_words if source_words else 0
    if not 0.68 <= ratio <= 1.45:
        failures.append(f"word_count_ratio_{ratio:.3f}")
    if not revised.strip():
        failures.append("empty_output")
    if revised.lstrip().casefold().startswith(("here is", "here's", "certainly", "of course")):
        failures.append("model_preamble")
    audit = audit_text(revised)
    if audit["contamination"]:
        failures.append("output_contamination")
    if "EDITORIAL SAMPLE WINDOW" in revised:
        failures.append("sample_marker_leaked")
    return failures


def build_plan(
    entry: dict[str, Any],
    sections: list[str],
    review: dict[str, Any],
    *,
    output_dir: Path,
    port: int,
    max_tokens: int,
    force: bool,
) -> dict[str, Any]:
    destination = output_dir / "revision-plan.json"
    if destination.is_file() and not force:
        return normalize_plan(json.loads(destination.read_text(encoding="utf-8")), len(sections))
    compact_review = {
        "decision": review.get("decision"),
        "diagnosis": review.get("one_sentence_diagnosis"),
        "blockers": review.get("release_blockers", []),
        "required_revisions": review.get("required_revisions", []),
        "chapters": review.get("chapter_reviews", []),
    }
    prompt = f"""BOOK: {entry['title']}
AUTHOR: {AUTHOR}
GENRE PROMISE: {entry.get('genre', 'Unspecified')}
DEVELOPMENTAL REVIEW: {json.dumps(compact_review, ensure_ascii=False)}
SECTION DIGESTS: {json.dumps([section_digest(section, index) for index, section in enumerate(sections, 1)], ensure_ascii=False)}

Create a conservative revision plan for this specific edition. Preserve its distinctive premise, events,
names, point of view, and authorial intent. Repair only defects supported by the review or section evidence.
Consolidate false endings, make causes lead to consequences, ground abstraction in character action, and
deliver the promised genre. Do not invent a different book. Return JSON only with this schema:
{{
  "premise": "",
  "genre_contract": "",
  "protagonist_arc": "",
  "central_conflict": "",
  "ending_contract": "",
  "global_repairs": [],
  "section_plans": [
    {{"section": 1, "purpose": "", "preserve": [], "repair": [], "transition_out": ""}}
  ]
}}"""
    payload = parse_json_response(
        invoke_model(
            prompt,
            system_prompt=(
                "You are A.P.R.I.L., a severe developmental editor and narrative architect. "
                "Plan repairs without replacing the author's book. Return JSON only."
            ),
            port=port,
            max_tokens=max_tokens,
            temperature=0.15,
        )
    )
    plan = normalize_plan(payload, len(sections))
    atomic_json(destination, plan)
    return plan


def revise_entry(entry: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    slug = str(entry["slug"])
    source = args.source_overrides.get(slug) or resolve_source(str(entry["source_ref"]))
    review_path = args.review_root / slug / "review.json"
    if not review_path.is_file():
        raise FileNotFoundError(f"review not found: {review_path}")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    original = normalize_front_matter(extract_text(source), str(entry["title"]))
    all_sections = chapter_sections(original)
    front_matter = ""
    if all_sections and len(all_sections[0].split()) < 80:
        front_matter = all_sections.pop(0).strip()
    sections = [section for section in all_sections if len(section.split()) >= 80]
    if not sections:
        raise ValueError(f"{slug}: no reviewable narrative sections")

    output_dir = args.output_root / slug / f"iteration-{args.iteration}"
    segment_dir = output_dir / "segments"
    plan = build_plan(
        entry,
        sections,
        review,
        output_dir=output_dir,
        port=args.port,
        max_tokens=args.plan_tokens,
        force=args.force,
    )
    global_plan = {key: value for key, value in plan.items() if key != "section_plans"}
    chapter_reviews = {int(item.get("chapter", 0)): item for item in review.get("chapter_reviews", [])}
    work: list[tuple[int, int, str]] = []
    for section_index, section in enumerate(sections, start=1):
        for chunk_index, chunk in enumerate(chunk_section(section, args.max_chars), start=1):
            work.append((section_index, chunk_index, chunk))

    revised_chunks: list[str] = []
    completed_this_run = 0
    previous_tail = ""
    for segment_index, (section_index, chunk_index, chunk) in enumerate(work, start=1):
        destination = segment_dir / f"{segment_index:04d}.md"
        if destination.is_file() and not args.force:
            revised = destination.read_text(encoding="utf-8").strip()
        else:
            if args.max_segments and completed_this_run >= args.max_segments:
                break
            next_head = work[segment_index][2][:900] if segment_index < len(work) else "[END OF EDITION]"
            prompt = f"""BOOK: {entry['title']}
AUTHOR: {AUTHOR}
GENRE: {entry.get('genre', 'Unspecified')}
PASSAGE: {segment_index} of {len(work)}; SECTION {section_index}; CHUNK {chunk_index}
GLOBAL REVISION PLAN: {json.dumps(global_plan, ensure_ascii=False)}
SECTION PLAN: {json.dumps(plan['section_plans'][section_index - 1], ensure_ascii=False)}
SECTION REVIEW: {json.dumps(chapter_reviews.get(section_index, {}), ensure_ascii=False)}
PREVIOUS REVISED TAIL: {previous_tail[-1000:]}
NEXT SOURCE OPENING: {next_head}

Revise the source passage itself. Preserve concrete events, names, point of view, tense, distinctive images,
and useful dialogue. Repair continuity, pacing, characterization, genre drift, repetitive abstraction, and
false-ending language according to the plan. Do not summarize, critique, add a preface, or mention the plan.
Return only the revised passage.

SOURCE PASSAGE:
{chunk}"""
            failures: list[str] = []
            revised = ""
            for attempt in range(1, 3):
                revised = strip_model_wrappers(
                    invoke_model(
                        prompt + (f"\n\nThe prior attempt failed validation: {failures}." if failures else ""),
                        system_prompt=(
                            "You are A.P.R.I.L., John Alexander Mobley's conservative developmental editor. "
                            "Strengthen the existing story without replacing its voice or facts. Output prose only."
                        ),
                        port=args.port,
                        max_tokens=args.max_tokens,
                        temperature=0.3,
                    )
                )
                failures = validate_revision(chunk, revised)
                if not failures:
                    break
            if failures:
                raise RuntimeError(f"segment {segment_index} rejected: {', '.join(failures)}")
            atomic_text(destination, revised.strip() + "\n")
            completed_this_run += 1
        previous_tail = revised
        revised_chunks.append(revised.strip())
        atomic_json(
            output_dir / "checkpoint.json",
            {
                "schema": "mobleybooks.developmental-checkpoint.v1",
                "slug": slug,
                "title": entry["title"],
                "author": AUTHOR,
                "source": str(source),
                "source_sha256": sha256_text(original),
                "iteration": args.iteration,
                "segments_total": len(work),
                "segments_completed": segment_index,
                "updated_at": utc_now(),
            },
        )

    if len(revised_chunks) < len(work):
        return {
            "schema": "mobleybooks.developmental-revision.v1",
            "status": "revision_in_progress",
            "slug": slug,
            "author": AUTHOR,
            "segments_total": len(work),
            "segments_completed": len(revised_chunks),
            "processed_this_run": completed_this_run,
        }

    body = "\n\n".join(revised_chunks).strip()
    revised_manuscript = normalize_front_matter(
        "\n\n".join(value for value in (front_matter, body) if value),
        str(entry["title"]),
    )
    manuscript_path = output_dir / "manuscript.md"
    atomic_text(manuscript_path, revised_manuscript)
    audit = audit_text(revised_manuscript, source=str(source))
    record = {
        "schema": "mobleybooks.developmental-revision.v1",
        "status": (
            "candidate_pending_editorial_re_review"
            if audit["mechanical_gate_passed"]
            else "candidate_failed_mechanical_gate"
        ),
        "slug": slug,
        "title": entry["title"],
        "author": AUTHOR,
        "source": str(source),
        "source_sha256": sha256_text(original),
        "iteration": args.iteration,
        "manuscript": str(manuscript_path),
        "manuscript_sha256": sha256_text(revised_manuscript),
        "source_words": len(original.split()),
        "revised_words": len(revised_manuscript.split()),
        "segments": len(work),
        "audit": audit,
        "created_at": utc_now(),
    }
    atomic_json(output_dir / "revision.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--source", action="append", default=[], metavar="SLUG=PATH")
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument("--port", type=int, default=18087)
    parser.add_argument("--max-chars", type=int, default=12_000)
    parser.add_argument("--max-tokens", type=int, default=4_096)
    parser.add_argument("--plan-tokens", type=int, default=2_400)
    parser.add_argument("--max-segments", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        args.source_overrides = parse_source_overrides(args.source)
    except ValueError as error:
        parser.error(str(error))
    entries = {entry["slug"]: entry for entry in load_catalog(args.catalog)["titles"]}
    unknown = [slug for slug in args.slugs if slug not in entries]
    if unknown:
        parser.error("unknown catalog slugs: " + ", ".join(unknown))
    print(json.dumps([revise_entry(entries[slug], args) for slug in args.slugs], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
