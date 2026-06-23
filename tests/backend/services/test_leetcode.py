from unittest.mock import AsyncMock

import pytest

from backend.app.services.leetcode.client import LeetCodeService


@pytest.fixture
def leetcode_service():
    return LeetCodeService()


@pytest.mark.asyncio
async def test_get_problem_list_success(leetcode_service):
    tags = ["array"]
    difficulty = "EASY"

    questions = await leetcode_service.get_problem_list(tags=tags, difficulty=difficulty)

    assert isinstance(questions, list)
    assert len(questions) > 0

    for question in questions:
        assert "questionFrontendId" in question
        assert "title" in question
        assert "titleSlug" in question
        assert "isPaidOnly" in question
        assert question["isPaidOnly"] is False


@pytest.mark.asyncio
async def test_draw_random_problem_success(leetcode_service):
    tags = ["dynamic-programming"]
    difficulty = "MEDIUM"

    problem = await leetcode_service.draw_random_problem(tags=tags, difficulty=difficulty)

    assert isinstance(problem, dict)
    assert "url" in problem
    assert problem["url"].startswith("https://leetcode.com/problems/")


@pytest.mark.asyncio
async def test_draw_random_problem_invalid_tag(leetcode_service):
    invalid_tags = ["this-is-not-a-real-leetcode-tag-12345"]
    difficulty = "EASY"

    with pytest.raises(ValueError):
        await leetcode_service.draw_random_problem(tags=invalid_tags, difficulty=difficulty)


@pytest.mark.asyncio
async def test_user_exists_for_real_user(leetcode_service):
    assert await leetcode_service.user_exists("neal_wu") is True


@pytest.mark.asyncio
async def test_user_exists_for_nonexistent_user(leetcode_service):
    assert await leetcode_service.user_exists("this-user-definitely-does-not-exist-12345") is False


@pytest.mark.asyncio
async def test_get_solved_stats_for_real_user(leetcode_service):
    stats = await leetcode_service.get_solved_stats("neal_wu")

    assert stats is not None
    assert stats.keys() == {"easy", "medium", "hard"}
    assert all(count >= 0 for count in stats.values())


@pytest.mark.asyncio
async def test_get_solved_stats_for_nonexistent_user(leetcode_service):
    stats = await leetcode_service.get_solved_stats("this-user-definitely-does-not-exist-12345")

    assert stats is None


@pytest.mark.asyncio
async def test_draw_random_problems_not_enough_free_problems(leetcode_service, monkeypatch):
    leetcode_service.get_problem_total = AsyncMock(return_value=10)

    leetcode_service.get_problem_list = AsyncMock(
        return_value=[
            {
                "questionFrontendId": "1",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "isPaidOnly": False,
            }
        ]
    )

    with pytest.raises(ValueError) as exc:
        await leetcode_service.draw_random_problems(
            tags=["array"],
            difficulty="EASY",
            count=2,
            choosing_window_size=5,
            max_attempts=1,
        )

    assert "Only found 1 free problems" in str(exc.value)
