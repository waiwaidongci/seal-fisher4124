import pytest
from src.services import leak_algorithm as algo


def test_reading_equal_to_cutoff_is_leak():
    # 读数达到分界算漏封：等于分界也判漏封
    assert algo.instrument_judges_leak(5.0, 5.0) is True
    assert algo.instrument_judges_leak(4.99, 5.0) is False


def test_choose_cutoff_min_misjudgements_then_smallest():
    # 读数 >= 分界 判漏封；复判标签为真值
    specimens = [
        {'reading': 1.0, 'rejudgement': 'sealed'},
        {'reading': 2.0, 'rejudgement': 'sealed'},
        {'reading': 3.0, 'rejudgement': 'leak'},
        {'reading': 4.0, 'rejudgement': 'leak'},
    ]
    cutoff, n, table = algo.choose_cutoff(specimens)
    # 分界 3.0：1,2 合格、3,4 漏封，零误判
    assert cutoff == 3.0
    assert n == 0
    assert {c['cutoff'] for c in table} == {1.0, 2.0, 3.0, 4.0}


def test_tie_chooses_smaller_cutoff():
    # 严格构造同分：候选 2.0 与 4.0 的误判数均为 1，必须取较小分界 2.0
    # 误判序列（候选 1/2/3/4）：2, 1, 2, 1
    specimens = [
        {'reading': 1.0, 'rejudgement': 'sealed'},
        {'reading': 2.0, 'rejudgement': 'leak'},
        {'reading': 3.0, 'rejudgement': 'sealed'},
        {'reading': 4.0, 'rejudgement': 'leak'},
    ]
    cutoff, n, table = algo.choose_cutoff(specimens)
    counts = {c['cutoff']: c['misjudgements'] for c in table}
    assert counts == {1.0: 2, 2.0: 1, 3.0: 2, 4.0: 1}
    assert n == 1
    assert cutoff == 2.0


def test_tie_chooses_smaller_cutoff_mixed():
    # 构造同分场景：两候选误判数相等，必须取小
    specimens = [
        {'reading': 1.0, 'rejudgement': 'leak'},
        {'reading': 2.0, 'rejudgement': 'sealed'},
        {'reading': 3.0, 'rejudgement': 'leak'},
    ]
    cutoff, n, table = algo.choose_cutoff(specimens)
    counts = {c['cutoff']: c['misjudgements'] for c in table}
    best = min(counts.values())
    assert cutoff == min(c for c, v in counts.items() if v == best)
    assert n == best


def test_cutoff_only_from_observed_readings():
    specimens = [
        {'reading': 1.5, 'rejudgement': 'sealed'},
        {'reading': 9.5, 'rejudgement': 'leak'},
    ]
    cutoff, _, table = algo.choose_cutoff(specimens)
    assert cutoff in (1.5, 9.5)
    assert sorted(c['cutoff'] for c in table) == [1.5, 9.5]


def test_empty_and_incomplete_rejected():
    with pytest.raises(ValueError):
        algo.choose_cutoff([])
    with pytest.raises(ValueError):
        algo.choose_cutoff([{'reading': 1.0, 'rejudgement': None}])
    with pytest.raises(ValueError):
        algo.blind_review([], 2.0)


def test_blind_review_counts_misjudgements():
    specimens = [
        {'specimen_key': 's1', 'reading': 1.0, 'rejudgement': 'sealed'},
        {'specimen_key': 's2', 'reading': 5.0, 'rejudgement': 'sealed'},  # 仪器判漏封，实际合格 -> 误判
        {'specimen_key': 's3', 'reading': 6.0, 'rejudgement': 'leak'},
    ]
    total, details = algo.blind_review(specimens, 5.0)
    assert total == 1
    assert [d['instrument'] for d in details] == ['sealed', 'leak', 'leak']
    assert details[1]['misjudged'] is True
