import pytest

from backend.app.services.stage.graph import CyclicDependencyError, StageGraph


def make_stage(id: int, name: str, requires: list[int], problems: int = 2) -> dict:
    return {
        "id": id,
        "name": name,
        "requires": requires,
        "problems": [
            {"url": f"https://leetcode.com/problems/p{i}/", "title": f"P{i}", "platform": "leetcode", "rewards": {"exp": 50, "coins": 25}}
            for i in range(problems)
        ],
        "rewards": {"exp": 200, "coins": 100},
    }


# --- StageGraph construction ---


def test_valid_dag_loads():
    stages = [
        make_stage(1, "A", []),
        make_stage(2, "B", [1]),
        make_stage(3, "C", [1]),
        make_stage(4, "D", [2, 3]),
    ]
    graph = StageGraph(stages)
    assert len(graph.stages) == 4


def test_single_stage_no_requires():
    graph = StageGraph([make_stage(1, "A", [])])
    assert 1 in graph.stages


def test_unknown_required_stage_raises():
    stages = [make_stage(1, "A", [99])]
    with pytest.raises(ValueError, match="unknown stage"):
        StageGraph(stages)


# --- Cycle detection ---


def test_direct_cycle_raises():
    stages = [
        make_stage(1, "A", [2]),
        make_stage(2, "B", [1]),
    ]
    with pytest.raises(CyclicDependencyError):
        StageGraph(stages)


def test_self_loop_raises():
    stages = [make_stage(1, "A", [1])]
    with pytest.raises(CyclicDependencyError):
        StageGraph(stages)


def test_three_node_cycle_raises():
    stages = [
        make_stage(1, "A", [3]),
        make_stage(2, "B", [1]),
        make_stage(3, "C", [2]),
    ]
    with pytest.raises(CyclicDependencyError):
        StageGraph(stages)


def test_diamond_dag_no_cycle():
    stages = [
        make_stage(1, "A", []),
        make_stage(2, "B", [1]),
        make_stage(3, "C", [1]),
        make_stage(4, "D", [2, 3]),
    ]
    StageGraph(stages)  # should not raise


# --- is_unlocked ---


def test_is_unlocked_no_requires():
    graph = StageGraph([make_stage(1, "A", [])])
    assert graph.is_unlocked(1, set()) is True


def test_is_unlocked_requires_met():
    stages = [make_stage(1, "A", []), make_stage(2, "B", [1])]
    graph = StageGraph(stages)
    assert graph.is_unlocked(2, {1}) is True


def test_is_unlocked_requires_not_met():
    stages = [make_stage(1, "A", []), make_stage(2, "B", [1])]
    graph = StageGraph(stages)
    assert graph.is_unlocked(2, set()) is False


def test_is_unlocked_multiple_requires_partial():
    stages = [
        make_stage(1, "A", []),
        make_stage(2, "B", []),
        make_stage(3, "C", [1, 2]),
    ]
    graph = StageGraph(stages)
    assert graph.is_unlocked(3, {1}) is False
    assert graph.is_unlocked(3, {1, 2}) is True


# --- available_to_enroll ---


def test_available_excludes_enrolled():
    stages = [make_stage(1, "A", []), make_stage(2, "B", [])]
    graph = StageGraph(stages)
    available = graph.available_to_enroll(completed_ids=set(), enrolled_ids={1})
    ids = [s["id"] for s in available]
    assert 1 not in ids
    assert 2 in ids


def test_available_excludes_locked():
    stages = [make_stage(1, "A", []), make_stage(2, "B", [1])]
    graph = StageGraph(stages)
    available = graph.available_to_enroll(completed_ids=set(), enrolled_ids=set())
    ids = [s["id"] for s in available]
    assert 1 in ids
    assert 2 not in ids


def test_available_unlocks_after_completion():
    stages = [make_stage(1, "A", []), make_stage(2, "B", [1])]
    graph = StageGraph(stages)
    available = graph.available_to_enroll(completed_ids={1}, enrolled_ids={1})
    ids = [s["id"] for s in available]
    assert 2 in ids
    assert 1 not in ids


def test_available_empty_when_all_enrolled():
    stages = [make_stage(1, "A", []), make_stage(2, "B", [1])]
    graph = StageGraph(stages)
    available = graph.available_to_enroll(completed_ids={1}, enrolled_ids={1, 2})
    assert available == []


# --- get_stage ---


def test_get_stage_returns_correct():
    stages = [make_stage(1, "First", []), make_stage(2, "Second", [1])]
    graph = StageGraph(stages)
    assert graph.get_stage(1)["name"] == "First"
    assert graph.get_stage(2)["name"] == "Second"


def test_all_stages_returns_all():
    stages = [make_stage(i, f"Stage {i}", []) for i in range(1, 6)]
    graph = StageGraph(stages)
    assert len(graph.all_stages()) == 5
