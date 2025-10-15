"""Command line interface for the Stoplight to Fern migrator."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .clients import StoplightDirectoryClient, StoplightHostedDocsClient
from .migrator import MigrationConfig, StoplightMigrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate Stoplight documentation to Fern docs")
    parser.add_argument(
        "source",
        help="Stoplight docs URL or path to a Stoplight export directory containing table_of_contents.json",
    )
    parser.add_argument(
        "--docs-yml",
        dest="docs_yml",
        default="docs.yml",
        help="Path to the Fern docs.yml file (default: docs.yml)",
    )
    parser.add_argument(
        "--docs-root",
        dest="docs_root",
        default="docs",
        help="Root directory containing Fern docs content (default: docs)",
    )
    parser.add_argument(
        "--pages-dir",
        dest="pages_dir",
        default=None,
        help="Directory to write generated markdown pages (default: <docs-root>/pages)",
    )
    parser.add_argument(
        "--append-navigation",
        action="store_true",
        help="Append generated navigation instead of replacing the existing navigation section",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without writing any files",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source = args.source
    pages_dir = Path(args.pages_dir) if args.pages_dir else Path(args.docs_root) / "pages"
    docs_yml_path = Path(args.docs_yml)

    if Path(source).exists():
        client = StoplightDirectoryClient(Path(source))
    else:
        client = StoplightHostedDocsClient(source)

    config = MigrationConfig(
        docs_yml_path=docs_yml_path,
        pages_dir=pages_dir,
        overwrite_navigation=not args.append_navigation,
        dry_run=args.dry_run,
    )
    migrator = StoplightMigrator(client=client, config=config)
    migrator.migrate()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

