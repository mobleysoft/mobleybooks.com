#!/usr/bin/env python3
"""Run a resumable local developmental review over MobleyBooks manuscripts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

try:
    from .april_manuscript_editor import AUTHOR, CATALOG, chapter_sections, load_catalog, normalize_front_matter, resolve_source
    from .manuscript_auditor import extract_text
except ImportError:
    from april_manuscript_editor import AUTHOR, CATALOG, chapter_sections, load_catalog, normalize_front_matter, resolve_source
    from manuscript_auditor import extract_text


DEFAULT_OUTPUT_ROOT = Path.home() / ".local" / "share" / "mobleybooks" / "editorial-reviews"
DECISIONS = {"approve", "revise", "split", "reject"}
DECISION_READINESS_CEILINGS = {
    "approve": 100,
    "revise": 79,
    "split": 69,
    "reject": 39,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def parse_source_overrides(values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values:
        slug, separator, raw_path = value.partition("=")
        if not separator or not slug.strip() or not raw_path.strip():
            raise ValueError(f"invalid source override {value!r}; expected SLUG=PATH")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"source override does not exist: {path}")
        overrides[slug.strip()] = path
    return overrides


def bounded_excerpt(text: str, maximum: int = 14_000) -> str:
    if len(text) <= maximum:
        return text
    head = maximum * 5 // 12
    middle = maximum * 3 // 12
    tail = maximum - head - middle
    midpoint = len(text) // 2
    return (
        text[:head]
        + "\n\n[EDITORIAL SAMPLE WINDOW: source continues outside this supplied window]\n\n"
        + text[midpoint - middle // 2 : midpoint + middle // 2]
        + "\n\n[EDITORIAL SAMPLE WINDOW: source continues outside this supplied window]\n\n"
        + text[-tail:]
    )


def parse_json_response(value: str) -> dict[str, Any]:
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.DOTALL | re.IGNORECASE).strip()
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            raise ValueError("reviewer did not return JSON")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("reviewer returned non-object JSON")
    return payload


def invoke_reviewer(prompt: str, *, port: int, max_tokens: int) -> dict[str, Any]:
    mascom = str(Path.home() / "mascom")
    if mascom not in sys.path:
        sys.path.insert(0, mascom)
    from powerthon_runtime import _pwy_invoke_llm

    response = _pwy_invoke_llm(
        prompt=prompt,
        system_prompt=(
            "You are a severe but constructive senior developmental editor. Evaluate the supplied fiction "
            "as a commercial reader would, not as a supportive writing assistant. Identify plot discontinuity, "
            "genre drift, repeated climaxes or false endings, generic AI-style abstraction, continuity errors, "
            "thin characterization, and unfinished material. Return JSON only. Never rewrite the passage. /no_think"
        ),
        port=port,
        temperature=0.15,
        max_tokens=max_tokens,
    )
    return parse_json_response(response)


def normalize_chapter_review(payload: dict[str, Any], index: int) -> dict[str, Any]:
    decision = str(payload.get("recommended_action", "revise")).casefold()
    if decision not in DECISIONS:
        decision = "revise"
    score_names = ("coherence_score", "prose_score", "commercial_readiness_score")
    raw_scores: dict[str, float] = {}
    for name in score_names:
        try:
            raw_scores[name] = float(payload.get(name, 0))
        except (TypeError, ValueError):
            raw_scores[name] = 0
    uses_ten_point_scale = all(0 <= value <= 10 for value in raw_scores.values())

    def score(name: str) -> int:
        value = raw_scores[name] * (10 if uses_ten_point_scale else 1)
        return max(0, min(100, round(value)))

    return {
        "chapter": index,
        "coherence_score": score("coherence_score"),
        "prose_score": score("prose_score"),
        "commercial_readiness_score": score("commercial_readiness_score"),
        "strengths": [str(item) for item in payload.get("strengths", [])][:8],
        "blocking_defects": [str(item) for item in payload.get("blocking_defects", [])][:12],
        "continuity_notes": [str(item) for item in payload.get("continuity_notes", [])][:12],
        "recommended_action": decision,
    }


def reconcile_readiness(
    decision: str,
    synthesis_score: float,
    chapter_reviews: list[dict[str, Any]],
) -> int:
    """Keep a model's summary score consistent with its underlying evidence."""
    if not chapter_reviews:
        return 0
    chapter_score = round(
        sum(review["commercial_readiness_score"] for review in chapter_reviews)
        / len(chapter_reviews)
    )
    score = min(round(synthesis_score), chapter_score)
    return max(0, min(score, DECISION_READINESS_CEILINGS[decision]))


def review_entry(entry: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    source = args.source_overrides.get(str(entry["slug"]))
    if source is None:
        source = resolve_source(str(entry["source_ref"]))
    manuscript = normalize_front_matter(extract_text(source), str(entry["title"]))
    sections = [section for section in chapter_sections(manuscript) if len(section.split()) >= 80]
    output_dir = args.output_root / str(entry["slug"])
    chapter_dir = output_dir / "chapters"
    reviews: list[dict[str, Any]] = []

    for index, section in enumerate(sections, start=1):
        checkpoint = chapter_dir / f"{index:04d}.json"
        if checkpoint.is_file() and not args.force:
            review = normalize_chapter_review(
                json.loads(checkpoint.read_text(encoding="utf-8")),
                index,
            )
        else:
            prompt = f"""BOOK: {entry['title']}
AUTHOR: {AUTHOR}
CATALOG GENRE: {entry.get('genre', 'Unspecified')}
SECTION: {index} of {len(sections)}

Evaluate this section in the context of a complete commercial book. Use this exact schema:
{{
  "coherence_score": 0,
  "prose_score": 0,
  "commercial_readiness_score": 0,
  "strengths": [],
  "blocking_defects": [],
  "continuity_notes": [],
  "recommended_action": "approve|revise|split|reject"
}}

IMPORTANT: Any bracketed EDITORIAL SAMPLE WINDOW marker was inserted by the review tool. It is not
part of the manuscript and is not evidence that the source is truncated or unfinished.

PASSAGE:
{bounded_excerpt(section, args.max_chars)}"""
            review = normalize_chapter_review(
                invoke_reviewer(prompt, port=args.port, max_tokens=args.max_tokens),
                index,
            )
            atomic_json(checkpoint, review)
        reviews.append(review)

    compact = json.dumps(reviews, ensure_ascii=False)
    synthesis_prompt = f"""BOOK: {entry['title']}
AUTHOR: {AUTHOR}
CATALOG GENRE: {entry.get('genre', 'Unspecified')}
WORD COUNT: {len(manuscript.split())}
SECTION REVIEWS: {compact}

Synthesize a strict release decision. Multiple chapter endings that repeatedly announce victory, a new era,
or that the real adventure has just begun are structural defects, not strengths. A genre-premise abandoned
mid-book is a release blocker. Disregard any chapter defect based only on an EDITORIAL SAMPLE WINDOW marker;
the marker represents bounded review input, not missing source text. Use this exact schema:
{{
  "decision": "approve|revise|split|reject",
  "commercial_readiness_score": 0,
  "one_sentence_diagnosis": "",
  "strengths": [],
  "release_blockers": [],
  "required_revisions": [],
  "recommended_split_points": []
}}"""
    synthesis = invoke_reviewer(synthesis_prompt, port=args.port, max_tokens=args.max_tokens)
    decision = str(synthesis.get("decision", "revise")).casefold()
    if decision not in DECISIONS:
        decision = "revise"
    try:
        raw_readiness = float(synthesis.get("commercial_readiness_score", 0))
        if 0 <= raw_readiness <= 10:
            raw_readiness *= 10
        readiness = reconcile_readiness(decision, raw_readiness, reviews)
    except (TypeError, ValueError):
        readiness = 0
    report = {
        "schema": "mobleybooks.editorial-review.v1",
        "status": "automated_developmental_review_complete",
        "title": entry["title"],
        "slug": entry["slug"],
        "author": AUTHOR,
        "source": str(source),
        "sections_reviewed": len(reviews),
        "decision": decision,
        "commercial_readiness_score": readiness,
        "one_sentence_diagnosis": str(synthesis.get("one_sentence_diagnosis", "")),
        "strengths": [str(item) for item in synthesis.get("strengths", [])][:12],
        "release_blockers": [str(item) for item in synthesis.get("release_blockers", [])][:20],
        "required_revisions": [str(item) for item in synthesis.get("required_revisions", [])][:20],
        "recommended_split_points": [str(item) for item in synthesis.get("recommended_split_points", [])][:20],
        "chapter_reviews": reviews,
        "human_editorial_review_still_required": True,
        "created_at": utc_now(),
    }
    atomic_json(output_dir / "review.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--port", type=int, default=18087)
    parser.add_argument("--max-chars", type=int, default=14_000)
    parser.add_argument("--max-tokens", type=int, default=1_400)
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="SLUG=PATH",
        help="review an explicit revised manuscript for a catalog slug",
    )
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
    reports = [review_entry(entries[slug], args) for slug in args.slugs]
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
