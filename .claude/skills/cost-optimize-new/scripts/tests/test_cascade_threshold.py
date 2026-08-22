from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cascade_threshold import CascadeExample, tune_threshold


def _examples() -> list[CascadeExample]:
    # cheap model is reliable (correct) when confidence is high, unreliable
    # when confidence is low; expensive model is always correct.
    return [
        CascadeExample(confidence=0.95, cheap_correct=True, expensive_correct=True),
        CascadeExample(confidence=0.92, cheap_correct=True, expensive_correct=True),
        CascadeExample(confidence=0.90, cheap_correct=True, expensive_correct=True),
        CascadeExample(confidence=0.88, cheap_correct=True, expensive_correct=True),
        CascadeExample(confidence=0.60, cheap_correct=False, expensive_correct=True),
        CascadeExample(confidence=0.55, cheap_correct=False, expensive_correct=True),
        CascadeExample(confidence=0.50, cheap_correct=True, expensive_correct=True),  # noisy
        CascadeExample(confidence=0.40, cheap_correct=False, expensive_correct=True),
    ]


def test_tune_threshold_finds_low_escalation_within_tolerance() -> None:
    result = tune_threshold(_examples(), max_accuracy_loss=0.15)
    # Threshold should sit above the unreliable-confidence band (~0.4-0.6)
    assert result.threshold >= 0.6
    assert result.accuracy_loss_vs_expensive_only <= 0.15
    assert 0.0 <= result.escalation_rate <= 1.0


def test_tune_threshold_zero_tolerance_forces_full_escalation_or_raises() -> None:
    # With zero tolerance, only a threshold that never trusts a wrong cheap
    # answer is feasible; since one noisy correct exists at 0.50, threshold
    # must be high enough to escalate everything unreliable.
    result = tune_threshold(_examples(), max_accuracy_loss=0.0)
    assert result.accuracy_loss_vs_expensive_only == 0.0


def test_tune_threshold_infeasible_tolerance_raises() -> None:
    # A cheap model that's always wrong can never meet a near-zero tolerance
    # without escalating everything, which is still feasible (accuracy loss
    # 0) -- so to actually trigger infeasibility we need max_accuracy_loss
    # negative, which is rejected directly.
    with pytest.raises(ValueError):
        tune_threshold(_examples(), max_accuracy_loss=-0.1)


def test_tune_threshold_empty_examples_raises() -> None:
    with pytest.raises(ValueError):
        tune_threshold([])


def test_tune_threshold_prefers_lower_escalation_among_feasible() -> None:
    # Generous tolerance: many thresholds are feasible; must pick the one
    # with the lowest escalation rate (i.e. trusts the cheap model most).
    # Ties on escalation rate break toward the higher (more conservative)
    # threshold, so the minimum observed confidence (0.40) wins here.
    result = tune_threshold(_examples(), max_accuracy_loss=1.0)
    assert result.escalation_rate == 0.0
    assert result.threshold == 0.40
