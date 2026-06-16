import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user_stage_progress import UserStageProgress
from backend.app.models.user_stats import UserStats


async def get_progress(session: AsyncSession, user_id: uuid.UUID, stage_id: int) -> UserStageProgress | None:
    result = await session.execute(
        select(UserStageProgress).where(
            UserStageProgress.user_id == user_id,
            UserStageProgress.stage_id == stage_id,
        )
    )
    return result.scalar_one_or_none()


async def get_all_progress(session: AsyncSession, user_id: uuid.UUID) -> list[UserStageProgress]:
    result = await session.execute(select(UserStageProgress).where(UserStageProgress.user_id == user_id))
    return list(result.scalars().all())


async def create_progress(session: AsyncSession, user_id: uuid.UUID, stage_id: int) -> UserStageProgress:
    progress = UserStageProgress(user_id=user_id, stage_id=stage_id)
    session.add(progress)
    await session.commit()
    return progress


async def advance_problem(session: AsyncSession, progress: UserStageProgress, next_index: int) -> None:
    progress.current_problem_index = next_index
    progress.assigned_at = datetime.now(timezone.utc)
    await session.commit()


async def complete_stage(session: AsyncSession, progress: UserStageProgress) -> None:
    progress.is_completed = True
    progress.completed_at = datetime.now(timezone.utc)
    await session.commit()


async def award_rewards(session: AsyncSession, stats: UserStats, exp: int, coins: int) -> None:
    stats.exp += exp
    stats.coins += coins
    await session.commit()
