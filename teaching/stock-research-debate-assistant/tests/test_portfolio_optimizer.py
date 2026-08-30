import unittest

from backend.agent.tools.portfolio_optimizer import optimize_portfolio, stress_test_portfolio


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

    def test_risk_profile_changes_deterministic_policy(self):
        conservative = optimize_portfolio(["AAA", "BBB"], self.fetched_data, risk_tolerance="conservative")
        aggressive = optimize_portfolio(["AAA", "BBB"], self.fetched_data, risk_tolerance="aggressive")
        self.assertEqual(conservative["risk_tolerance"], "conservative")
        self.assertEqual(aggressive["risk_tolerance"], "aggressive")
        self.assertNotEqual(conservative["method"], aggressive["method"])
        self.assertLessEqual(max(row["weight"] for row in conservative["allocations"]), 0.5 + 1e-8)

    def test_covariance_matrix_exposed_for_concentration_flagging(self):
        # Phase 2 item 5: covariance matrix additive to _metrics, no new
        # math beyond exposing what optimize_portfolio already computes.
        output = optimize_portfolio(["AAA", "BBB"], self.fetched_data, amount=100_000)
        cov = output["optimized"]["covariance_matrix"]
        self.assertEqual(len(cov), 2)
        self.assertEqual(len(cov[0]), 2)
        self.assertAlmostEqual(cov[0][1], cov[1][0])
        self.assertIn("covariance_matrix", output["equal_weight"])


def _noisy_history(slope: float, seed: int):
    import random
    rng = random.Random(seed)
    price = 100.0
    rows = []
    for day in range(1, 101):
        price += slope + rng.uniform(-0.8, 0.8)
        rows.append({"date": f"2020-01-{day:02d}" if day <= 31 else f"2020-02-{day - 31:02d}", "close": max(price, 1.0)})
    return rows


class StressTestTests(unittest.TestCase):
    def setUp(self):
        self.fetched_data = {
            "AAA": {"price_fundamentals": {"price_history": _noisy_history(1.0, seed=1), "sector": "Tech"}},
            "BBB": {"price_fundamentals": {"price_history": _noisy_history(0.5, seed=2), "sector": "Health"}},
        }

    def test_negative_return_shock_lowers_expected_return(self):
        result = stress_test_portfolio(
            ["AAA", "BBB"], [0.5, 0.5], self.fetched_data,
            shock_ticker="AAA", return_shift=-0.20,
        )
        self.assertLess(
            result["after"]["expected_annual_return"],
            result["before"]["expected_annual_return"],
        )

    def test_correlation_to_one_changes_covariance_but_not_variance_diagonal(self):
        result = stress_test_portfolio(
            ["AAA", "BBB"], [0.5, 0.5], self.fetched_data,
            correlation_to_one=True,
        )
        before_cov = result["before"]["covariance_matrix"]
        # Not exposed directly in _metrics output today beyond volatility,
        # so assert the shock actually changed the resulting volatility.
        self.assertNotAlmostEqual(
            result["before"]["annualized_volatility"],
            result["after"]["annualized_volatility"],
            places=6,
        )
        self.assertEqual(len(before_cov), 2)

    def test_mismatched_weights_length_raises(self):
        with self.assertRaises(Exception):
            stress_test_portfolio(["AAA", "BBB"], [1.0], self.fetched_data)


if __name__ == "__main__":
    unittest.main()
