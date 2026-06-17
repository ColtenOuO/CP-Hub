from backend.app.services.level import exp_progress, exp_to_next, level_from_exp

# ── exp_to_next ────────────────────────────────────────────────────────────


def test_exp_to_next_level_1():
    assert exp_to_next(1) == 100


def test_exp_to_next_level_2():
    assert exp_to_next(2) == 282


def test_exp_to_next_level_5():
    assert exp_to_next(5) == 1118


def test_exp_to_next_increases_with_level():
    for n in range(1, 20):
        assert exp_to_next(n) < exp_to_next(n + 1)


# ── level_from_exp ─────────────────────────────────────────────────────────


def test_level_1_at_zero_exp():
    assert level_from_exp(0) == 1


def test_level_1_just_before_threshold():
    assert level_from_exp(exp_to_next(1) - 1) == 1


def test_level_2_at_threshold():
    assert level_from_exp(exp_to_next(1)) == 2


def test_level_3_at_threshold():
    threshold = exp_to_next(1) + exp_to_next(2)
    assert level_from_exp(threshold) == 3


def test_level_from_exp_monotone():
    prev = level_from_exp(0)
    for exp in range(0, 20000, 50):
        current = level_from_exp(exp)
        assert current >= prev
        prev = current


def test_level_from_exp_large():
    assert level_from_exp(100_000) > 10


def test_level_from_exp_roundtrip():
    for level in range(1, 15):
        total = sum(exp_to_next(n) for n in range(1, level))
        assert level_from_exp(total) == level
        assert level_from_exp(total + exp_to_next(level) - 1) == level
        assert level_from_exp(total + exp_to_next(level)) == level + 1


# ── exp_progress ───────────────────────────────────────────────────────────


def test_exp_progress_at_zero():
    current, needed, level = exp_progress(0)
    assert level == 1
    assert current == 0
    assert needed == exp_to_next(1)


def test_exp_progress_mid_level():
    current, needed, level = exp_progress(50)
    assert level == 1
    assert current == 50
    assert needed == exp_to_next(1)


def test_exp_progress_at_level_boundary():
    threshold = exp_to_next(1)
    current, needed, level = exp_progress(threshold)
    assert level == 2
    assert current == 0
    assert needed == exp_to_next(2)


def test_exp_progress_current_plus_accumulated_equals_total():
    for total in [0, 50, 100, 500, 1000, 5000]:
        current, needed, level = exp_progress(total)
        accumulated = sum(exp_to_next(n) for n in range(1, level))
        assert accumulated + current == total
