"""Unit test for the financial-statement serialization helper (Phase 3
item 1) — synthetic pandas DataFrame, no network call."""
from __future__ import annotations

import unittest

import pandas as pd

from backend.agent.tools.price_fundamentals import _serialize_financial_statement


class SerializeFinancialStatementTests(unittest.TestCase):
    def test_transposes_rows_and_columns_and_handles_nan(self):
        df = pd.DataFrame(
            {
                pd.Timestamp("2024-12-31"): {"Total Revenue": 1000.0, "Net Income": float("nan")},
                pd.Timestamp("2023-12-31"): {"Total Revenue": 900.0, "Net Income": 100.0},
            }
        )
        result = _serialize_financial_statement(df)
        self.assertEqual(set(result.keys()), {"2024-12-31", "2023-12-31"})
        self.assertEqual(result["2024-12-31"]["Total Revenue"], 1000.0)
        self.assertIsNone(result["2024-12-31"]["Net Income"])
        self.assertEqual(result["2023-12-31"]["Net Income"], 100.0)

    def test_empty_dataframe_returns_empty_dict(self):
        self.assertEqual(_serialize_financial_statement(pd.DataFrame()), {})

    def test_none_returns_empty_dict(self):
        self.assertEqual(_serialize_financial_statement(None), {})


if __name__ == "__main__":
    unittest.main()
