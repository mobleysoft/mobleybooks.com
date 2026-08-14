from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
