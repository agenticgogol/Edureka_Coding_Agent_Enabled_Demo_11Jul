"""Unit tests for `_parse_sources` in news_search.py (Phase 2 item 6):
structured {title, url} source extraction from a synthetic/mocked
tavily-mcp response shape. No network, no MCP subprocess.
"""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from backend.agent.tools.news_search import _parse_sources


class SourceParsingTests(unittest.TestCase):
    def test_extracts_from_json_typed_content_block(self):
        content_items = [
            SimpleNamespace(
                type="json",
                data={"results": [{"title": "AAPL falls on guidance cut", "url": "https://example.com/a"}]},
            )
        ]
        sources = _parse_sources(content_items, [])
        self.assertEqual(sources, [{"title": "AAPL falls on guidance cut", "url": "https://example.com/a"}])

    def test_extracts_from_json_embedded_in_text_block(self):
        text = json.dumps({"results": [{"title": "MSFT beats earnings", "url": "https://example.com/b"}]})
        sources = _parse_sources([], [text])
        self.assertEqual(sources, [{"title": "MSFT beats earnings", "url": "https://example.com/b"}])

    def test_falls_back_to_regex_url_extraction_from_plain_text(self):
        text = "AAPL dropped after a report at https://news.example.com/aapl-drop, more at https://reuters.com/x."
        sources = _parse_sources([], [text])
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["title"], None)
        self.assertEqual(sources[0]["url"], "https://news.example.com/aapl-drop")
        self.assertEqual(sources[1]["url"], "https://reuters.com/x")

    def test_no_urls_returns_empty_list_not_error(self):
        self.assertEqual(_parse_sources([], ["no urls in this text at all"]), [])


if __name__ == "__main__":
    unittest.main()
