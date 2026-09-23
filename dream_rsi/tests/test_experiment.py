from dream_rsi.research.experiment import (
    TrialResult, paired_differences, paired_permutation_pvalue,
    paired_bootstrap_ci, summarize, compare,
)


def test_statistics_are_paired_by_seed():
    rows = [
        TrialResult("a", 1, 2.0, 2.0, "a", 1, 0.1),
        TrialResult("b", 1, 1.0, 1.0, "b", 1, 0.1),
        TrialResult("a", 2, 4.0, 4.0, "a", 1, 0.1),
        TrialResult("b", 2, 3.0, 3.0, "b", 1, 0.1),
    ]
    assert paired_differences(rows, "a", "b") == [1.0, 1.0]
    assert paired_permutation_pvalue([1.0, 1.0]) == 0.5
    lo, hi = paired_bootstrap_ci([1.0, 1.0], samples=100)
    assert lo == hi == 1.0


def test_summary_and_comparison():
    rows = [
        TrialResult("a", 1, 2.0, 2.0, "a", 1, 0.1),
        TrialResult("a", 2, 4.0, 4.0, "a", 1, 0.1),
        TrialResult("b", 1, 1.0, 1.0, "b", 1, 0.1),
        TrialResult("b", 2, 3.0, 3.0, "b", 1, 0.1),
    ]
    assert {x.method for x in summarize(rows)} == {"a", "b"}
    result = compare(rows, "a", "b")
    assert result["mean_difference_a_minus_b"] == 1.0
    assert result["positive_difference_rate"] == 1.0
