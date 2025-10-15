"""Core logic for migrating Stoplight documentation into Fern docs."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .clients import StoplightClient
from .simple_yaml import dump as dump_yaml
from .simple_yaml import load as load_yaml
from .toc import StoplightNode, slugify


@dataclass
class MigrationConfig:
    docs_yml_path: Path
    pages_dir: Path
    overwrite_navigation: bool = True
    dry_run: bool = False


class StoplightMigrator:
    """Migrates Stoplight documentation to Fern docs."""

    def __init__(self, client: StoplightClient, config: MigrationConfig) -> None:
        self.client = client
        self.config = config
        self.slug_registry: Dict[str, int] = {}
        self.pages_dir = config.pages_dir
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def migrate(self) -> None:
        nodes = self.client.load_tree()
        navigation = []
        for node in nodes:
            nav_item = self._convert_node(node)
            if nav_item is not None:
                navigation.append(nav_item)
        docs_config = self._load_docs_yml()
        if "navigation" not in docs_config or not self.config.overwrite_navigation:
            existing = docs_config.get("navigation", [])
            if not isinstance(existing, list):
                existing = []
            navigation = existing + navigation
        docs_config["navigation"] = navigation
        if self.config.dry_run:
            print(dump_yaml(docs_config))
        else:
            self._write_docs_yml(docs_config)

    def _load_docs_yml(self) -> OrderedDict:
        path = self.config.docs_yml_path
        if path.exists():
            text = path.read_text(encoding="utf-8")
            return load_yaml(text)
        return OrderedDict()

    def _write_docs_yml(self, data: OrderedDict) -> None:
        text = dump_yaml(data)
        self.config.docs_yml_path.write_text(text, encoding="utf-8")

    def _convert_node(self, node: StoplightNode) -> Optional[OrderedDict]:
        if node.is_markdown():
            return self._create_page_entry(node)
        if node.is_section():
            contents = []
            for child in node.children:
                child_nav = self._convert_node(child)
                if child_nav is not None:
                    contents.append(child_nav)
            if not contents:
                return None
            slug = self._ensure_unique_slug(node.slug or slugify(node.title))
            entry = OrderedDict()
            entry["section"] = node.title
            entry["slug"] = slug
            entry["contents"] = contents
            return entry
        if node.children:
            contents = []
            for child in node.children:
                child_nav = self._convert_node(child)
                if child_nav is not None:
                    contents.append(child_nav)
            if contents:
                slug = self._ensure_unique_slug(node.slug or slugify(node.title))
                entry = OrderedDict()
                entry["section"] = node.title
                entry["slug"] = slug
                entry["contents"] = contents
                return entry
        page_entry = self._create_page_entry(node)
        if page_entry is not None:
            return page_entry
        return None

    def _create_page_entry(self, node: StoplightNode) -> Optional[OrderedDict]:
        markdown = self.client.get_markdown(node)
        if markdown is None:
            return None
        slug = self._ensure_unique_slug(node.slug or slugify(node.title))
        filename = f"{slug}.mdx"
        output_path = self.pages_dir / filename
        page_content = self._wrap_markdown(node.title, slug, markdown)
        if not self.config.dry_run:
            output_path.write_text(page_content, encoding="utf-8")
        entry = OrderedDict()
        entry["page"] = node.title
        entry["slug"] = slug
        entry["path"] = str(output_path.relative_to(self.config.docs_yml_path.parent))
        return entry

    def _wrap_markdown(self, title: str, slug: str, markdown: str) -> str:
        front_matter_lines = [
            "---",
            f"slug: {slug}",
            f"title: {self._format_front_matter_value(title)}",
            "---",
            "",
        ]
        body = markdown.strip()
        if body:
            front_matter_lines.append(body)
        front_matter_lines.append("")
        return "\n".join(front_matter_lines)

    @staticmethod
    def _format_front_matter_value(value: str) -> str:
        if not value:
            return "''"
        requires_quotes = any(ch in value for ch in "\n:" ) or value != value.strip()
        if requires_quotes:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return value

    def _ensure_unique_slug(self, slug: str) -> str:
        slug = slugify(slug)
        if slug not in self.slug_registry:
            self.slug_registry[slug] = 1
            return slug
        counter = self.slug_registry[slug] + 1
        base = slug
        while f"{base}-{counter}" in self.slug_registry:
            counter += 1
        unique_slug = f"{base}-{counter}"
        self.slug_registry[base] = counter
        self.slug_registry[unique_slug] = 1
        return unique_slug

