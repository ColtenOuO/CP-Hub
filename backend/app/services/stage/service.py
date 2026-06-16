from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crud import stage as stage_crud
from backend.app.models.user import User
from backend.app.models.user_stage_progress import UserStageProgress
from backend.app.services.leetcode.client import LeetCodeService
from backend.app.services.stage.graph import StageGraph


class StageNotFoundError(ValueError):
    pass


class AlreadyEnrolledError(ValueError):
    pass


class DependencyNotMetError(ValueError):
    pass


class NotEnrolledError(ValueError):
    pass


class NoLeetCodeAccountError(ValueError):
    pass


@dataclass
class VerifyResult:
    solved: bool
    problem_rewards: dict
    stage_complete: bool
    stage_rewards: dict | None


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


class StageService:
    def __init__(self, graph: StageGraph, leetcode_service: LeetCodeService):
        self.graph = graph
        self.leetcode = leetcode_service

    async def enroll(self, session: AsyncSession, user: User, stage_id: int) -> UserStageProgress:
        if stage_id not in self.graph.stages:
            raise StageNotFoundError(f"Stage {stage_id} does not exist")

        existing = await stage_crud.get_progress(session, user.id, stage_id)
        if existing is not None:
            raise AlreadyEnrolledError(f"Already enrolled in stage {stage_id}")

        all_progress = await stage_crud.get_all_progress(session, user.id)
        completed_ids = {p.stage_id for p in all_progress if p.is_completed}

        if not self.graph.is_unlocked(stage_id, completed_ids):
            requires = self.graph.get_stage(stage_id).get("requires", [])
            missing = [self.graph.get_stage(r)["name"] for r in requires if r not in completed_ids]
            raise DependencyNotMetError(f"Must complete first: {', '.join(missing)}")

        return await stage_crud.create_progress(session, user.id, stage_id)

    async def get_current_problem(self, session: AsyncSession, user: User, stage_id: int) -> dict:
        progress = await stage_crud.get_progress(session, user.id, stage_id)
        if progress is None:
            raise NotEnrolledError(f"Not enrolled in stage {stage_id}")

        stage = self.graph.get_stage(stage_id)
        return {
            "problem": stage["problems"][progress.current_problem_index],
            "index": progress.current_problem_index,
            "total": len(stage["problems"]),
            "assigned_at": progress.assigned_at,
            "is_completed": progress.is_completed,
        }

    async def get_all_status(self, session: AsyncSession, user: User) -> list[dict]:
        all_progress = await stage_crud.get_all_progress(session, user.id)
        result = []
        for p in all_progress:
            stage = self.graph.get_stage(p.stage_id)
            total = len(stage["problems"])
            done = total if p.is_completed else p.current_problem_index
            result.append(
                {
                    "stage_id": p.stage_id,
                    "name": stage["name"],
                    "done": done,
                    "total": total,
                    "is_completed": p.is_completed,
                    "completed_at": p.completed_at,
                }
            )
        return result

    async def get_achievements(self, session: AsyncSession, user: User) -> list[dict]:
        all_progress = await stage_crud.get_all_progress(session, user.id)
        result = []
        for p in all_progress:
            if not p.is_completed:
                continue
            stage = self.graph.get_stage(p.stage_id)
            result.append(
                {
                    "name": stage["name"],
                    "started_at": p.assigned_at,
                    "completed_at": p.completed_at,
                }
            )
        return result

    async def get_list(self, session: AsyncSession, user: User) -> list[dict]:
        all_progress = await stage_crud.get_all_progress(session, user.id)
        completed_ids = {p.stage_id for p in all_progress if p.is_completed}
        enrolled_ids = {p.stage_id for p in all_progress}

        result = []
        for stage in self.graph.all_stages():
            progress = next((p for p in all_progress if p.stage_id == stage["id"]), None)
            unlocked = self.graph.is_unlocked(stage["id"], completed_ids)
            result.append(
                {
                    "stage": stage,
                    "unlocked": unlocked,
                    "enrolled": stage["id"] in enrolled_ids,
                    "completed": stage["id"] in completed_ids,
                    "progress": progress,
                }
            )
        return result

    async def verify_and_advance(self, session: AsyncSession, user: User, stage_id: int) -> VerifyResult:
        if not user.leetcode_id:
            raise NoLeetCodeAccountError("請先用 /account link 綁定 LeetCode 帳號")

        progress = await stage_crud.get_progress(session, user.id, stage_id)
        if progress is None:
            raise NotEnrolledError(f"Not enrolled in stage {stage_id}")

        stage = self.graph.get_stage(stage_id)
        problem = stage["problems"][progress.current_problem_index]
        slug = _slug_from_url(problem["url"])

        solved = await self.leetcode.verify_problem_solved(
            username=user.leetcode_id,
            title_slug=slug,
            after=progress.assigned_at,
        )

        if not solved:
            return VerifyResult(solved=False, problem_rewards={}, stage_complete=False, stage_rewards=None)

        problem_rewards = problem["rewards"]
        await stage_crud.award_rewards(session, user.stats, problem_rewards["exp"], problem_rewards["coins"])

        next_index = progress.current_problem_index + 1
        stage_complete = next_index >= len(stage["problems"])

        if stage_complete:
            await stage_crud.complete_stage(session, progress)
            stage_rewards = stage["rewards"]
            await stage_crud.award_rewards(session, user.stats, stage_rewards["exp"], stage_rewards["coins"])
        else:
            await stage_crud.advance_problem(session, progress, next_index)
            stage_rewards = None

        return VerifyResult(
            solved=True,
            problem_rewards=problem_rewards,
            stage_complete=stage_complete,
            stage_rewards=stage_rewards,
        )

    def available_stages(self, completed_ids: set[int], enrolled_ids: set[int]) -> list[dict]:
        return self.graph.available_to_enroll(completed_ids, enrolled_ids)
