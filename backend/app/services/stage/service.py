from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crud import stage as stage_crud
from backend.app.crud import stage_def as stage_def_crud
from backend.app.models.stage import Stage
from backend.app.models.user import User
from backend.app.models.user_stage_progress import UserStageProgress
from backend.app.services.stage.graph import StageGraph
from backend.app.services.stage.verifiers.base import PlatformVerifier


class AlreadyEnrolledError(ValueError):
    pass


class DependencyNotMetError(ValueError):
    pass


class NotEnrolledError(ValueError):
    pass


class NoPlatformAccountError(ValueError):
    _labels = {"leetcode": "LeetCode", "codeforces": "Codeforces", "atcoder": "AtCoder"}

    def __init__(self, platform: str):
        label = self._labels.get(platform, platform)
        super().__init__(f"請先用 /account link 綁定 {label} 帳號")


@dataclass
class VerifyResult:
    solved: bool
    problem_rewards: dict
    stage_complete: bool
    stage_rewards: dict | None


def stage_to_dict(stage: Stage) -> dict:
    return {
        "id": stage.id,
        "name": stage.name,
        "requires": stage.requires,
        "problems": stage.problems,
        "rewards": {"exp": stage.rewards_exp, "coins": stage.rewards_coins},
    }


class StageService:
    def __init__(self, verifiers: dict[str, PlatformVerifier]):
        self._verifiers = verifiers

    def _get_handle(self, user: User, platform: str) -> str | None:
        return {
            "leetcode": user.leetcode_id,
            "codeforces": user.codeforces_id,
            "atcoder": user.atcoder_id,
        }.get(platform)

    async def _load_graph(self, session: AsyncSession) -> StageGraph:
        stages = await stage_def_crud.get_all_stages(session)
        return StageGraph([stage_to_dict(s) for s in stages])

    async def get_stage(self, session: AsyncSession, stage_id: int) -> dict | None:
        stage = await stage_def_crud.get_stage(session, stage_id)
        return stage_to_dict(stage) if stage else None

    async def get_all_stages(self, session: AsyncSession) -> list[dict]:
        stages = await stage_def_crud.get_all_stages(session)
        return [stage_to_dict(s) for s in stages]

    async def enroll(self, session: AsyncSession, user: User, stage_id: int) -> UserStageProgress:
        graph = await self._load_graph(session)

        if stage_id not in graph.stages:
            raise stage_def_crud.StageNotFoundError(f"Stage {stage_id} does not exist")

        existing = await stage_crud.get_progress(session, user.id, stage_id)
        if existing is not None:
            raise AlreadyEnrolledError(f"Already enrolled in stage {stage_id}")

        all_progress = await stage_crud.get_all_progress(session, user.id)
        completed_ids = {p.stage_id for p in all_progress if p.is_completed}

        if not graph.is_unlocked(stage_id, completed_ids):
            requires = graph.get_stage(stage_id).get("requires", [])
            missing = [graph.get_stage(r)["name"] for r in requires if r not in completed_ids]
            raise DependencyNotMetError(f"Must complete first: {', '.join(missing)}")

        return await stage_crud.create_progress(session, user.id, stage_id)

    async def get_current_problem(self, session: AsyncSession, user: User, stage_id: int) -> dict:
        progress = await stage_crud.get_progress(session, user.id, stage_id)
        if progress is None:
            raise NotEnrolledError(f"Not enrolled in stage {stage_id}")

        stage = await stage_def_crud.get_stage(session, stage_id)
        return {
            "problem": stage.problems[progress.current_problem_index],
            "index": progress.current_problem_index,
            "total": len(stage.problems),
            "assigned_at": progress.assigned_at,
            "is_completed": progress.is_completed,
        }

    async def get_all_status(self, session: AsyncSession, user: User) -> list[dict]:
        all_progress = await stage_crud.get_all_progress(session, user.id)
        result = []
        for p in all_progress:
            stage = await stage_def_crud.get_stage(session, p.stage_id)
            if stage is None:
                continue
            total = len(stage.problems)
            done = total if p.is_completed else p.current_problem_index
            result.append(
                {
                    "stage_id": p.stage_id,
                    "name": stage.name,
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
            stage = await stage_def_crud.get_stage(session, p.stage_id)
            if stage is None:
                continue
            result.append(
                {
                    "name": stage.name,
                    "started_at": p.assigned_at,
                    "completed_at": p.completed_at,
                }
            )
        return result

    async def get_list(self, session: AsyncSession, user: User) -> list[dict]:
        graph = await self._load_graph(session)
        all_progress = await stage_crud.get_all_progress(session, user.id)
        completed_ids = {p.stage_id for p in all_progress if p.is_completed}
        enrolled_ids = {p.stage_id for p in all_progress}

        result = []
        for stage in graph.all_stages():
            progress = next((p for p in all_progress if p.stage_id == stage["id"]), None)
            unlocked = graph.is_unlocked(stage["id"], completed_ids)
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

    async def available_stages(self, session: AsyncSession, completed_ids: set[int], enrolled_ids: set[int]) -> list[dict]:
        graph = await self._load_graph(session)
        return graph.available_to_enroll(completed_ids, enrolled_ids)

    async def verify_and_advance(self, session: AsyncSession, user: User, stage_id: int) -> VerifyResult:
        progress = await stage_crud.get_progress(session, user.id, stage_id)
        if progress is None:
            raise NotEnrolledError(f"Not enrolled in stage {stage_id}")

        stage = await stage_def_crud.get_stage(session, stage_id)
        problem = stage.problems[progress.current_problem_index]
        platform = problem["platform"]

        handle = self._get_handle(user, platform)
        if not handle:
            raise NoPlatformAccountError(platform)

        verifier = self._verifiers.get(platform)
        if verifier is None:
            raise ValueError(f"Unsupported platform: {platform}")

        solved = await verifier.verify(handle, problem["url"], progress.assigned_at)

        if not solved:
            return VerifyResult(solved=False, problem_rewards={}, stage_complete=False, stage_rewards=None)

        problem_rewards = problem["rewards"]
        await stage_crud.award_rewards(session, user.stats, problem_rewards["exp"], problem_rewards["coins"])

        next_index = progress.current_problem_index + 1
        stage_complete = next_index >= len(stage.problems)

        if stage_complete:
            await stage_crud.complete_stage(session, progress)
            stage_rewards = {"exp": stage.rewards_exp, "coins": stage.rewards_coins}
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
