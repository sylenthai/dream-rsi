from dream_rsi.research.tasks import default_task_suite, get_split
from dream_rsi.research.experiment import run_trials, summarize, paired_differences


def test_task_suite_has_held_out_split():
    suite = default_task_suite()
    assert suite.train and suite.validation and suite.test
    assert not ({t.task_id for t in suite.train} & {t.task_id for t in suite.test})
    assert len(get_split(suite, "held-out")) == len(suite.validation) + len(suite.test)


def test_trials_are_paired_by_task_and_seed():
    results = run_trials(["static", "random"], [0, 1], iterations=1, workers=2, rounds=2,
                         split="test", tasks=default_task_suite().test[:1])
    assert len(results) == 4
    assert len(paired_differences(results, "static", "random")) == 2
    assert all(r.task_id == "test-0" for r in results)


def test_summary_contains_split_and_fresh_metric():
    results = run_trials(["static"], [0], iterations=1, workers=2, rounds=2,
                         split="validation", tasks=default_task_suite().validation[:1])
    summary = summarize(results)
    assert summary[0].split == "validation"
    assert summary[0].n == 1
