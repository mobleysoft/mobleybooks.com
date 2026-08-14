from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import package_release


class PackageReleaseTests(unittest.TestCase):
    def fixture(self, root: Path, *, author: str = package_release.AUTHOR, status: str = "Complete manuscript") -> dict:
        source = root / "source.txt"
        paragraphs = [f"Chapter {index}: Trial\n\n" + ("A complete sentence follows. " * 100) for index in range(1, 4)]
        source.write_text("\n\n".join(paragraphs), encoding="utf-8")
        cover = root / "project" / "assets" / "covers" / "trial-cover-v1.png"
        cover.parent.mkdir(parents=True, exist_ok=True)
        cover.write_bytes(b"png")
        return {
            "slug": "trial",
            "title": "Trial",
            "author": author,
            "status": status,
            "source_ref": str(source),
        }

    @mock.patch.object(package_release.subprocess, "run")
    def test_packages_only_clean_complete_canonical_author(self, run: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entry = self.fixture(root)
            output = root / "output"
            original_project = package_release.PROJECT_ROOT
            package_release.PROJECT_ROOT = root / "project"
            try:
                def emit_epub(command: list[str], check: bool) -> subprocess.CompletedProcess:
                    Path(command[-1]).write_bytes(b"epub")
                    return subprocess.CompletedProcess(command, 0)

                run.side_effect = emit_epub
                record = package_release.package_entry(entry, output)
            finally:
                package_release.PROJECT_ROOT = original_project
            self.assertEqual("candidate_pending_final_editorial_review", record["status"])
            self.assertEqual(package_release.AUTHOR, record["author"])
            self.assertTrue((output / "trial" / "release-candidate.json").is_file())
            command = run.call_args.args[0]
            self.assertIn("lang=en-US", command)
            self.assertIn(str(output / "trial" / "epub-manuscript.md"), command)
            self.assertEqual(
                record,
                json.loads((output / "trial" / "release-candidate.json").read_text()),
            )

    def test_rejects_noncanonical_author_and_noncomplete_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "author must be"):
                package_release.package_entry(self.fixture(root, author="Someone Else"), root / "out")
            with self.assertRaisesRegex(ValueError, "not Complete manuscript"):
                package_release.package_entry(self.fixture(root, status="Working manuscript"), root / "out")


if __name__ == "__main__":
    unittest.main()
