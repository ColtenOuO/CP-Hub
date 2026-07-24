import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from backend.app.api.deps import LeetCodeServiceDep
from backend.app.schema.leetcode import (
    Difficulty,
    LeetCodeProblem,
    ProblemListResponse,
    ProblemSolvedResponse,
    RandomProblemsResponse,
    UserExistsResponse,
    UserSolvedStatsResponse,
)

router = APIRouter()

DifficultyQuery = Annotated[Difficulty, Query(description="Difficulty filter; case insensitive")]
TagsQuery = Annotated[list[str] | None, Query(description="Topic slugs such as `array` or `dynamic-programming`; repeat for multiple tags")]
UsernamePath = Annotated[str, Path(description="LeetCode username")]


def _to_http_error(exc: Exception) -> HTTPException:
    """Maps LeetCodeService failures to HTTP errors: rejected filters are 404, upstream/transport failures are 502."""
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/problems", response_model=ProblemListResponse, summary="List free problems")
async def list_problems(
    service: LeetCodeServiceDep,
    difficulty: DifficultyQuery,
    tags: TagsQuery = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 50,
    skip: Annotated[int, Query(ge=0, description="Number of problems to skip")] = 0,
) -> ProblemListResponse:
    """Returns one page of free problems matching the filters. Premium problems are dropped, so `count` may be below `limit`."""
    tags = tags or []

    try:
        total, questions = await asyncio.gather(
            service.get_problem_total(tags=tags, difficulty=difficulty.value),
            service.get_problem_list(tags=tags, difficulty=difficulty.value, limit=limit, skip=skip),
        )
    except (ValueError, RuntimeError) as exc:
        raise _to_http_error(exc) from exc

    problems = [LeetCodeProblem.model_validate(q) for q in questions]
    return ProblemListResponse(
        difficulty=difficulty,
        tags=tags,
        skip=skip,
        limit=limit,
        total=total,
        count=len(problems),
        problems=problems,
    )


@router.get("/problems/random", response_model=RandomProblemsResponse, summary="Draw random problems")
async def draw_random_problems(
    service: LeetCodeServiceDep,
    difficulty: DifficultyQuery,
    tags: TagsQuery = None,
    count: Annotated[int, Query(ge=1, le=10, description="How many distinct problems to draw")] = 1,
) -> RandomProblemsResponse:
    """Draws `count` distinct free problems at random. Returns 404 when the filters match too few free problems."""
    tags = tags or []

    try:
        drawn = await service.draw_random_problems(difficulty=difficulty.value, count=count, tags=tags)
    except (ValueError, RuntimeError) as exc:
        raise _to_http_error(exc) from exc

    problems = [LeetCodeProblem.model_validate(p) for p in drawn]
    return RandomProblemsResponse(difficulty=difficulty, tags=tags, count=len(problems), problems=problems)


@router.get("/users/{username}", response_model=UserExistsResponse, summary="Check whether a user exists")
async def check_user(service: LeetCodeServiceDep, username: UsernamePath) -> UserExistsResponse:
    """Reports whether the LeetCode account exists. Used before linking an account, so a missing user is 200 with `exists: false`."""
    try:
        exists = await service.user_exists(username)
    except (ValueError, RuntimeError) as exc:
        raise _to_http_error(exc) from exc

    return UserExistsResponse(username=username, exists=exists)


@router.get("/users/{username}/stats", response_model=UserSolvedStatsResponse, summary="Get solved counts per difficulty")
async def get_user_stats(service: LeetCodeServiceDep, username: UsernamePath) -> UserSolvedStatsResponse:
    """Returns the user's accepted-problem counts per difficulty."""
    try:
        stats = await service.get_solved_stats(username)
    except (ValueError, RuntimeError) as exc:
        raise _to_http_error(exc) from exc

    if stats is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"LeetCode user not found: {username}")

    return UserSolvedStatsResponse(username=username, **stats)


@router.get("/users/{username}/solved/{title_slug}", response_model=ProblemSolvedResponse, summary="Verify a problem was solved")
async def verify_problem_solved(
    service: LeetCodeServiceDep,
    username: UsernamePath,
    title_slug: Annotated[str, Path(description="Problem slug, e.g. `two-sum`")],
    after: Annotated[datetime, Query(description="Only accept submissions at or after this time; naive values are read as UTC")],
) -> ProblemSolvedResponse:
    """Checks the user's 20 most recent accepted submissions, so submissions older than that window are reported as unsolved."""
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)

    try:
        solved = await service.verify_problem_solved(username, title_slug, after)
    except (ValueError, RuntimeError) as exc:
        raise _to_http_error(exc) from exc

    return ProblemSolvedResponse(username=username, title_slug=title_slug, after=after, solved=solved)
