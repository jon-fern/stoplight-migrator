"""Clients for retrieving Stoplight documentation content."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .toc import StoplightNode, TocParser


class StoplightClient:
    """Common interface for reading Stoplight documentation data."""

    def load_tree(self) -> List[StoplightNode]:
        raise NotImplementedError

    def get_markdown(self, node: StoplightNode) -> Optional[str]:
        raise NotImplementedError


@dataclass
class StoplightDirectoryClient(StoplightClient):
    """Reads Stoplight documentation from a local export directory."""

    root: Path
    toc_filename: str = "table_of_contents.json"
    documents_dirname: str = "documents"

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if not self.root.exists():
            raise FileNotFoundError(f"Stoplight export directory '{self.root}' does not exist")

    def _load_raw_tree(self) -> Iterable[dict]:
        toc_path = self._find_table_of_contents()
        with toc_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            for key in ("items", "contents", "children"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        if isinstance(data, list):
            return data
        raise ValueError(f"Unsupported table of contents format: {type(data)}")

    def _find_table_of_contents(self) -> Path:
        toc_path = self.root / self.toc_filename
        if toc_path.exists():
            return toc_path
        for candidate in self.root.rglob(self.toc_filename):
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(
            f"Unable to locate a '{self.toc_filename}' file under {self.root}. "
            "Expected a Stoplight export directory containing Stoplight metadata."
        )

    def load_tree(self) -> List[StoplightNode]:
        parser = TocParser(self._load_raw_tree())
        return parser.parse()

    def get_markdown(self, node: StoplightNode) -> Optional[str]:
        slug = node.slug or node.id or node.raw.get("slug")
        if not slug:
            return None
        documents_dir = self.root / self.documents_dirname
        for candidate in self._candidate_markdown_paths(documents_dir, slug):
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        fallback = self._find_markdown_file(slug)
        if fallback and fallback.exists():
            return fallback.read_text(encoding="utf-8")
        # Some Stoplight exports embed markdown inline under the node.
        return extract_markdown_from_node(node.raw)

    @staticmethod
    def _candidate_markdown_paths(documents_dir: Path, slug: str) -> Iterable[Path]:
        base = slug.replace("/", "-")
        extensions = (".md", ".mdx", ".markdown")
        for extension in extensions:
            yield documents_dir / f"{base}{extension}"

    def _find_markdown_file(self, slug: str) -> Optional[Path]:
        base = slug.replace("/", "-")
        extensions = (".md", ".mdx", ".markdown")
        for extension in extensions:
            pattern = f"{base}{extension}"
            for candidate in self.root.rglob(pattern):
                if self.documents_dirname in candidate.parts:
                    return candidate
        return None


class StoplightHostedDocsClient(StoplightClient):
    """Fetches documentation from a hosted Stoplight Elements site."""

    def __init__(self, base_url: str) -> None:
        if not base_url:
            raise ValueError("Base URL must be provided")
        self.base_url = base_url.rstrip("/")
        self._next_data: Optional[dict] = None
        self._nodes_by_id: Dict[str, dict] = {}
        self._toc: List[StoplightNode] = []
        self._load()

    def _load(self) -> None:
        next_data = self._fetch_next_data()
        if next_data is None:
            raise RuntimeError(
                "Unable to locate Next.js data from Stoplight documentation site."
            )
        self._next_data = next_data
        self._nodes_by_id = collect_nodes_by_id(next_data)
        raw_toc = find_table_of_contents(next_data)
        if raw_toc is None:
            raise RuntimeError("Failed to find table of contents in Stoplight data")
        parser = TocParser(raw_toc)
        self._toc = parser.parse()

    def _fetch_next_data(self) -> Optional[dict]:
        html = http_get(self.base_url)
        if html is None:
            return None
        match = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if match:
            json_text = match.group(1).strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
        assign_match = re.search(r"window\.__NEXT_DATA__\s*=\s*(\{)", html)
        if assign_match:
            start = assign_match.start(1)
            json_text = _extract_json_object(html, start)
            if json_text:
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    return None
        return None

    def load_tree(self) -> List[StoplightNode]:
        return list(self._toc)

    def get_markdown(self, node: StoplightNode) -> Optional[str]:
        raw = node.raw
        inline = extract_markdown_from_node(raw)
        if inline:
            return inline
        node_id = raw.get("id") or raw.get("targetId")
        if node_id and node_id in self._nodes_by_id:
            referenced = extract_markdown_from_node(self._nodes_by_id[node_id])
            if referenced:
                return referenced
        slug = node.slug or raw.get("slug")
        if slug:
            url = urllib.parse.urljoin(self.base_url + "/", f"{slug}.md")
            markdown = http_get(url)
            if markdown:
                return markdown
        return None


def http_get(url: str) -> Optional[str]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        return None


def collect_nodes_by_id(data: dict) -> Dict[str, dict]:
    nodes: Dict[str, dict] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            node_id = value.get("id")
            node_type = value.get("type") or value.get("kind")
            if node_id and node_type:
                nodes[node_id] = value
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return nodes


def find_table_of_contents(data: dict) -> Optional[Iterable[dict]]:
    candidates: List[Iterable[dict]] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key in ("tableOfContents", "toc", "tree", "items", "contents", "children"):
                candidate = value.get(key)
                if isinstance(candidate, list) and _looks_like_toc(candidate):
                    candidates.append(candidate)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return candidates[0] if candidates else None


def _looks_like_toc(items: Iterable[dict]) -> bool:
    sample = list(items)[:5]
    if not sample:
        return False
    return all(isinstance(item, dict) and any(k in item for k in ("type", "kind", "title")) for item in sample)


def extract_markdown_from_node(node: dict) -> Optional[str]:
    markdown_fields = [
        ("markdown",),
        ("data", "markdown"),
        ("document", "markdown"),
        ("body", "markdown"),
    ]
    for path in markdown_fields:
        current = node
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:  # Only executed if loop wasn't broken
            if isinstance(current, str):
                return current
            if isinstance(current, dict):
                for text_key in ("content", "raw", "plain", "text"):
                    if text_key in current and isinstance(current[text_key], str):
                        return current[text_key]
    return None


def _extract_json_object(source: str, start: int) -> Optional[str]:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[start : index + 1]
    return None

