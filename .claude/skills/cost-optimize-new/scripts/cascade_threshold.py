"""Tune a model-cascade confidence threshold against a labeled set.

A cascade routes a query to a cheap model first; if the cheap model's
logprob-derived confidence is below the threshold, it escalates to the
expensive model. This module picks the threshold that keeps escalation rate
(and therefore cost) as low as possible while keeping accuracy loss vs.
always-using-the-expensive-model within a tolerance.

Input: a labeled set of (cheap_model_confidence, cheap_model_correct,
expensive_model_correct) triples — one per example, already computed by
whatever ran both models against the labeled set. This module does not call
any model itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CascadeExample:
    confidence: float  # cheap model's logprob-derived confidence, 0-1
    cheap_correct: bool
    expensive_correct: bool


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    escalation_rate: float  # fraction of examples routed to the expensive model
    accuracy: float  # accuracy of the cascade as a whole at this threshold
    accuracy_loss_vs_expensive_only: float  # expensive-only accuracy minus cascade accuracy


def _cascade_accuracy(examples: Sequence[CascadeExample], threshold: float) -> tuple[float, float]:
    """Returns (accuracy, escalation_rate) for routing at this threshold:
    confidence >= threshold -> trust the cheap model's answer;
    confidence < threshold -> escalate to the expensive model's answer."""
    if not examples:
        raise ValueError("cannot tune a threshold on zero examples")
    n_correct = 0
    n_escalated = 0
    for ex in examples:
        if ex.confidence >= threshold:
            n_correct += int(ex.cheap_correct)
        else:
            n_correct += int(ex.expensive_correct)
            n_escalated += 1
    n = len(examples)
    return n_correct / n, n_escalated / n


def tune_threshold(
    examples: Sequence[CascadeExample],
    max_accuracy_loss: float = 0.02,
    candidate_thresholds: Sequence[float] | None = None,
) -> ThresholdResult:
    """Finds the threshold that minimizes escalation rate subject to
    accuracy loss (vs. always using the expensive model) staying within
    `max_accuracy_loss`.

    Raises ValueError if no candidate threshold satisfies the accuracy-loss
    constraint — that means the cheap model isn't a viable cascade stage for
    this task at any threshold, not that the tuning failed to search hard
    enough.
    """
    if not examples:
        raise ValueError("cannot tune a threshold on zero examples")
    if max_accuracy_loss < 0:
        raise ValueError(f"max_accuracy_loss must be non-negative, got {max_accuracy_loss}")

    expensive_only_accuracy = sum(ex.expensive_correct for ex in examples) / len(examples)

    if candidate_thresholds is None:
        # Every distinct observed confidence value, plus 0.0 and 1.0, is a
        # sufficient candidate set: accuracy/escalation-rate only change at
        # a threshold that crosses an observed confidence value.
        candidate_thresholds = sorted({0.0, 1.0} | {ex.confidence for ex in examples})

    feasible: list[ThresholdResult] = []
    for t in candidate_thresholds:
        accuracy, escalation_rate = _cascade_accuracy(examples, t)
        loss = expensive_only_accuracy - accuracy
        if loss <= max_accuracy_loss:
            feasible.append(
                ThresholdResult(
                    threshold=t,
                    escalation_rate=escalation_rate,
                    accuracy=accuracy,
                    accuracy_loss_vs_expensive_only=loss,
                )
            )

    if not feasible:
        raise ValueError(
            f"no threshold keeps accuracy loss within {max_accuracy_loss:.4f} "
            f"of the expensive-only accuracy ({expensive_only_accuracy:.4f}); "
            f"the cheap model is not a viable cascade stage for this task "
            f"at the given tolerance"
        )

    # Among feasible thresholds, prefer the lowest escalation rate (cheapest);
    # break ties by preferring the higher threshold (more conservative /
    # more likely to generalize past this exact labeled set).
    feasible.sort(key=lambda r: (r.escalation_rate, -r.threshold))
    return feasible[0]
