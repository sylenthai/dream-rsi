from dream_rsi.core.tree import DiscoveryTree, TreeView
from dream_rsi.core.world import ReplayWorld
from dream_rsi.policies.heuristic import ConservativePolicy


def make_tree():
    t = DiscoveryTree()
    a = t.add_child("root", 0.5)
    t.add_child(a.id, 0.7)
    t.add_child("root", 0.6)
    return t


def test_tree_eligibility():
    t = make_tree()
    assert "root" in t.eligible()
    assert len(t.nodes) == 4


def test_replay_never_reveals_unselected_siblings():
    t = make_tree()
    r = ReplayWorld("w", t).run(ConservativePolicy(0.35), 1, 1)
    assert set(r.revealed) == {"root", "n1"}


def test_replay_score_has_cost():
    t = make_tree()
    r = ReplayWorld("w", t).run(ConservativePolicy(0.7), 2, 3)
    assert r.metrics.work >= 1
    assert r.metrics.reward <= r.metrics.quality + 0.02 * r.metrics.parallelism_bonus
