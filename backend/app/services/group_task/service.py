import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crud import group_task as group_task_crud
from backend.app.crud.stage import award_rewards
from backend.app.models.group_task import GroupTask
from backend.app.models.group_task_problem import GroupTaskProblem
from backend.app.models.user import User
from backend.app.services.leetcode.client import LeetCodeService

DIFFICULTY_REWARDS = {
    "easy": {"exp": 30, "coins": 10},
    "medium": {"exp": 55, "coins": 30},
    "hard": {"exp": 150, "coins": 100},
}


class ActiveTaskExistsError(Exception):
    """Raised when trying to create a group task while one is already active."""


class NoActiveTaskError(Exception):
    """Raised when trying to delete a group task but none is active."""


def _slug_from_url(url: str) -> str:
    if "/problems/" in url:
        return url.split("/problems/")[1].split("/")[0]
    return url.rstrip("/").rsplit("/", 1)[-1]


@dataclass
class VerifiedProblem:
    problem: GroupTaskProblem
    exp: int
    coins: int


@dataclass
class FailedProblem:
    code: str
    reason: str


@dataclass
class VerifyBatchResult:
    succeeded: list[VerifiedProblem] = field(default_factory=list)
    failed: list[FailedProblem] = field(default_factory=list)
    task_completed: bool = False


@dataclass
class RecapEntry:
    user: User
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


@dataclass
class RecapData:
    status: str
    total_problems: int
    completed_problems: int
    entries: list[RecapEntry]
    bonus_exp: int
    bonus_coins: int


class GroupTaskService:
    def __init__(self, leetcode_service: LeetCodeService):
        self._leetcode = leetcode_service

    async def create_task(
        self,
        session: AsyncSession,
        *,
        deadline: datetime,
        reward_exp: int,
        reward_coins: int,
        created_by: int,
        channel_id: int,
    ) -> GroupTask:
        if await group_task_crud.get_active_task(session) is not None:
            raise ActiveTaskExistsError()

        problems: list[dict] = []
        for difficulty, prefix in (("EASY", "E"), ("MEDIUM", "M"), ("HARD", "H")):
            drawn = await self._leetcode.draw_random_problems(difficulty=difficulty, count=10, choosing_window_size=100, take_per_window=1)
            for index, question in enumerate(drawn, start=1):
                problems.append(
                    {
                        "code": f"{prefix}{index}",
                        "difficulty": difficulty.lower(),
                        "title": question["title"],
                        "url": question["url"],
                        "title_slug": question["titleSlug"],
                    }
                )

        return await group_task_crud.create_task(
            session,
            deadline=deadline,
            reward_exp=reward_exp,
            reward_coins=reward_coins,
            created_by=created_by,
            channel_id=channel_id,
            problems=problems,
        )

    async def delete_active_task(self, session: AsyncSession) -> None:
        task = await group_task_crud.get_active_task(session)
        if task is None:
            raise NoActiveTaskError()
        await group_task_crud.delete_task(session, task.id)

    async def claim(self, session: AsyncSession, task: GroupTask, user: User, codes: list[str]) -> dict[str, str]:
        if user.leetcode_id is None:
            return {code: "請先用 /link leetcode 連結帳號才能認領題目" for code in codes}

        problems = {p.code: p for p in await group_task_crud.get_problems_by_codes(session, task.id, codes)}
        results: dict[str, str] = {}
        for code in codes:
            problem = problems.get(code)
            if problem is None:
                results[code] = "找不到此題"
            elif problem.is_completed:
                results[code] = "此題已完成"
            elif problem.claimed_by == user.id:
                results[code] = "你已認領此題"
            elif problem.claimed_by is not None:
                results[code] = "已被他人認領"
            else:
                claimed = await group_task_crud.mark_claimed(session, problem.id, user.id)
                results[code] = "認領成功" if claimed else "已被他人搶先認領"
        return results

    async def unclaim(self, session: AsyncSession, task: GroupTask, user: User, codes: list[str]) -> dict[str, str]:
        problems = {p.code: p for p in await group_task_crud.get_problems_by_codes(session, task.id, codes)}
        results: dict[str, str] = {}
        for code in codes:
            problem = problems.get(code)
            if problem is None:
                results[code] = "找不到此題"
            elif problem.is_completed:
                results[code] = "此題已完成，無法取消認領"
            elif problem.claimed_by != user.id:
                results[code] = "你沒有認領此題"
            else:
                unclaimed = await group_task_crud.mark_unclaimed(session, problem.id, user.id)
                results[code] = "取消認領成功" if unclaimed else "取消認領失敗，請重新查詢狀態"
        return results

    async def get_verifiable_problems(self, session: AsyncSession, task: GroupTask, user: User) -> list[GroupTaskProblem]:
        return await group_task_crud.get_claimed_incomplete_by_user(session, task.id, user.id)

    async def verify(self, session: AsyncSession, task: GroupTask, user: User, codes: list[str]) -> VerifyBatchResult:
        result = VerifyBatchResult()

        if user.leetcode_id is None:
            result.failed = [FailedProblem(code=code, reason="尚未連結 LeetCode 帳號") for code in codes]
            return result

        problems = {p.code: p for p in await group_task_crud.get_problems_by_codes(session, task.id, codes)}

        for code in codes:
            problem = problems.get(code)
            if problem is None:
                result.failed.append(FailedProblem(code=code, reason="找不到此題"))
                continue
            if problem.is_completed:
                result.failed.append(FailedProblem(code=code, reason="已完成過"))
                continue
            if problem.claimed_by != user.id:
                result.failed.append(FailedProblem(code=code, reason="你沒有認領此題"))
                continue

            slug = _slug_from_url(problem.url)
            solved = await self._leetcode.verify_problem_solved(user.leetcode_id, slug, problem.claimed_at)
            if not solved:
                result.failed.append(FailedProblem(code=code, reason="尚未偵測到 AC 提交"))
                continue

            completed = await group_task_crud.mark_completed(session, problem.id, user.id)
            if not completed:
                result.failed.append(FailedProblem(code=code, reason="題目狀態已改變，請重新查詢後再試"))
                continue

            rewards = DIFFICULTY_REWARDS[problem.difficulty]
            await award_rewards(session, user.stats, rewards["exp"], rewards["coins"])
            result.succeeded.append(VerifiedProblem(problem=problem, exp=rewards["exp"], coins=rewards["coins"]))

        refreshed_task = await group_task_crud.get_task_with_problems(session, task.id)
        result.task_completed = refreshed_task is not None and all(p.is_completed for p in refreshed_task.problems)
        return result

    async def finalize(self, session: AsyncSession, task_id: uuid.UUID, status: Literal["completed", "expired"]) -> RecapData | None:
        task = await group_task_crud.finalize_task(session, task_id, status)
        if task is None:
            return None

        contributions: dict[uuid.UUID, RecapEntry] = {}
        completed_count = 0
        for problem in task.problems:
            if not problem.is_completed:
                continue
            completed_count += 1
            contributor = problem.completed_by_user
            entry = contributions.setdefault(contributor.id, RecapEntry(user=contributor, counts={"easy": 0, "medium": 0, "hard": 0}))
            entry.counts[problem.difficulty] += 1

        bonus_exp = 0
        bonus_coins = 0
        if status == "completed":
            bonus_exp = task.reward_exp
            bonus_coins = task.reward_coins
            for entry in contributions.values():
                await award_rewards(session, entry.user.stats, bonus_exp, bonus_coins)

        return RecapData(
            status=status,
            total_problems=len(task.problems),
            completed_problems=completed_count,
            entries=sorted(contributions.values(), key=lambda e: e.total, reverse=True),
            bonus_exp=bonus_exp,
            bonus_coins=bonus_coins,
        )
