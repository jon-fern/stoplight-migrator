from __future__ import annotations

import unittest
from collections import OrderedDict

from stoplight_migrator.simple_yaml import dump, load


class SimpleYamlTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        original = OrderedDict(
            [
                ("title", "Sample"),
                (
                    "navigation",
                    [
                        OrderedDict(
                            [
                                ("section", "Intro"),
                                ("contents", [OrderedDict([("page", "Welcome"), ("path", "docs/pages/welcome.mdx")])]),
                            ]
                        )
                    ],
                ),
            ]
        )
        text = dump(original)
        loaded = load(text)
        self.assertEqual(original, loaded)

    def test_parses_existing_docs_yml(self) -> None:
        text = """title: Example\nlayout:\n  tabs-placement: header\nnavigation:\n  - page: Home\n    path: docs/pages/home.mdx\n"""
        data = load(text)
        self.assertEqual(data["title"], "Example")
        self.assertEqual(data["navigation"][0]["page"], "Home")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

