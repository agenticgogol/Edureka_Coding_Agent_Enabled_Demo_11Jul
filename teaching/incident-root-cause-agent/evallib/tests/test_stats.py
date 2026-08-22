from __future__ import annotations

from collections import Counter

import pytest

from evallib.stats import (
    bias_correct,
    bootstrap_ci,
    cohens_kappa,
    confusion,
    stratified_split,
    tpr_tnr,
)

# ---------------------------------------------------------------------------
# cohens_kappa
# ---------------------------------------------------------------------------


def test_kappa_hand_computed_2x2() -> None:
    # Classic textbook example (Landis & Koch style 2x2):
    # rater A: 10 items yes, 10 items no (20 total)
    # Confusion: both-yes=8, A-yes/B-no=2, A-no/B-yes=1, both-no=9
    a = [True] * 10 + [False] * 10
    b = [True] * 8 + [False] * 2 + [True] * 1 + [False] * 9

    # marginals: a has 10 True / 10 False; b has 9 True / 11 False
    n = 20
    po = (8 + 9) / n  # 0.85
    pe = (10 / n) * (9 / n) + (10 / n) * (11 / n)  # 0.5
    expected_kappa = (po - pe) / (1 - pe)  # 0.7

    kappa = cohens_kappa(a, b)
    assert kappa == pytest.approx(expected_kappa, abs=1e-9)
    assert kappa == pytest.approx(0.7, abs=1e-9)


def test_kappa_perfect_agreement_is_one() -> None:
    a = [True, False, True, True, False]
    assert cohens_kappa(a, a) == pytest.approx(1.0)


def test_kappa_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cohens_kappa([True, False], [True])


def test_kappa_empty_raises() -> None:
    with pytest.raises(ValueError):
        cohens_kappa([], [])


# ---------------------------------------------------------------------------
# confusion / tpr_tnr
# ---------------------------------------------------------------------------


def test_confusion_known_values() -> None:
    human = [True, True, False, False, True]
    judge = [True, False, False, True, True]
    tp, fp, tn, fn = confusion(human, judge)
    assert (tp, fp, tn, fn) == (2, 1, 1, 1)


def test_tpr_tnr_known_values() -> None:
    human = [True, True, False, False, True]
    judge = [True, False, False, True, True]
    tpr, tnr = tpr_tnr(human, judge)
    assert tpr == pytest.approx(2 / 3)
    assert tnr == pytest.approx(1 / 2)


def test_tpr_undefined_when_no_positives() -> None:
    with pytest.raises(ValueError):
        tpr_tnr([False, False, False], [False, True, False])


def test_tnr_undefined_when_no_negatives() -> None:
    with pytest.raises(ValueError):
        tpr_tnr([True, True, True], [True, False, True])


# ---------------------------------------------------------------------------
# bias_correct
# ---------------------------------------------------------------------------


def test_bias_correct_perfect_judge_returns_p_observed_unchanged() -> None:
    # tpr = tnr = 1.0 -> denom = 1 -> theta_hat = p_obs + 1 - 1 = p_obs
    theta_hat = bias_correct(p_observed=0.37, tpr=1.0, tnr=1.0)
    assert theta_hat == pytest.approx(0.37)


def test_bias_correct_at_chance_raises() -> None:
    # tpr + tnr == 1 exactly -> undefined
    with pytest.raises(ValueError):
        bias_correct(p_observed=0.3, tpr=0.6, tnr=0.4)


def test_bias_correct_below_chance_raises() -> None:
    with pytest.raises(ValueError):
        bias_correct(p_observed=0.3, tpr=0.4, tnr=0.3)


def test_bias_correct_clamps_and_warns_above_one() -> None:
    with pytest.warns(UserWarning, match="clamping"):
        theta_hat = bias_correct(p_observed=0.95, tpr=0.6, tnr=0.6)
    assert theta_hat == 1.0


def test_bias_correct_clamps_and_warns_below_zero() -> None:
    with pytest.warns(UserWarning, match="clamping"):
        theta_hat = bias_correct(p_observed=0.01, tpr=0.55, tnr=0.55)
    assert theta_hat == 0.0


def test_bias_correct_known_value() -> None:
    # theta_hat = (p_obs + tnr - 1) / (tpr + tnr - 1)
    theta_hat = bias_correct(p_observed=0.4, tpr=0.8, tnr=0.9)
    expected = (0.4 + 0.9 - 1) / (0.8 + 0.9 - 1)
    assert theta_hat == pytest.approx(expected)


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------


def test_bootstrap_ci_perfect_judge_is_a_point_interval_at_p_observed() -> None:
    human = [True] * 20 + [False] * 20
    judge = human[:]  # perfect judge: tpr = tnr = 1.0 on every resample
    lo, hi = bootstrap_ci(human, judge, p_observed=0.42, n_resamples=200, random_state=0)
    assert lo == pytest.approx(0.42, abs=1e-9)
    assert hi == pytest.approx(0.42, abs=1e-9)


def test_bootstrap_ci_bounds_are_ordered_and_within_unit_interval() -> None:
    human = [True] * 15 + [False] * 15
    judge = [True] * 12 + [False] * 3 + [False] * 12 + [True] * 3
    with pytest.warns(UserWarning, match="clamping"):
        lo, hi = bootstrap_ci(human, judge, p_observed=0.35, n_resamples=500, random_state=1)
    assert 0.0 <= lo <= hi <= 1.0


def test_bootstrap_ci_reproducible_with_seed() -> None:
    human = [True] * 15 + [False] * 15
    judge = [True] * 11 + [False] * 4 + [False] * 13 + [True] * 2
    with pytest.warns(UserWarning, match="clamping"):
        result_a = bootstrap_ci(human, judge, p_observed=0.3, n_resamples=300, random_state=42)
    with pytest.warns(UserWarning, match="clamping"):
        result_b = bootstrap_ci(human, judge, p_observed=0.3, n_resamples=300, random_state=42)
    assert result_a == result_b


def test_bootstrap_ci_all_resamples_undefined_raises() -> None:
    # Judge always predicts True: tpr=1 always, tnr undefined whenever a
    # resample has any negative -> forcing every resample degenerate is hard,
    # so instead use a judge exactly at chance on a set with no variability
    # across resamples (single-item repeated set can't vary), guaranteeing
    # tpr+tnr<=1 every draw is awkward; use a tiny adversarial set instead:
    # a judge that always agrees with a coin-flip-cancelling pattern.
    human = [True, False]
    judge = [False, True]  # tp=0,fn=1 -> tpr=0 ; tn=0,fp=1 -> tnr=0
    with pytest.raises(ValueError):
        bootstrap_ci(human, judge, p_observed=0.5, n_resamples=50, random_state=0)


def test_bootstrap_ci_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([True, False], [True], p_observed=0.5)


def test_bootstrap_ci_invalid_alpha_raises() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([True, False], [True, False], p_observed=0.5, alpha=1.5)


# ---------------------------------------------------------------------------
# stratified_split
# ---------------------------------------------------------------------------


def test_stratified_split_proportions_per_stratum() -> None:
    records = [(f"a-{i}", "strat_a") for i in range(10)] + [
        (f"b-{i}", "strat_b") for i in range(10)
    ]
    train, dev, test = stratified_split(
        records, by=lambda r: r[1], ratios=(0.2, 0.4, 0.4), random_state=0
    )

    assert len(train) + len(dev) + len(test) == 20

    for split in (train, dev, test):
        strata_in_split = {r[1] for r in split}
        assert strata_in_split <= {"strat_a", "strat_b"}

    train_strata = Counter(r[1] for r in train)
    assert train_strata["strat_a"] == 2  # 20% of 10
    assert train_strata["strat_b"] == 2


def test_stratified_split_no_overlap_and_covers_all_records() -> None:
    records = list(range(30))
    train, dev, test = stratified_split(
        records, by=lambda r: r % 3, ratios=(0.2, 0.4, 0.4), random_state=7
    )
    all_out = train + dev + test
    assert sorted(all_out) == records
    assert len(set(train) & set(dev)) == 0
    assert len(set(dev) & set(test)) == 0
    assert len(set(train) & set(test)) == 0


def test_stratified_split_bad_ratios_raises() -> None:
    with pytest.raises(ValueError):
        stratified_split([1, 2, 3], by=lambda r: 0, ratios=(0.5, 0.5, 0.5))


def test_stratified_split_reproducible_with_seed() -> None:
    records = list(range(20))
    result_a = stratified_split(records, by=lambda r: r % 2, random_state=3)
    result_b = stratified_split(records, by=lambda r: r % 2, random_state=3)
    assert result_a == result_b
