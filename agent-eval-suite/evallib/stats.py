"""The only place in this repo that computes eval statistics.

No skill, subagent, or LLM call may compute kappa, TPR/TNR, bias correction,
confidence intervals, or stratified splits inline — import from here instead.
Centralizing this means a formula fix or a bug fix happens once, and every
skill picks it up automatically.
"""

from __future__ import annotations

import random
import warnings
from collections import Counter, defaultdict
from typing import Callable, Hashable, Sequence, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Cohen's kappa
# ---------------------------------------------------------------------------


def cohens_kappa(labels_a: Sequence[Hashable], labels_b: Sequence[Hashable]) -> float:
    """Cohen's kappa for two raters' labels over the same items.

    labels_a[i] and labels_b[i] are the two raters' labels for item i.
    Works for any hashable label type, not just booleans.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError(
            f"labels_a and labels_b must be the same length "
            f"(got {len(labels_a)} and {len(labels_b)})"
        )
    n = len(labels_a)
    if n == 0:
        raise ValueError("cannot compute kappa on zero items")

    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n

    marginal_a = Counter(labels_a)
    marginal_b = Counter(labels_b)
    all_labels = set(marginal_a) | set(marginal_b)
    pe = sum((marginal_a.get(k, 0) / n) * (marginal_b.get(k, 0) / n) for k in all_labels)

    if pe == 1.0:
        # Both raters agree on everything trivially (single label, e.g.) and
        # the denominator (1 - pe) is zero. Perfect agreement -> kappa is
        # conventionally taken as 1.0.
        return 1.0

    return (po - pe) / (1 - pe)


# ---------------------------------------------------------------------------
# Confusion matrix / TPR / TNR
# ---------------------------------------------------------------------------


def confusion(
    human: Sequence[bool], judge: Sequence[bool]
) -> tuple[int, int, int, int]:
    """Returns (TP, FP, TN, FN) treating `human` as ground truth and
    `judge` as the prediction. True == the failure/positive class."""
    if len(human) != len(judge):
        raise ValueError(
            f"human and judge must be the same length (got {len(human)} and {len(judge)})"
        )
    tp = fp = tn = fn = 0
    for h, j in zip(human, judge):
        if h and j:
            tp += 1
        elif not h and j:
            fp += 1
        elif not h and not j:
            tn += 1
        else:  # h and not j
            fn += 1
    return tp, fp, tn, fn


def tpr_tnr(human: Sequence[bool], judge: Sequence[bool]) -> tuple[float, float]:
    """Returns (TPR, TNR) = (sensitivity, specificity) of `judge` against
    `human` ground truth."""
    tp, fp, tn, fn = confusion(human, judge)

    if tp + fn == 0:
        raise ValueError(
            "cannot compute TPR: no positive (human_label=True) items in the sample"
        )
    if tn + fp == 0:
        raise ValueError(
            "cannot compute TNR: no negative (human_label=False) items in the sample"
        )

    tpr = tp / (tp + fn)
    tnr = tn / (tn + fp)
    return tpr, tnr


# ---------------------------------------------------------------------------
# Bias correction
# ---------------------------------------------------------------------------


def bias_correct(p_observed: float, tpr: float, tnr: float) -> float:
    """theta_hat = (p_obs + tnr - 1) / (tpr + tnr - 1)

    Corrects an observed positive rate under an imperfect judge (with known
    TPR/TNR) back to an estimate of the true positive rate.

    Raises ValueError when tpr + tnr <= 1: the judge is at or below chance
    (equivalent to a coin flip or worse), so the correction is undefined
    rather than merely noisy — returning a number here would be actively
    misleading.
    """
    denom = tpr + tnr - 1
    if denom <= 0:
        raise ValueError(
            f"bias correction undefined: tpr + tnr = {tpr + tnr:.4f} <= 1 "
            f"(judge is at or below chance; theta_hat has no valid solution)"
        )

    theta_hat = (p_observed + tnr - 1) / denom

    if theta_hat < 0.0 or theta_hat > 1.0:
        clamped = min(max(theta_hat, 0.0), 1.0)
        warnings.warn(
            f"theta_hat={theta_hat:.4f} outside [0, 1]; clamping to {clamped:.4f}. "
            f"This usually means p_observed, tpr, or tnr is noisy or miscalibrated.",
            stacklevel=2,
        )
        theta_hat = clamped

    return theta_hat


# ---------------------------------------------------------------------------
# Bootstrap confidence interval
# ---------------------------------------------------------------------------


def bootstrap_ci(
    human: Sequence[bool],
    judge: Sequence[bool],
    p_observed: float,
    n_resamples: int = 5000,
    alpha: float = 0.05,
    random_state: int | None = None,
) -> tuple[float, float]:
    """Bootstrap confidence interval for theta_hat.

    Resamples (human, judge) pairs from the test set with replacement,
    re-derives TPR/TNR from each resample, and re-derives theta_hat from
    (p_observed, tpr_resample, tnr_resample). p_observed is held fixed
    (it comes from the production sample being corrected, not the test
    set used to calibrate the judge). Returns the
    (alpha/2, 1 - alpha/2) percentile interval over the resulting
    theta_hat draws.

    Draws where the resampled tpr + tnr <= 1 are skipped (undefined
    theta_hat for that draw) rather than aborting the whole CI. If every
    draw is skipped, raises ValueError.
    """
    if len(human) != len(judge):
        raise ValueError(
            f"human and judge must be the same length (got {len(human)} and {len(judge)})"
        )
    n = len(human)
    if n == 0:
        raise ValueError("cannot bootstrap on zero items")
    if not (0 < alpha < 1):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    rng = random.Random(random_state)
    pairs = list(zip(human, judge))

    theta_draws: list[float] = []
    n_skipped = 0
    for _ in range(n_resamples):
        resample = [pairs[rng.randrange(n)] for _ in range(n)]
        h_resample = [h for h, _ in resample]
        j_resample = [j for _, j in resample]
        try:
            tpr_r, tnr_r = tpr_tnr(h_resample, j_resample)
            theta_r = bias_correct(p_observed, tpr_r, tnr_r)
        except ValueError:
            n_skipped += 1
            continue
        theta_draws.append(theta_r)

    if not theta_draws:
        raise ValueError(
            f"all {n_resamples} bootstrap resamples produced an undefined theta_hat "
            f"(judge at or below chance, or a degenerate resample); cannot compute a CI"
        )
    if n_skipped:
        warnings.warn(
            f"{n_skipped}/{n_resamples} bootstrap resamples were skipped "
            f"(undefined theta_hat); CI is based on the remaining {len(theta_draws)}.",
            stacklevel=2,
        )

    theta_draws.sort()
    lo_idx = int((alpha / 2) * len(theta_draws))
    hi_idx = int((1 - alpha / 2) * len(theta_draws)) - 1
    hi_idx = min(hi_idx, len(theta_draws) - 1)
    lo_idx = min(lo_idx, hi_idx)

    return theta_draws[lo_idx], theta_draws[hi_idx]


# ---------------------------------------------------------------------------
# Stratified split
# ---------------------------------------------------------------------------


def stratified_split(
    records: Sequence[T],
    by: Callable[[T], Hashable],
    ratios: tuple[float, float, float] = (0.2, 0.4, 0.4),
    random_state: int | None = None,
) -> tuple[list[T], list[T], list[T]]:
    """Splits `records` into (train, dev, test) lists, stratified by the key
    `by(record)` returns, so each split gets a proportional share of every
    stratum rather than accidentally isolating a whole stratum in one split.

    `ratios` is (train_ratio, dev_ratio, test_ratio) and must sum to 1.0
    (within floating point tolerance).
    """
    if len(ratios) != 3:
        raise ValueError(f"ratios must have exactly 3 values (train, dev, test), got {ratios}")
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError(f"ratios must sum to 1.0, got {ratios} (sum={sum(ratios)})")
    if any(r < 0 for r in ratios):
        raise ValueError(f"ratios must be non-negative, got {ratios}")

    rng = random.Random(random_state)

    strata: dict[Hashable, list[T]] = defaultdict(list)
    for record in records:
        strata[by(record)].append(record)

    train: list[T] = []
    dev: list[T] = []
    test: list[T] = []
    train_ratio, dev_ratio, _test_ratio = ratios

    for _key, group in strata.items():
        shuffled = group[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = round(n * train_ratio)
        n_dev = round(n * dev_ratio)
        n_train = min(n_train, n)
        n_dev = min(n_dev, n - n_train)

        train.extend(shuffled[:n_train])
        dev.extend(shuffled[n_train : n_train + n_dev])
        test.extend(shuffled[n_train + n_dev :])

    return train, dev, test
