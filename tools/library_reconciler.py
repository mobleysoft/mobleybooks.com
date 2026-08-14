#!/usr/bin/env python3
"""Build a private, evidence-backed MobleyBooks manuscript inventory.

Discovery is deliberately separate from publication. This tool reads Unlost's
local SQLite shards in read-only mode, groups likely manuscript artifacts into
candidate works, estimates completion work, and emits one bounded A.P.R.I.L.
profile per candidate. It never edits a manuscript or the public catalog.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import statistics
import tempfile
from typing import Any, Iterable
import zipfile


SCHEMA = "mobleybooks.library-reconciliation.v1"
PROFILE_SCHEMA = "mobleybooks.april-completion-profile.v1"
KDP_SCHEMA = "mobleybooks.private-kdp-inventory.v1"

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "publications.json"
DEFAULT_PRIVATE_ROOT = HOME / ".local" / "share" / "mobleybooks"
DEFAULT_DATABASES = (
    HOME / ".local" / "share" / "unlost" / "unlost.db",
    HOME / ".local" / "share" / "unlost-replicas" / "dell-owner" / "unlost.db",
)
DEFAULT_APRIL_ENGINE = HOME / "mascom" / "apex_april_engine.py"
DEFAULT_LINEAGE = HOME / "mascom" / "april_lineage_manifest.json"

PROSE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".epub",
    ".gdoc",
    ".md",
    ".mobi",
    ".mobtxt",
    ".odt",
    ".pages",
    ".pdf",
    ".rtf",
    ".txt",
}

STRONG_PATH_MARKERS = (
    "/writing/",
    "/books/",
    "/book/",
    "/fiction/",
    "/novel/",
    "/novels/",
    "/stories/",
    "/story/",
    "/manuscript/",
    "/manuscripts/",
    "/screenplay/",
)
AUTHORED_PATH_MARKERS = (
    "/business/writing/",
    "/0transfer/books/docs/",
    "/0transfer/books/orgus/",
)
GENERATED_PATH_MARKERS = (
    "/april/",
    "/april5/",
    "/april6/",
    "/april7/",
    "/april8/",
    "/april9/",
    "/april18/",
    "/hardenedapril/",
    "/wordsmith/",
    "/productions/",
)
SUPPORT_MARKERS = (
    "supportdoc",
    "support doc",
    "bible",
    "worldbuilder",
    "world builder",
    "character illustration",
    "cover",
    "notes",
    "outline",
    "readme",
    "staging_output",
    "log.txt",
)
SUPPORT_PATH_MARKERS = (
    "/meta/editing/contracts/",
    "/meta/howtowrite/",
    "/bookcovers/",
)
CREATIVE_REVIEW_PATH_MARKERS = (
    "/comedy/",
    "/lyrics/",
    "/music/",
)
SYSTEM_PATH_MARKERS = (
    "/.git/",
    "/node_modules/",
    "/site-packages/",
    "/.venv/",
    "/venv/",
    "/__pycache__/",
    "/nuclei-templates/",
    "/training/",
    "/enwik_",
    "/corpus/",
    "/papers/",
    "/research/",
    "/joinery/runs/",
    "/codex/sessions/",
    "/antigravity-cli/brain/",
)
NON_BOOK_NAME_MARKERS = (
    "readme",
    "license",
    "changelog",
    "requirements",
    "runbook",
    "manifest",
    "specification",
    "conversation_history",
    "transcript",
    "benchmark",
    "report",
)
MATURE_REVIEW_MARKERS = (
    "erotica",
    "femboy",
    "intimacy",
    "sissy",
    "/erotic/",
    "/adult",
    "/mature",
)
GENERIC_TITLES = {
    "book",
    "generated book",
    "simulated book",
    "staging output",
    "untitled book",
    "story",
    "novel",
    "document",
}
TITLE_STOPWORDS = {"a", "an", "and", "book", "of", "the", "volume"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "untitled"


def sha256_file(path: Path, limit: int = 64 * 1024 * 1024) -> tuple[str, str]:
    if not path.exists() or not path.is_file():
        return "", "unavailable"
    if path.stat().st_size > limit:
        stat = path.stat()
        value = f"{path}:{stat.st_size}:{stat.st_mtime_ns}"
        return hashlib.sha256(value.encode()).hexdigest(), "metadata"
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest(), "content"


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(payload)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Asset:
    database: str
    path: str
    name: str
    entity_id: str
    extension: str
    size: int
    mtime_ns: int
    sha256: str
    source_id: str
    role: str
    authority: int
    uri: str

    @property
    def local_path(self) -> Path:
        original = Path(self.path)
        if original.exists():
            return original
        prefix = "/Volumes/Users/"
        if self.path.startswith(prefix):
            relative = self.path[len(prefix) :]
            return HOME / ".local" / "mnt" / "dell-users" / relative
        return original


def read_assets(database: Path) -> list[Asset]:
    if not database.exists():
        return []
    uri = f"file:{database}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        placeholders = ",".join("?" for _ in PROSE_EXTENSIONS)
        rows = connection.execute(
            f"""
            SELECT path, name, entity_id, extension, size, mtime_ns,
                   coalesce(sha256, ''), source_id, role, authority, coalesce(uri, '')
            FROM files
            WHERE lower(extension) IN ({placeholders})
            """,
            sorted(PROSE_EXTENSIONS),
        ).fetchall()
    finally:
        connection.close()
    return [Asset(str(database), *row) for row in rows]


def candidate_score(asset: Asset) -> int:
    path = asset.path.casefold()
    name = asset.name.casefold()
    score = 0
    if any(marker in path for marker in STRONG_PATH_MARKERS):
        score += 6
    if any(marker in path for marker in AUTHORED_PATH_MARKERS):
        score += 4
    if any(marker in path for marker in GENERATED_PATH_MARKERS):
        score += 3
    if asset.extension.casefold() in {".doc", ".docx", ".epub", ".mobi", ".mobtxt", ".odt", ".pages"}:
        score += 2
    if re.search(r"(?:^|[_\s-])(book|chapter|novel|story|manuscript)(?:[_\s.-]|$)", name):
        score += 2
    if any(marker in path for marker in SYSTEM_PATH_MARKERS):
        score -= 8
    if any(marker in name for marker in NON_BOOK_NAME_MARKERS):
        score -= 5
    if asset.size < 40:
        score -= 3
    return score


def title_and_word_hint(asset: Asset) -> tuple[str, int]:
    filename = asset.name
    hint = 0
    if asset.extension.casefold() == ".gdoc" and "/meta/drafts/" in asset.path.casefold():
        match = re.match(r"^(\d{2,5})(?=[A-Za-z])", Path(filename).stem)
        if match:
            hint = int(match.group(1))
            filename = Path(filename).stem[len(match.group(1)) :] + asset.extension
    return clean_title(filename), hint


def clean_title(filename: str) -> str:
    value = Path(filename).stem
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\b(?:support\s*doc|generated\s*book|simulated\s*book)\b", " ", value, flags=re.I)
    value = re.sub(r"\bbook\b\s*", " ", value, flags=re.I)
    value = re.sub(r"\b(?:published|final|fixed|again|copy)\b", " ", value, flags=re.I)
    value = re.sub(r"\(\d+\)", " ", value)
    value = re.sub(r"(?:^|\s)20\d{6}(?:\s|$)", " ", value)
    value = re.sub(r"(?:^|\s)\d{6}(?:\s|$)", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return value or "Untitled"


def normalized_title(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return " ".join(part for part in value.split() if part not in {"published", "final", "copy"})


def work_key(asset: Asset) -> str:
    title, _ = title_and_word_hint(asset)
    normalized = normalized_title(title)
    if normalized in GENERIC_TITLES or len(normalized) < 3:
        parent = Path(asset.path).parent.name
        return safe_slug(f"{parent}-{title}")
    return safe_slug(normalized)


def classify_asset(asset: Asset) -> str:
    path = asset.path.casefold()
    name = asset.name.casefold()
    if any(marker in name for marker in SUPPORT_MARKERS) or any(
        marker in path for marker in SUPPORT_PATH_MARKERS
    ):
        return "support_material"
    if any(marker in path for marker in GENERATED_PATH_MARKERS) or re.search(r"_book_20\d{6}", name):
        return "legacy_generated_candidate"
    if any(marker in path for marker in CREATIVE_REVIEW_PATH_MARKERS):
        return "review_candidate"
    if any(marker in path for marker in AUTHORED_PATH_MARKERS):
        return "authored_candidate"
    return "review_candidate"


def xml_to_text(value: bytes) -> str:
    decoded = value.decode("utf-8", errors="replace")
    decoded = re.sub(r"<[^>]+>", " ", decoded)
    return html.unescape(re.sub(r"\s+", " ", decoded)).strip()


def extract_text(path: Path, extension: str, max_chars: int = 4_000_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    extension = extension.casefold()
    try:
        if extension in {".txt", ".md", ".mobtxt", ".rtf"}:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        if extension == ".docx":
            with zipfile.ZipFile(path) as archive:
                return xml_to_text(archive.read("word/document.xml"))[:max_chars]
        if extension == ".odt":
            with zipfile.ZipFile(path) as archive:
                return xml_to_text(archive.read("content.xml"))[:max_chars]
        if extension == ".epub":
            chunks: list[str] = []
            with zipfile.ZipFile(path) as archive:
                for name in sorted(archive.namelist()):
                    if name.casefold().endswith((".html", ".htm", ".xhtml")):
                        chunks.append(xml_to_text(archive.read(name)))
                        if sum(map(len, chunks)) >= max_chars:
                            break
            return " ".join(chunks)[:max_chars]
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    return ""


def count_words(value: str) -> int:
    return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", value, flags=re.UNICODE))


def infer_series(title: str, path: str, catalog: dict[str, Any]) -> str:
    key = normalized_title(title)
    for entry in catalog.get("titles", []):
        if normalized_title(entry["title"]) == key:
            return entry.get("series", "Standalone")
    joined = f"{title} {path}".casefold()
    known = {
        "verdant vale": "Verdant Vale",
        "historia": "Historia's Heartbeat",
        "canticle of champions": "Canticle of Champions",
        "new founding": "The New Founding",
        "arcane seven": "Arcane Seven",
    }
    for marker, series in known.items():
        if marker in joined:
            return series
    return "Standalone"


def series_word_targets(catalog: dict[str, Any]) -> dict[str, int]:
    samples: dict[str, list[int]] = defaultdict(list)
    for entry in catalog.get("titles", []):
        if "published" in entry.get("status", "").casefold() and entry.get("series") != "Standalone":
            samples[entry["series"]].append(int(entry["words"]))
    return {series: int(statistics.median(words)) for series, words in samples.items() if words}


def structural_status(words: int, declared_status: str = "") -> str:
    status = declared_status.casefold()
    if "published" in status:
        return "published"
    if "complete" in status:
        return "complete_unpublished"
    if "treatment" in status:
        return "treatment"
    if "fragment" in status or words < 1_000:
        return "fragment"
    if words < 10_000:
        return "partial_draft"
    if words < 45_000:
        return "substantial_draft"
    return "full_length_review"


def target_words(words: int, status: str, series: str, series_targets: dict[str, int]) -> int:
    lowered = status.casefold()
    if "published" in lowered or "complete" in lowered:
        return words
    if series != "Standalone" and series in series_targets:
        return max(words, series_targets[series])
    if "treatment" in lowered or "fragment" in lowered:
        return max(words, 5_000)
    if words < 1_500:
        return 7_500
    if words < 10_000:
        return 15_000
    if words < 30_000:
        return 30_000
    if words < 50_000:
        return 50_000
    return words


def specialization_for(classification: str, status: str, words: int, series: str) -> str:
    if classification == "legacy_generated_candidate":
        return "legacy-output-rehabilitation"
    if "complete" in status or "published" in status:
        return "editorial-and-release"
    if series != "Standalone":
        return "series-continuity-completion"
    if words < 1_500:
        return "fragment-expansion"
    if words < 10_000:
        return "short-form-completion"
    return "novel-completion"


def april_name(title: str, series: str) -> str:
    source = series if series != "Standalone" else title
    tokens = [token for token in re.findall(r"[A-Za-z0-9]+", source) if token.casefold() not in TITLE_STOPWORDS]
    return f"April {tokens[-1] if tokens else 'Story'}"


def remaining_gates(status: str, series: str, delta: int, accessible: bool) -> list[str]:
    gates: list[str] = []
    if not accessible:
        gates.append("hydrate_source")
    gates.extend(["editorial_scope_confirmation", "canon_extract", "structural_audit"])
    if delta > 0:
        gates.extend(["gap_map", "scene_plan", "draft_missing_scenes"])
    if series != "Standalone":
        gates.append("series_continuity_gate")
    gates.extend(
        [
            "quality_gate",
            "line_edit",
            "copyedit",
            "workplace_safety_review",
            "rights_and_provenance_review",
            "edition_package",
            "explicit_publication_approval",
        ]
    )
    return gates


def make_profile(work: dict[str, Any], private_root: Path, lineage_hash: str) -> dict[str, Any]:
    source = work["representative_source"]
    output_root = private_root / "april-output" / work["work_id"]
    ready = (
        work["classification"] == "authored_candidate"
        and work["source_accessible"]
        and not work["editorial_blocked"]
    )
    return {
        "schema": PROFILE_SCHEMA,
        "profile_id": f"april.completion.{work['work_id']}.v1",
        "display_name": april_name(work["title"], work["series"]),
        "base_engine": str(DEFAULT_APRIL_ENGINE),
        "lineage_manifest": str(DEFAULT_LINEAGE),
        "lineage_manifest_sha256": lineage_hash,
        "specialization": specialization_for(
            work["classification"], work["declared_status"], work["current_words"], work["series"]
        ),
        "execution_status": "ready_for_bounded_run" if ready else "blocked_pending_review",
        "source_contract": {
            "path": source["path"],
            "uri": source["uri"],
            "fingerprint": work["source_fingerprint"],
            "fingerprint_kind": work["source_fingerprint_kind"],
            "source_mutation_forbidden": True,
            "output_root": str(output_root),
        },
        "story_contract": {
            "title": work["title"],
            "series": work["series"],
            "current_words": work["current_words"],
            "target_words": work["target_words"],
            "length_delta": work["length_delta"],
            "structural_status": work["structural_status"],
            "target_is_provisional": True,
        },
        "stages": [
            "source_integrity_check",
            "canon_extract",
            "structural_audit",
            "gap_map",
            "scene_plan",
            "parallel_scene_drafts",
            "continuity_gate",
            "quality_gate",
            "editorial_package",
        ],
        "acceptance": {
            "preserve_existing_prose": True,
            "mark_generated_text_by_provenance": True,
            "no_unresolved_continuity_errors": True,
            "no_publication_without_human_approval": True,
            "required_gates": work["remaining_gates"],
        },
    }


def catalog_draft_works(catalog: dict[str, Any], series_targets: dict[str, int]) -> list[dict[str, Any]]:
    works: list[dict[str, Any]] = []
    for entry in catalog.get("titles", []):
        if "published" in entry.get("status", "").casefold():
            continue
        words = int(entry["words"])
        target = target_words(words, entry["status"], entry["series"], series_targets)
        work_id = safe_slug(entry["slug"])
        works.append(
            {
                "work_id": work_id,
                "title": entry["title"],
                "series": entry.get("series", "Standalone"),
                "classification": "catalogued_private_manuscript",
                "declared_status": entry["status"],
                "structural_status": structural_status(words, entry["status"]),
                "current_words": words,
                "target_words": target,
                "length_delta": max(0, target - words),
                "completion_ratio": round(min(1.0, words / target), 4) if target else 0,
                "source_count": 1,
                "source_accessible": False,
                "source_fingerprint": hashlib.sha256(entry["source_ref"].encode()).hexdigest(),
                "source_fingerprint_kind": "catalog-reference",
                "editorial_blocked": False,
                "representative_source": {
                    "path": entry["source_ref"],
                    "uri": "",
                    "source_id": "public-catalog-reference",
                },
                "remaining_gates": remaining_gates(
                    entry["status"], entry.get("series", "Standalone"), max(0, target - words), False
                ),
            }
        )
    return works


def build_asset_works(
    assets: Iterable[Asset],
    catalog: dict[str, Any],
    decisions: dict[str, Any],
    series_targets: dict[str, int],
    min_score: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    candidate_assets = [asset for asset in assets if candidate_score(asset) >= min_score]
    groups: dict[str, list[Asset]] = defaultdict(list)
    for asset in candidate_assets:
        groups[work_key(asset)].append(asset)

    class_rank = {
        "authored_candidate": 3,
        "review_candidate": 2,
        "legacy_generated_candidate": 1,
        "support_material": 0,
    }
    works: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    for key, group in groups.items():
        classifications = [classify_asset(asset) for asset in group]
        dominant = max(classifications, key=lambda value: class_rank[value])
        class_counts[dominant] += 1
        if dominant == "support_material":
            continue

        decision = decisions.get("works", {}).get(key, {})
        blocked = decision.get("disposition") == "exclude" or any(
            marker in f"{asset.path}/{asset.name}".casefold()
            for asset in group
            for marker in (*MATURE_REVIEW_MARKERS, *CREATIVE_REVIEW_PATH_MARKERS)
        )
        measured: list[tuple[Asset, int, str, str]] = []
        for asset in group:
            text = "" if blocked else extract_text(asset.local_path, asset.extension)
            measured_words = count_words(text)
            _, hint = title_and_word_hint(asset)
            words = measured_words or hint
            word_kind = "extracted" if measured_words else ("filename_hint" if hint else "unavailable")
            measured.append((asset, words, text, word_kind))
        representative, words, _, word_kind = max(
            measured,
            key=lambda item: (
                class_rank[classify_asset(item[0])],
                item[1],
                item[0].size,
                item[0].authority,
            ),
        )
        title, _ = title_and_word_hint(representative)
        series = infer_series(title, representative.path, catalog)
        declared_status = "Discovered draft candidate"
        status = structural_status(words, declared_status)
        target = target_words(words, declared_status, series, series_targets)
        delta = max(0, target - words)
        fingerprint = representative.sha256
        fingerprint_kind = "unlost-content" if fingerprint else ""
        if not fingerprint:
            fingerprint, fingerprint_kind = sha256_file(representative.local_path)
        if not fingerprint:
            fingerprint = hashlib.sha256(
                f"{representative.path}:{representative.size}:{representative.mtime_ns}".encode()
            ).hexdigest()
            fingerprint_kind = "unlost-metadata"
        works.append(
            {
                "work_id": key,
                "title": title,
                "series": series,
                "classification": dominant,
                "declared_status": declared_status,
                "structural_status": status,
                "current_words": words,
                "word_count_kind": word_kind,
                "target_words": target,
                "length_delta": delta,
                "completion_ratio": round(min(1.0, words / target), 4) if target else 0,
                "source_count": len(group),
                "source_accessible": representative.local_path.exists(),
                "source_fingerprint": fingerprint,
                "source_fingerprint_kind": fingerprint_kind,
                "editorial_blocked": blocked,
                "representative_source": {
                    "path": representative.path,
                    "uri": representative.uri,
                    "source_id": representative.source_id,
                },
                "alternate_sources": [
                    {"path": asset.path, "uri": asset.uri, "size": asset.size}
                    for asset in sorted(group, key=lambda item: item.path)
                    if asset.path != representative.path
                ],
                "remaining_gates": remaining_gates(declared_status, series, delta, representative.local_path.exists()),
            }
        )
    works.sort(key=lambda item: (item["editorial_blocked"], -item["length_delta"], item["title"].casefold()))
    metrics = {
        "candidate_assets": len(candidate_assets),
        "candidate_work_groups": len(groups),
        "support_material_groups": class_counts["support_material"],
        "authored_candidate_groups": class_counts["authored_candidate"],
        "legacy_generated_groups": class_counts["legacy_generated_candidate"],
        "review_candidate_groups": class_counts["review_candidate"],
    }
    return works, metrics


def asin_from_url(value: str) -> str:
    match = re.search(r"/dp/([A-Z0-9]+)", value or "")
    return match.group(1) if match else ""


def audit_kdp(catalog: dict[str, Any], inventory: dict[str, Any] | None) -> dict[str, Any]:
    public = {asin_from_url(entry.get("retail_url", "")): entry["slug"] for entry in catalog.get("titles", [])}
    public.pop("", None)
    if not inventory:
        return {
            "status": "unavailable",
            "reason": "private KDP inventory is missing",
            "public_retail_records": len(public),
        }
    if inventory.get("schema") != KDP_SCHEMA:
        raise ValueError("unsupported private KDP inventory schema")
    records = inventory.get("records", [])
    approved = [record for record in records if record.get("disposition") == "approved_sfw"]
    excluded = [record for record in records if record.get("disposition") == "exclude"]
    omissions = [record for record in approved if record.get("ebook_asin") not in public]
    return {
        "status": "passed" if not omissions else "incomplete",
        "inventory_scope": inventory.get("scope", {}),
        "inventory_records": len(records),
        "approved_sfw_records": len(approved),
        "excluded_records": len(excluded),
        "public_retail_records": len(public),
        "approved_omissions": [
            {
                "inventory_id": record["inventory_id"],
                "title": record.get("title"),
                "ebook_asin": record.get("ebook_asin"),
            }
            for record in omissions
        ],
        "unreconciled_public_asins": sorted(set(public) - {record.get("ebook_asin") for record in records}),
    }


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# MobleyBooks Private Reconciliation",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "This is a discovery and planning report, not a publication allowlist.",
        "",
        "## Inventory",
        "",
        f"- Raw prose-capable assets indexed: {metrics['raw_prose_assets']:,}",
        f"- Likely manuscript assets: {metrics['candidate_assets']:,}",
        f"- Candidate work groups after title/revision grouping: {metrics['candidate_work_groups']:,}",
        f"- Authored candidate groups: {metrics['authored_candidate_groups']:,}",
        f"- Legacy generated groups: {metrics['legacy_generated_groups']:,}",
        f"- Review candidate groups: {metrics['review_candidate_groups']:,}",
        f"- Catalogued unpublished works: {metrics['catalogued_unpublished_works']:,}",
        f"- April profiles emitted: {metrics['april_profiles_emitted']:,}",
        "",
        "## Completion Queue",
        "",
        "| Work | Class | Words | Target | Delta | April | State |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for work in report["works"][:250]:
        profile = report["profile_index"].get(work["work_id"], {})
        state = profile.get("execution_status", "not_emitted")
        title = work["title"].replace("|", "\\|")
        lines.append(
            f"| {title} | {work['classification']} | {work['current_words']:,} | "
            f"{work['target_words']:,} | {work['length_delta']:,} | "
            f"{profile.get('display_name', '')} | {state} |"
        )
    if len(report["works"]) > 250:
        lines.extend(["", f"The JSON report contains {len(report['works']) - 250:,} additional work groups."])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A file is not a book, a work group is not an approved title, and an April profile is not permission to publish. "
            "Every work must pass the profile's editorial, safety, provenance, and explicit publication gates.",
            "",
        ]
    )
    return "\n".join(lines)


def reconcile(args: argparse.Namespace) -> dict[str, Any]:
    catalog = load_json(args.catalog)
    if not catalog:
        raise FileNotFoundError(args.catalog)
    private_root: Path = args.private_root.expanduser().resolve()
    decisions = load_json(private_root / "private" / "editorial-decisions.json", {"works": {}})
    inventory = load_json(private_root / "private" / "kdp-inventory.json")

    assets: list[Asset] = []
    seen: set[tuple[str, str]] = set()
    database_counts: dict[str, int] = {}
    for database in args.database:
        records = read_assets(database.expanduser().resolve())
        database_counts[str(database)] = len(records)
        for asset in records:
            identity = (asset.path, asset.entity_id)
            if identity not in seen:
                seen.add(identity)
                assets.append(asset)

    targets = series_word_targets(catalog)
    discovered, metrics = build_asset_works(assets, catalog, decisions, targets, args.min_score)
    known = catalog_draft_works(catalog, targets)
    catalog_ids = {
        identifier
        for entry in catalog.get("titles", [])
        for identifier in (safe_slug(entry["slug"]), safe_slug(normalized_title(entry["title"])))
    }
    works = known + [work for work in discovered if work["work_id"] not in catalog_ids]

    lineage_hash, _ = sha256_file(DEFAULT_LINEAGE)
    profiles: list[dict[str, Any]] = []
    profile_index: dict[str, dict[str, str]] = {}
    profile_root = private_root / "april-profiles"
    for work in works:
        profile = make_profile(work, private_root, lineage_hash)
        profiles.append(profile)
        profile_index[work["work_id"]] = {
            "profile_id": profile["profile_id"],
            "display_name": profile["display_name"],
            "execution_status": profile["execution_status"],
            "path": str(profile_root / f"{work['work_id']}.json"),
        }
        atomic_write_json(profile_root / f"{work['work_id']}.json", profile)

    report = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "scope": {
            "databases": database_counts,
            "min_candidate_score": args.min_score,
            "publication_side_effects": False,
            "source_mutations": False,
        },
        "metrics": {
            "raw_prose_assets": len(assets),
            **metrics,
            "catalogued_unpublished_works": len(known),
            "april_profiles_emitted": len(profiles),
            "blocked_profiles": sum(profile["execution_status"].startswith("blocked") for profile in profiles),
        },
        "kdp_audit": audit_kdp(catalog, inventory),
        "works": works,
        "profile_index": profile_index,
    }
    report_root = private_root / "reconciliation"
    atomic_write_json(report_root / "latest.json", report)
    atomic_write_text(report_root / "latest.md", render_markdown(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--database", action="append", type=Path)
    parser.add_argument("--min-score", type=int, default=5)
    parser.add_argument("--strict", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.database:
        args.database = list(DEFAULT_DATABASES)
    report = reconcile(args)
    summary = {
        "status": "observed",
        "report": str(args.private_root.expanduser().resolve() / "reconciliation" / "latest.json"),
        "metrics": report["metrics"],
        "kdp_audit": report["kdp_audit"],
    }
    print(json.dumps(summary, indent=2))
    if args.strict and report["kdp_audit"].get("status") == "incomplete":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
