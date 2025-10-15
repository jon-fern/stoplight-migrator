"""Parsing Stoplight table of contents structures."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional


@dataclass
class StoplightNode:
    """Represents a node in the Stoplight documentation tree."""

    type: str
    title: str
    slug: Optional[str]
    id: Optional[str]
    raw: dict
    children: List["StoplightNode"] = field(default_factory=list)

    def is_markdown(self) -> bool:
        return self.type in {"article", "markdown", "page", "md"}

    def is_section(self) -> bool:
        return self.type in {"group", "section", "chapter", "node", "http_service"}


class TocParser:
    """Converts Stoplight raw TOC data into :class:`StoplightNode` objects."""

    def __init__(self, items: Iterable[dict]):
        self.items = list(items)

    def parse(self) -> List[StoplightNode]:
        return [node for node in (self._parse_item(item) for item in self.items) if node is not None]

    def _parse_item(self, item: dict) -> Optional[StoplightNode]:
        if not isinstance(item, dict):
            return None
        node_type = (item.get("type") or item.get("kind") or "").lower()
        title = item.get("title") or item.get("name") or item.get("label")
        if not title:
            title = item.get("slug") or item.get("id") or "Untitled"
        slug = item.get("slug") or item.get("uriSlug") or item.get("permalink")
        node_id = item.get("id") or item.get("targetId")
        children_data = None
        for key in ("items", "children", "contents", "nodes"):
            if key in item and isinstance(item[key], list):
                children_data = item[key]
                break
        if node_type in {"group", "section", "chapter", "http_service", "http-service"}:
            children = [
                child for child in (self._parse_item(child) for child in (children_data or [])) if child is not None
            ]
            return StoplightNode(
                type="group",
                title=title,
                slug=slug,
                id=node_id,
                raw=item,
                children=children,
            )
        if node_type in {"markdown", "page", "article", "md", "http_service.operation"}:
            return StoplightNode(
                type="article",
                title=title,
                slug=slug,
                id=node_id,
                raw=item,
                children=[],
            )
        if children_data:
            children = [
                child for child in (self._parse_item(child) for child in children_data) if child is not None
            ]
            return StoplightNode(
                type="group",
                title=title,
                slug=slug,
                id=node_id,
                raw=item,
                children=children,
            )
        if item.get("markdown"):
            return StoplightNode(
                type="article",
                title=title,
                slug=slug,
                id=node_id,
                raw=item,
                children=[],
            )
        return None


_slug_pattern = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    replaced = _slug_pattern.sub("-", lowered)
    slug = replaced.strip("-")
    return slug or "page"

