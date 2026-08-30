"""Unit tests for the orchestrator/judge `_extract_json` parsing helpers.

These feed synthetic raw strings directly into the parsing functions — no
real LLM call, no API key needed. They cover: valid JSON, JSON wrapped in
markdown fences (the common LLM-output shape these functions normalize),
and malformed JSON raising the dedicated error type (which `route`/
`run_judge` then use to trigger a single re-prompt retry).
"""
from __future__ import annotations

import unittest

from backend.agent.nodes.orchestrator import RouterJSONError, _extract_json as orchestrator_extract_json
from backend.agent.nodes.judge import JudgeJSONError, _extract_json as judge_extract_json


class OrchestratorJSONParsingTests(unittest.TestCase):
    def test_parses_valid_json(self):
        raw = '{"turn_type": "new_analysis", "tickers": ["AAPL"], "selected_tools": ["price_fundamentals"]}'
        parsed = orchestrator_extract_json(raw)
        self.assertEqual(parsed["turn_type"], "new_analysis")
        self.assertEqual(parsed["tickers"], ["AAPL"])

    def test_parses_json_wrapped_in_markdown_fences(self):
        raw = '```json\n{"turn_type": "topic_switch", "tickers": ["MSFT"]}\n```'
        parsed = orchestrator_extract_json(raw)
        self.assertEqual(parsed["turn_type"], "topic_switch")

    def test_raises_router_json_error_on_malformed_json(self):
        raw = "Sure! Here's my classification: turn_type is new_analysis for AAPL."
        with self.assertRaises(RouterJSONError):
            orchestrator_extract_json(raw)

    def test_raises_router_json_error_on_truncated_json(self):
        raw = '{"turn_type": "new_analysis", "tickers": ["AAPL"'
        with self.assertRaises(RouterJSONError):
            orchestrator_extract_json(raw)


class JudgeJSONParsingTests(unittest.TestCase):
    def test_parses_valid_json(self):
        raw = '{"stance": "Buy", "reasoning": "Strong fundamentals.", "confidence": 0.8}'
        parsed = judge_extract_json(raw)
        self.assertEqual(parsed["stance"], "Buy")
        self.assertEqual(parsed["confidence"], 0.8)

    def test_parses_json_wrapped_in_markdown_fences(self):
        raw = '```\n{"stance": "Hold", "reasoning": "Mixed signals.", "confidence": 0.4}\n```'
        parsed = judge_extract_json(raw)
        self.assertEqual(parsed["stance"], "Hold")

    def test_raises_judge_json_error_on_malformed_json(self):
        raw = "Stance: Buy. Reasoning: strong fundamentals."
        with self.assertRaises(JudgeJSONError):
            judge_extract_json(raw)

    def test_raises_judge_json_error_on_trailing_garbage(self):
        raw = '{"stance": "Sell", "reasoning": "Weak outlook."} extra text after json'
        with self.assertRaises(JudgeJSONError):
            judge_extract_json(raw)


if __name__ == "__main__":
    unittest.main()
