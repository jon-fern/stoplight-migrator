from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict
from unittest import TestCase
from unittest.mock import patch

from stoplight_migrator.clients import StoplightDirectoryClient, StoplightHostedDocsClient


class StoplightDirectoryClientTests(TestCase):
    def test_finds_nested_table_of_contents_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "export" / "data"
            nested.mkdir(parents=True)
            toc_path = nested / "table_of_contents.json"
            toc_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "intro",
                            "title": "Introduction",
                            "type": "group",
                            "items": [
                                {"id": "doc", "title": "Welcome", "type": "markdown", "slug": "welcome"}
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            documents = nested / "documents"
            documents.mkdir()
            (documents / "welcome.md").write_text("# Welcome", encoding="utf-8")

            client = StoplightDirectoryClient(root)
            nodes = client.load_tree()

            self.assertEqual(len(nodes), 1)
            child = nodes[0].children[0]
            self.assertEqual(child.slug, "welcome")
            markdown = client.get_markdown(child)
            self.assertIn("# Welcome", markdown or "")


class StoplightHostedDocsClientTests(TestCase):
    def _build_next_data(self) -> Dict[str, object]:
        return {
            "props": {
                "pageProps": {
                    "tableOfContents": [
                        {"id": "doc", "title": "Doc", "type": "markdown", "slug": "doc"}
                    ]
                }
            }
        }

    @patch("stoplight_migrator.clients.http_get")
    def test_parses_next_data_with_additional_script_attributes(self, mock_http_get) -> None:
        base_url = "https://example.com/docs"
        html = (
            '<html><head><script id="__NEXT_DATA__" type="application/json" data-ssr="true">'
            f"{json.dumps(self._build_next_data())}" "</script></head></html>"
        )

        def side_effect(url: str) -> str | None:
            if url == base_url:
                return html
            if url == f"{base_url}/doc.md":
                return "# Doc"
            return None

        mock_http_get.side_effect = side_effect

        client = StoplightHostedDocsClient(base_url)
        nodes = client.load_tree()

        self.assertEqual(len(nodes), 1)
        markdown = client.get_markdown(nodes[0])
        self.assertIn("# Doc", markdown or "")

    @patch("stoplight_migrator.clients.http_get")
    def test_parses_window_assignment_fallback(self, mock_http_get) -> None:
        base_url = "https://example.com/alt"
        next_data = json.dumps(self._build_next_data())
        html = (
            "<html><head><script>window.__NEXT_DATA__ = "
            f"{next_data}"
            "</script></head></html>"
        )

        def side_effect(url: str) -> str | None:
            if url == base_url:
                return html
            if url == f"{base_url}/doc.md":
                return "# Doc"
            return None

        mock_http_get.side_effect = side_effect

        client = StoplightHostedDocsClient(base_url)
        nodes = client.load_tree()

        self.assertEqual(len(nodes), 1)
        markdown = client.get_markdown(nodes[0])
        self.assertIn("# Doc", markdown or "")

