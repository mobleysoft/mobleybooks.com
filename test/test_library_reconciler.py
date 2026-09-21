from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import library_reconciler as reconciler


def create_unlost_database(path: Path, rows: list[tuple]) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE files (
          id INTEGER PRIMARY KEY,
          path TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          extension TEXT,
          size INTEGER NOT NULL,
          mtime_ns INTEGER NOT NULL,
          sha256 TEXT,
          source_id TEXT NOT NULL,
          role TEXT NOT NULL,
          authority INTEGER NOT NULL,
          uri TEXT
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO files
        (path, name, entity_id, extension, size, mtime_ns, sha256, source_id, role, authority, uri)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    connection.close()


class ReconcilerTests(unittest.TestCase):
    def test_revision_grouping_and_generated_separation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authored = root / "Business" / "Writing" / "NonErotic" / "Gloom"
            generated = root / "Books" / "April6"
            authored.mkdir(parents=True)
            generated.mkdir(parents=True)
            source = authored / "Gloom.txt"
            duplicate = authored / "Gloom (1).txt"
            machine = generated / "Stars_Book_20250101_010101.txt"
            source.write_text("The city slept. " * 200, encoding="utf-8")
            duplicate.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            machine.write_text("A generated star crossed the sky. " * 300, encoding="utf-8")

            database = root / "unlost.db"
            rows = []
            for index, path in enumerate((source, duplicate, machine), start=1):
                rows.append(
                    (
                        str(path),
                        path.name,
                        f"entity-{index}",
                        path.suffix,
                        path.stat().st_size,
                        path.stat().st_mtime_ns,
                        "",
                        "fixture",
                        "working-copy",
                        20,
                        "",
                    )
                )
            create_unlost_database(database, rows)
            assets = reconciler.read_assets(database)
            catalog = {"titles": []}
            works, metrics = reconciler.build_asset_works(
                assets, catalog, {"works": {}}, {}, min_score=5
            )

            self.assertEqual(metrics["candidate_assets"], 3)
            self.assertEqual(metrics["candidate_work_groups"], 2)
            by_class = {work["classification"]: work for work in works}
            self.assertEqual(by_class["authored_candidate"]["source_count"], 2)
            self.assertEqual(by_class["legacy_generated_candidate"]["title"], "Stars")

    def test_kdp_audit_uses_private_inventory_not_hardcoded_titles(self) -> None:
        catalog = {
            "titles": [
                {
                    "slug": "represented",
                    "retail_url": "https://www.amazon.com/dp/ASIN000001",
                }
            ]
        }
        inventory = {
            "schema": reconciler.KDP_SCHEMA,
            "scope": {"pagination_exhaustiveness": "not_verified"},
            "records": [
                {
                    "inventory_id": "represented",
                    "title": "Represented",
                    "ebook_asin": "ASIN000001",
                    "disposition": "approved_sfw",
                },
                {
                    "inventory_id": "omitted",
                    "title": "Omitted",
                    "ebook_asin": "ASIN000002",
                    "disposition": "approved_sfw",
                },
                {
                    "inventory_id": "private",
                    "title": None,
                    "ebook_asin": "ASIN000003",
                    "disposition": "exclude",
                },
            ],
        }
        audit = reconciler.audit_kdp(catalog, inventory)
        self.assertEqual(audit["status"], "incomplete")
        self.assertEqual(audit["excluded_records"], 1)
        self.assertEqual(audit["approved_omissions"][0]["inventory_id"], "omitted")

    def test_profile_is_source_immutable_and_uses_shared_engine(self) -> None:
        work = {
            "work_id": "gloom",
            "title": "Gloom",
            "series": "Standalone",
            "classification": "authored_candidate",
            "declared_status": "Discovered draft candidate",
            "current_words": 800,
            "target_words": 7500,
            "length_delta": 6700,
            "structural_status": "fragment",
            "source_accessible": True,
            "source_fingerprint": "abc123",
            "source_fingerprint_kind": "content",
            "editorial_blocked": False,
            "representative_source": {
                "path": "/private/Gloom.txt",
                "uri": "unlost://fixture/Gloom.txt",
                "source_id": "fixture",
            },
            "remaining_gates": ["quality_gate", "explicit_publication_approval"],
        }
        profile = reconciler.make_profile(work, Path("/private/output"), "lineage")
        self.assertTrue(profile["source_contract"]["source_mutation_forbidden"])
        self.assertEqual(profile["base_engine"], str(reconciler.DEFAULT_APRIL_ENGINE))
        self.assertEqual(profile["execution_status"], "ready_for_bounded_run")
        self.assertTrue(profile["acceptance"]["no_publication_without_human_approval"])

    def test_catalog_identity_joins_accessible_unlost_source(self) -> None:
        known = [
            {
                "work_id": "verdant-vale-trials-of-valor",
                "title": "Trials of Valor",
                "series": "Verdant Vale",
                "classification": "catalogued_private_manuscript",
                "declared_status": "Working manuscript",
                "structural_status": "substantial_draft",
                "current_words": 12000,
                "target_words": 18000,
                "length_delta": 6000,
                "completion_ratio": 0.66,
                "source_count": 1,
                "source_accessible": False,
                "source_fingerprint": "catalog",
                "source_fingerprint_kind": "catalog-reference",
                "editorial_blocked": False,
                "representative_source": {
                    "path": "verdantvale/Verdant Vale 03 Trials Of Valor.txt",
                    "uri": "",
                    "source_id": "catalog",
                },
                "remaining_gates": ["hydrate_source"],
            }
        ]
        discovered = [
            {
                "work_id": "verdant-vale-03-trials-of-valor",
                "title": "Verdant Vale 03 Trials Of Valor",
                "series": "Verdant Vale",
                "current_words": 13500,
                "source_count": 3,
                "source_accessible": True,
                "source_fingerprint": "content",
                "source_fingerprint_kind": "content",
                "editorial_blocked": False,
                "representative_source": {
                    "path": "/private/Verdant Vale 03 Trials Of Valor_FINAL.docx",
                    "uri": "unlost://home/trials",
                    "source_id": "home",
                },
                "alternate_sources": [],
            }
        ]
        joined, consumed = reconciler.join_catalog_sources(
            known, discovered, {"Verdant Vale": 18000}
        )
        self.assertTrue(joined[0]["source_accessible"])
        self.assertEqual(joined[0]["current_words"], 13500)
        self.assertNotIn("hydrate_source", joined[0]["remaining_gates"])
        self.assertEqual(consumed, {"verdant-vale-03-trials-of-valor"})

    def test_blocked_candidate_never_reads_or_hashes_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Business" / "Writing" / "Erotic" / "Private.txt"
            source.parent.mkdir(parents=True)
            source.write_text("private words " * 100, encoding="utf-8")
            asset = reconciler.Asset(
                database="fixture",
                path=str(source),
                name=source.name,
                entity_id="private",
                extension=".txt",
                size=source.stat().st_size,
                mtime_ns=source.stat().st_mtime_ns,
                sha256="",
                source_id="fixture",
                role="working-copy",
                authority=20,
                uri="",
            )
            with mock.patch.object(
                reconciler, "extract_text", side_effect=AssertionError("content read")
            ), mock.patch.object(
                reconciler, "sha256_file", side_effect=AssertionError("content hashed")
            ):
                works, _ = reconciler.build_asset_works(
                    [asset], {"titles": []}, {"works": {}}, {}, min_score=5
                )
            self.assertTrue(works[0]["editorial_blocked"])
            self.assertEqual(works[0]["word_count_kind"], "unavailable")

    def test_catalog_source_bypasses_generic_path_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "verdantvale" / "Trials Of Valor.txt"
            source.parent.mkdir()
            source.write_text("valor " * 100, encoding="utf-8")
            asset = reconciler.Asset(
                database="fixture",
                path=str(source),
                name=source.name,
                entity_id="trials",
                extension=".txt",
                size=source.stat().st_size,
                mtime_ns=source.stat().st_mtime_ns,
                sha256="",
                source_id="fixture",
                role="working-copy",
                authority=20,
                uri="",
            )
            catalog = {
                "titles": [
                    {
                        "status": "Working manuscript",
                        "source_ref": "verdantvale/Trials Of Valor.txt",
                    }
                ]
            }
            works, metrics = reconciler.build_asset_works(
                [asset], catalog, {"works": {}}, {}, min_score=5, extract_content=False
            )
            self.assertEqual(metrics["candidate_assets"], 1)
            self.assertEqual(works[0]["title"], "Trials Of Valor")


if __name__ == "__main__":
    unittest.main()
