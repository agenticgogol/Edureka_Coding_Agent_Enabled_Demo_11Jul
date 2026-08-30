"""Long-term memory reuse: orchestrator.route() must populate
`prior_analysis_context`/`prior_allocation_context` from memory.py once
tickers are resolved, and debate._format_fetched_data must fold that
context into the prompt fed to bull/bear/risk. No real LLM call, no real
SQLite file — `memory.get_past_analysis`/`memory.get_latest_allocation`
and `llm_client.complete` are monkeypatched.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from backend.agent.nodes import orchestrator
from backend.agent.nodes.debate import _format_fetched_data


class RouterPriorContextTests(unittest.TestCase):
    def _router_json(self, **overrides):
        payload = {
            "turn_type": "new_analysis",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals"],
            "needs_fx": False,
            "out_of_scope_reason": None,
            "notes": "test",
            "allocation_amount": None,
            "allocation_currency": None,
            "target_return": None,
            "critique_mode": None,
            "shock_ticker": None,
            "shock_return_shift": None,
            "shock_correlation_to_one": False,
        }
        payload.update(overrides)
        return json.dumps(payload)

    @patch.object(orchestrator, "memory")
    @patch.object(orchestrator, "complete")
    def test_route_injects_prior_analysis_context_for_resolved_ticker(self, mock_complete, mock_memory):
        mock_complete.return_value = self._router_json()
        mock_memory.get_past_analysis.return_value = {
            "ticker": "AAPL",
            "synthesis": "Bull case was strong on margins.",
            "stance": "Buy",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        with patch.object(orchestrator, "_resolve_ticker", return_value=("AAPL", "")):
            state = {"user_message": "Analyze AAPL", "tickers": [], "fetched_data": {}, "transcript": []}
            result = orchestrator.route(state)

        self.assertIn("AAPL", result["prior_analysis_context"])
        self.assertIn("Buy", result["prior_analysis_context"]["AAPL"])
        self.assertIn("margins", result["prior_analysis_context"]["AAPL"])
        self.assertIsNone(result["prior_allocation_context"])

    @patch.object(orchestrator, "memory")
    @patch.object(orchestrator, "complete")
    def test_route_no_prior_analysis_yields_empty_context(self, mock_complete, mock_memory):
        mock_complete.return_value = self._router_json()
        mock_memory.get_past_analysis.return_value = None
        with patch.object(orchestrator, "_resolve_ticker", return_value=("AAPL", "")):
            state = {"user_message": "Analyze AAPL", "tickers": [], "fetched_data": {}, "transcript": []}
            result = orchestrator.route(state)

        self.assertEqual(result["prior_analysis_context"], {})

    @patch.object(orchestrator, "memory")
    @patch.object(orchestrator, "complete")
    def test_route_injects_prior_allocation_context_for_allocation_turn(self, mock_complete, mock_memory):
        mock_complete.return_value = self._router_json(
            turn_type="allocation_new", tickers=["AAPL", "MSFT"], allocation_amount=10000, allocation_currency="USD"
        )
        mock_memory.get_past_analysis.return_value = None
        mock_memory.get_latest_allocation.return_value = {
            "output": {"tickers": ["AAPL", "MSFT"]},
            "synthesis": "Previously weighted 60/40 toward AAPL.",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        with patch.object(orchestrator, "_resolve_ticker", side_effect=lambda t: (t, "")):
            state = {"user_message": "allocate $10k", "user_key": "u1", "tickers": [], "fetched_data": {}, "transcript": []}
            result = orchestrator.route(state)

        mock_memory.get_latest_allocation.assert_called_once_with("u1")
        self.assertIn("60/40", result["prior_allocation_context"])


class DebatePromptPriorContextTests(unittest.TestCase):
    def test_format_fetched_data_includes_prior_analysis_context(self):
        state = {
            "tickers": ["AAPL"],
            "fetched_data": {"AAPL": {"price_fundamentals": {"pe": 30}, "news": None}},
            "prior_analysis_context": {"AAPL": "(2026-01-01) Buy: strong margins"},
        }
        formatted = _format_fetched_data(state)
        self.assertIn("Prior conclusion for AAPL", formatted)
        self.assertIn("strong margins", formatted)
        self.assertIn("revisit and update", formatted)

    def test_format_fetched_data_omits_prior_context_when_absent(self):
        state = {
            "tickers": ["AAPL"],
            "fetched_data": {"AAPL": {"price_fundamentals": {"pe": 30}, "news": None}},
            "prior_analysis_context": {},
        }
        formatted = _format_fetched_data(state)
        self.assertNotIn("Prior conclusion", formatted)

    def test_format_fetched_data_includes_prior_allocation_context(self):
        state = {
            "tickers": ["AAPL", "MSFT"],
            "fetched_data": {},
            "allocation_output": {"weights": {"AAPL": 0.6, "MSFT": 0.4}},
            "prior_allocation_context": "(2026-01-01) Previously weighted 60/40 toward AAPL.",
        }
        formatted = _format_fetched_data(state)
        self.assertIn("Prior allocation conclusion", formatted)
        self.assertIn("60/40", formatted)


if __name__ == "__main__":
    unittest.main()
