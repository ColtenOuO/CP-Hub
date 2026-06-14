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
