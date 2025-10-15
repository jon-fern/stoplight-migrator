from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from stoplight_migrator.clients import StoplightDirectoryClient
from stoplight_migrator.migrator import MigrationConfig, StoplightMigrator
from stoplight_migrator.simple_yaml import load as load_yaml


class StoplightMigratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.docs_yml = self.temp_dir / "docs.yml"
        self.docs_yml.write_text(
            "title: Sample Docs\nnavigation:\n  - page: Existing\n    path: docs/pages/existing.mdx\n",
            encoding="utf-8",
        )
        self.docs_root = self.temp_dir / "docs"
        (self.docs_root / "pages").mkdir(parents=True, exist_ok=True)

    def test_migrator_generates_navigation_and_pages(self) -> None:
        fixture_root = Path(__file__).parent / "fixtures" / "sample_project"
        client = StoplightDirectoryClient(fixture_root)
        config = MigrationConfig(
            docs_yml_path=self.docs_yml,
            pages_dir=self.docs_root / "pages",
            overwrite_navigation=True,
        )
        migrator = StoplightMigrator(client=client, config=config)
        migrator.migrate()

        docs_config = load_yaml(self.docs_yml.read_text(encoding="utf-8"))
        navigation = docs_config["navigation"]
        self.assertEqual(len(navigation), 2)
        introduction = navigation[0]
        self.assertEqual(introduction["section"], "Introduction")
        self.assertEqual(introduction["slug"], "introduction")
        self.assertEqual(len(introduction["contents"]), 2)
        overview = introduction["contents"][0]
        self.assertEqual(overview["page"], "Overview")
        self.assertEqual(overview["path"], "docs/pages/overview.mdx")

        error_page = navigation[1]
        self.assertEqual(error_page["slug"], "error-handling")

        overview_file = self.docs_root / "pages" / "overview.mdx"
        self.assertTrue(overview_file.exists())
        contents = overview_file.read_text(encoding="utf-8")
        self.assertIn("slug: overview", contents)
        self.assertIn("# Overview", contents)

    def test_append_navigation(self) -> None:
        fixture_root = Path(__file__).parent / "fixtures" / "sample_project"
        client = StoplightDirectoryClient(fixture_root)
        config = MigrationConfig(
            docs_yml_path=self.docs_yml,
            pages_dir=self.docs_root / "pages",
            overwrite_navigation=False,
        )
        migrator = StoplightMigrator(client=client, config=config)
        migrator.migrate()

        docs_config = load_yaml(self.docs_yml.read_text(encoding="utf-8"))
        navigation = docs_config["navigation"]
        self.assertEqual(len(navigation), 3)
        self.assertEqual(navigation[0]["page"], "Existing")
        self.assertEqual(navigation[1]["section"], "Introduction")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

