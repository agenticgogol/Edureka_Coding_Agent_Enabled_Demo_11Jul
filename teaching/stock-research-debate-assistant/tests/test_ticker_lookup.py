"""Unit test for resolve_company_name's exchange-priority re-ranking
(Mandatory A) — mocks yf.Search's confirmed response shape, no live call."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.agent.tools import ticker_lookup


class _FakeSearch:
    def __init__(self, quotes):
        self.quotes = quotes


class ResolveCompanyNameRankingTests(unittest.TestCase):
    def test_nse_ranks_above_bse_above_us(self):
        # yfinance relevance order deliberately "wrong" (US first) so the
        # re-sort is what makes the test pass, not incidental ordering.
        fake_quotes = [
            {"symbol": "RS", "shortname": "Reliance Steel", "exchDisp": "NYSE"},
            {"symbol": "RELIANCE.BO", "shortname": "Reliance Industries", "exchDisp": "BSE"},
            {"symbol": "RELIANCE.NS", "shortname": "Reliance Industries", "exchDisp": "NSE"},
        ]
        with patch.object(ticker_lookup.yf, "Search", return_value=_FakeSearch(fake_quotes)):
            result = ticker_lookup.resolve_company_name("Reliance")
        self.assertEqual([c["symbol"] for c in result], ["RELIANCE.NS", "RELIANCE.BO", "RS"])

    def test_empty_query_returns_empty(self):
        self.assertEqual(ticker_lookup.resolve_company_name("  "), [])

    def test_search_exception_returns_empty(self):
        with patch.object(ticker_lookup.yf, "Search", side_effect=RuntimeError("boom")):
            self.assertEqual(ticker_lookup.resolve_company_name("Reliance"), [])


if __name__ == "__main__":
    unittest.main()
