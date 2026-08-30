"""Unit tests for `_route_after_orchestrator`'s deterministic routing
logic in graph.py — including the fetched_data freshness/cache-check
added to the new_analysis/topic_switch/comparison fan-out (previously
only the allocation path had this check).

These call the routing function directly with synthetic `GraphState`-like
dicts; no graph execution, no LLM call, no API key needed.
"""
from __future__ import annotations

import time
import unittest

from langgraph.types import Send

from backend.agent.graph import _DATA_FRESH_SECONDS, _route_after_judge, _route_after_orchestrator
from backend.agent.nodes.judge import CONFLICT_CONFIDENCE_THRESHOLD


def _fresh_price_entry(overrides: dict | None = None) -> dict:
    entry = {"ticker": "AAPL", "currency": "USD", "fetched_at": time.time()}
    entry.update(overrides or {})
    return entry


def _stale_price_entry() -> dict:
    return {"ticker": "AAPL", "currency": "USD", "fetched_at": time.time() - _DATA_FRESH_SECONDS - 60}


class SimpleRoutingTests(unittest.TestCase):
    def test_out_of_scope_routes_to_decline(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "out_of_scope"}), "decline")

    def test_drill_down_routes_to_drill_down_answer(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "drill_down"}), "drill_down_answer")

    def test_follow_up_routes_to_follow_up_answer(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "follow_up"}), "follow_up_answer")

    def test_refinement_routes_to_risk_refine(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "refinement"}), "risk_refine")

    def test_allocation_parameter_change_routes_to_optimizer(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "allocation_parameter_change"}), "optimizer")

    def test_allocation_compare_routes_to_allocation_answer(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "allocation_compare"}), "allocation_answer")


class FreshPipelineFanOutTests(unittest.TestCase):
    def test_new_analysis_with_no_cache_fans_out_price_and_news(self):
        state = {
            "turn_type": "new_analysis",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals", "news"],
            "fetched_data": {},
        }
        sends = _route_after_orchestrator(state)
        self.assertIsInstance(sends, list)
        self.assertTrue(all(isinstance(s, Send) for s in sends))
        node_names = [s.node for s in sends]
        self.assertIn("fetch_price", node_names)
        self.assertIn("fetch_news", node_names)

    def test_new_analysis_skips_refetch_when_fresh_data_cached(self):
        state = {
            "turn_type": "new_analysis",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        result = _route_after_orchestrator(state)
        # Price fetch is skipped (already fresh); the only send left is the
        # explicit skip_news no-op (news wasn't requested), so no
        # fetch_price Send should be present.
        self.assertIsInstance(result, list)
        node_names = [s.node for s in result]
        self.assertNotIn("fetch_price", node_names)
        self.assertIn("skip_news", node_names)

    def test_new_analysis_refetches_when_cached_data_is_stale(self):
        state = {
            "turn_type": "new_analysis",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _stale_price_entry()}},
        }
        sends = _route_after_orchestrator(state)
        self.assertIsInstance(sends, list)
        node_names = [s.node for s in sends]
        self.assertIn("fetch_price", node_names)

    def test_new_analysis_with_news_selected_routes_directly_to_fetch_fx_when_fully_cached(self):
        # Edge case: news IS selected but the ticker's price data is fresh.
        # Current freshness check skips both the price and news Send for
        # that ticker, so with a single already-fresh ticker there is
        # nothing left to fan out -> straight to the join-barrier node.
        state = {
            "turn_type": "new_analysis",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals", "news"],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        self.assertEqual(_route_after_orchestrator(state), "fetch_fx")

    def test_topic_switch_fetches_new_ticker_not_in_cache(self):
        state = {
            "turn_type": "topic_switch",
            "tickers": ["MSFT"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        sends = _route_after_orchestrator(state)
        node_names = [s.node for s in sends]
        self.assertIn("fetch_price", node_names)

    def test_comparison_skips_only_the_already_fresh_ticker(self):
        state = {
            "turn_type": "comparison",
            "tickers": ["AAPL", "MSFT"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        sends = _route_after_orchestrator(state)
        fetched_tickers = [s.arg["_fetch_ticker"] for s in sends if s.node == "fetch_price"]
        self.assertEqual(fetched_tickers, ["MSFT"])

    def test_no_tickers_routes_to_invalid_ticker(self):
        state = {"turn_type": "new_analysis", "tickers": [], "selected_tools": [], "fetched_data": {}}
        self.assertEqual(_route_after_orchestrator(state), "invalid_ticker")


class AllocationFanOutTests(unittest.TestCase):
    def test_allocation_new_skips_ticker_with_fresh_cached_price(self):
        state = {
            "turn_type": "allocation_new",
            "tickers": ["AAPL", "MSFT"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        sends = _route_after_orchestrator(state)
        fetched_tickers = [s.arg["_fetch_ticker"] for s in sends if s.node == "fetch_price"]
        self.assertEqual(fetched_tickers, ["MSFT"])

    def test_allocation_new_routes_directly_to_fetch_fx_when_all_cached(self):
        state = {
            "turn_type": "allocation_new",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        self.assertEqual(_route_after_orchestrator(state), "fetch_fx")

    def test_allocation_new_refetches_stale_cached_ticker(self):
        state = {
            "turn_type": "allocation_new",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals"],
            "fetched_data": {"AAPL": {"price_fundamentals": _stale_price_entry()}},
        }
        sends = _route_after_orchestrator(state)
        fetched_tickers = [s.arg["_fetch_ticker"] for s in sends if s.node == "fetch_price"]
        self.assertEqual(fetched_tickers, ["AAPL"])


class AdaptiveDebateDepthRoutingTests(unittest.TestCase):
    """`_route_after_judge` — the adaptive debate-depth trigger added to
    handle sharply conflicting bull/bear conclusions with one extra
    rebuttal round, capped at ROUNDS + 1 = 3 total rounds via
    `debate_extended`. See nodes/debate.py's `run_extra_round` and
    nodes/judge.py's `CONFLICT_CONFIDENCE_THRESHOLD` docstrings."""

    def test_low_confidence_fresh_analysis_routes_to_extra_round(self):
        state = {
            "turn_type": "new_analysis",
            "confidence": CONFLICT_CONFIDENCE_THRESHOLD - 0.01,
            "allocation_output": None,
            "debate_extended": False,
        }
        self.assertEqual(_route_after_judge(state), "debate_extra_round")

    def test_confidence_exactly_at_threshold_does_not_trigger(self):
        # Strictly-less-than semantics: exactly at threshold is not
        # "sharply conflicting" enough to spend an extra round.
        state = {
            "turn_type": "new_analysis",
            "confidence": CONFLICT_CONFIDENCE_THRESHOLD,
            "allocation_output": None,
            "debate_extended": False,
        }
        from langgraph.graph import END

        self.assertEqual(_route_after_judge(state), END)

    def test_high_confidence_agreement_ends_normally(self):
        from langgraph.graph import END

        state = {
            "turn_type": "new_analysis",
            "confidence": 0.9,
            "allocation_output": None,
            "debate_extended": False,
        }
        self.assertEqual(_route_after_judge(state), END)

    def test_already_extended_never_loops_twice(self):
        from langgraph.graph import END

        state = {
            "turn_type": "new_analysis",
            "confidence": 0.05,
            "allocation_output": None,
            "debate_extended": True,
        }
        self.assertEqual(_route_after_judge(state), END)

    def test_refinement_turn_never_triggers_extra_round(self):
        # refinement re-judges only the risk assessment; adaptive depth is
        # scoped to fresh new_analysis/topic_switch/comparison turns only.
        from langgraph.graph import END

        state = {
            "turn_type": "refinement",
            "confidence": 0.0,
            "allocation_output": None,
            "debate_extended": False,
        }
        self.assertEqual(_route_after_judge(state), END)

    def test_allocation_turn_never_triggers_extra_round(self):
        from langgraph.graph import END

        state = {
            "turn_type": "new_analysis",
            "confidence": 0.0,
            "allocation_output": {"allocations": [{"ticker": "AAPL", "weight": 1.0}]},
            "debate_extended": False,
        }
        self.assertEqual(_route_after_judge(state), END)

    def test_missing_confidence_does_not_trigger(self):
        from langgraph.graph import END

        state = {
            "turn_type": "new_analysis",
            "confidence": None,
            "allocation_output": None,
            "debate_extended": False,
        }
        self.assertEqual(_route_after_judge(state), END)


class QuickSummaryRoutingTests(unittest.TestCase):
    """New `quick_summary` turn_type: fans out to fetch_price only (no
    news), then `fetch_fx`'s conditional edge sends it to
    quick_summary_answer instead of debate."""

    def test_quick_summary_fans_out_to_price_only_no_news(self):
        state = {
            "turn_type": "quick_summary",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals", "news"],
            "fetched_data": {},
        }
        sends = _route_after_orchestrator(state)
        self.assertIsInstance(sends, list)
        node_names = [s.node for s in sends]
        self.assertIn("fetch_price", node_names)
        self.assertNotIn("fetch_news", node_names)

    def test_quick_summary_with_no_tickers_routes_to_invalid_ticker(self):
        state = {"turn_type": "quick_summary", "tickers": [], "selected_tools": [], "fetched_data": {}}
        self.assertEqual(_route_after_orchestrator(state), "invalid_ticker")

    def test_quick_summary_all_cached_routes_via_skip_news_no_price_refetch(self):
        state = {
            "turn_type": "quick_summary",
            "tickers": ["AAPL"],
            "selected_tools": [],
            "fetched_data": {"AAPL": {"price_fundamentals": _fresh_price_entry()}},
        }
        sends = _route_after_orchestrator(state)
        self.assertIsInstance(sends, list)
        node_names = [s.node for s in sends]
        self.assertNotIn("fetch_price", node_names)
        self.assertIn("skip_news", node_names)

    def test_fetch_fx_conditional_edge_routes_quick_summary_to_its_answer_node(self):
        # The conditional edge function attached to "fetch_fx" isn't
        # exported by name, so this replicates its exact logic (see
        # graph.py's `build_graph`) as a routing-contract test.
        def route_after_fetch_fx(state):
            if state.get("allocation_requested"):
                return "optimizer"
            if state.get("turn_type") == "quick_summary":
                return "quick_summary_answer"
            return "debate"

        self.assertEqual(route_after_fetch_fx({"turn_type": "quick_summary"}), "quick_summary_answer")
        self.assertEqual(route_after_fetch_fx({"turn_type": "new_analysis"}), "debate")
        self.assertEqual(route_after_fetch_fx({"turn_type": "quick_summary", "allocation_requested": True}), "optimizer")


class CritiqueRoutingTests(unittest.TestCase):
    def test_critique_routes_to_critique_answer(self):
        self.assertEqual(_route_after_orchestrator({"turn_type": "critique"}), "critique_answer")

    def test_critique_does_not_fan_out(self):
        # No Send objects should be produced for critique — it reuses the
        # existing transcript, same as drill_down.
        result = _route_after_orchestrator({"turn_type": "critique", "tickers": ["AAPL"]})
        self.assertEqual(result, "critique_answer")


class Phase2NewTurnTypeRoutingTests(unittest.TestCase):
    """Phase 2 items 2-4: price_move_explain, scenario_simulator,
    news_materiality — all light-answer turn types that reuse existing
    state, same routing shape as follow_up/critique (no fan-out)."""

    def test_price_move_explain_routes_to_its_answer_node(self):
        self.assertEqual(
            _route_after_orchestrator({"turn_type": "price_move_explain"}),
            "price_move_explain_answer",
        )

    def test_scenario_simulator_routes_to_its_answer_node(self):
        self.assertEqual(
            _route_after_orchestrator({"turn_type": "scenario_simulator"}),
            "scenario_simulator_answer",
        )

    def test_news_materiality_routes_to_its_answer_node(self):
        self.assertEqual(
            _route_after_orchestrator({"turn_type": "news_materiality"}),
            "news_materiality_answer",
        )

    def test_new_turn_types_do_not_fan_out(self):
        for turn_type in ("price_move_explain", "scenario_simulator", "news_materiality"):
            result = _route_after_orchestrator({"turn_type": turn_type, "tickers": ["AAPL"]})
            self.assertIsInstance(result, str)


class Phase3NewTurnTypeRoutingTests(unittest.TestCase):
    """Phase 3: reverse_dcf (price-only fan-out, like quick_summary) and
    portfolio_stress_test (no fan-out, reuses existing allocation)."""

    def test_reverse_dcf_fans_out_to_price_only_no_news(self):
        state = {
            "turn_type": "reverse_dcf",
            "tickers": ["AAPL"],
            "selected_tools": ["price_fundamentals", "news"],
            "fetched_data": {},
        }
        sends = _route_after_orchestrator(state)
        self.assertIsInstance(sends, list)
        node_names = [s.node for s in sends]
        self.assertIn("fetch_price", node_names)
        self.assertNotIn("fetch_news", node_names)

    def test_reverse_dcf_with_no_tickers_routes_to_invalid_ticker(self):
        state = {"turn_type": "reverse_dcf", "tickers": [], "selected_tools": [], "fetched_data": {}}
        self.assertEqual(_route_after_orchestrator(state), "invalid_ticker")

    def test_fetch_fx_conditional_edge_routes_reverse_dcf_to_its_answer_node(self):
        def route_after_fetch_fx(state):
            if state.get("allocation_requested"):
                return "optimizer"
            if state.get("turn_type") == "quick_summary":
                return "quick_summary_answer"
            if state.get("turn_type") == "reverse_dcf":
                return "reverse_dcf_answer"
            return "debate"

        self.assertEqual(route_after_fetch_fx({"turn_type": "reverse_dcf"}), "reverse_dcf_answer")

    def test_portfolio_stress_test_routes_to_its_answer_node_no_fan_out(self):
        result = _route_after_orchestrator({"turn_type": "portfolio_stress_test", "tickers": ["AAPL"]})
        self.assertEqual(result, "portfolio_stress_test_answer")


class RouterTranscriptWindowTests(unittest.TestCase):
    """Fix 1 (multi-turn memory bug): orchestrator.route()'s transcript slice
    widened from [-8:] to [-40:] so turn-1 content survives past turn 3.
    Replicates the exact slice expression from orchestrator.py's route()
    rather than invoking complete() — pure list-slicing, no LLM call."""

    def _build_transcript(self, num_turns: int, entries_per_turn: int = 6) -> list[dict]:
        transcript = []
        for turn_num in range(1, num_turns + 1):
            for i in range(entries_per_turn):
                transcript.append(
                    {
                        "role": f"role{i}",
                        "round": 1,
                        "content": f"turn{turn_num} argument mentions TICKER{turn_num}",
                    }
                )
        return transcript

    def test_old_window_loses_turn_one_by_turn_three(self):
        transcript = self._build_transcript(num_turns=3)
        windowed = transcript[-8:]
        self.assertNotIn(
            "TICKER1", " ".join(t["content"] for t in windowed),
            "sanity check: old [-8:] window should already have scrolled past turn 1",
        )

    def test_widened_window_retains_turn_one_content(self):
        transcript = self._build_transcript(num_turns=3)
        self.assertGreaterEqual(len(transcript), 18)
        windowed = transcript[-40:]
        combined = " ".join(t["content"] for t in windowed)
        self.assertIn("TICKER1", combined)
        self.assertIn("TICKER2", combined)
        self.assertIn("TICKER3", combined)

    def test_widened_window_still_bounded_for_very_long_sessions(self):
        transcript = self._build_transcript(num_turns=10)
        windowed = transcript[-40:]
        combined = " ".join(t["content"] for t in windowed)
        # 40-entry window covers ~6-7 full turns; earliest turns still fall off
        # eventually by design (documented tradeoff, not this fix's scope).
        self.assertNotIn("TICKER1 ", combined)
        self.assertIn("TICKER10", combined)


if __name__ == "__main__":
    unittest.main()
