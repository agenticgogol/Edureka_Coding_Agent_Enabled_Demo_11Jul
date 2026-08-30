"""Unit tests for the reverse single-stage DCF solve (Phase 3 item 3),
known-answer inputs, no network/LLM call."""
from __future__ import annotations

import unittest

from backend.agent.tools.valuation import ReverseDCFError, implied_growth_rate


class ImpliedGrowthRateTests(unittest.TestCase):
    def test_known_answer_solves_correctly(self):
        # market_cap = fcf * (1+g) / (r - g); pick r=0.10, g known=0.04,
        # fcf=100 -> market_cap = 100*1.04/0.06 = 1733.33...
        market_cap = 100 * 1.04 / 0.06
        result = implied_growth_rate(market_cap, 100, discount_rate=0.10)
        self.assertAlmostEqual(result["implied_growth_rate"], 0.04, places=6)
        self.assertEqual(result["discount_rate"], 0.10)

    def test_zero_market_cap_raises(self):
        with self.assertRaises(ReverseDCFError):
            implied_growth_rate(0, 100)

    def test_negative_fcf_raises(self):
        with self.assertRaises(ReverseDCFError):
            implied_growth_rate(1000, -50)

    def test_fcf_large_relative_to_price_implies_negative_growth(self):
        # High FCF yield relative to price implies the market expects decline.
        result = implied_growth_rate(1000, 300, discount_rate=0.10)
        self.assertLess(result["implied_growth_rate"], 0)


if __name__ == "__main__":
    unittest.main()
