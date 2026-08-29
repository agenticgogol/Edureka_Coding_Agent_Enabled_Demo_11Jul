import unittest

from backend.agent.tools.portfolio_optimizer import optimize_portfolio


def _history(slope: float):
    return [
        {"date": f"2020-01-{day:02d}", "close": 100 + slope * day}
        for day in range(1, 101)
    ]


class PortfolioOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.fetched_data = {
            "AAA": {"price_fundamentals": {"price_history": _history(1.0), "sector": "Tech"}},
            "BBB": {"price_fundamentals": {"price_history": _history(0.5), "sector": "Health"}},
        }

    def test_weights_and_amounts_are_deterministic_outputs(self):
        output = optimize_portfolio(["AAA", "BBB"], self.fetched_data, amount=100_000)
        self.assertAlmostEqual(sum(row["weight"] for row in output["allocations"]), 1.0)
        self.assertAlmostEqual(sum(row["amount"] for row in output["allocations"]), 100_000)
        self.assertEqual(output["equal_weight"]["weights"], [0.5, 0.5])
        self.assertIn("historical", output["basis"].lower())

    def test_requires_multiple_tickers(self):
        with self.assertRaisesRegex(RuntimeError, "at least two tickers"):
            optimize_portfolio(["AAA"], self.fetched_data)


if __name__ == "__main__":
    unittest.main()
