from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.stage import Stage


class StageNotFoundError(ValueError):
    pass


class ProblemIndexError(IndexError):
    pass


async def get_stage(session: AsyncSession, stage_id: int) -> Stage | None:
    result = await session.execute(select(Stage).where(Stage.id == stage_id))
    return result.scalar_one_or_none()


async def get_all_stages(session: AsyncSession) -> list[Stage]:
    result = await session.execute(select(Stage))
    return list(result.scalars().all())


async def create_stage(session: AsyncSession, name: str, rewards_exp: int, rewards_coins: int) -> Stage:
    stage = Stage(name=name, requires=[], problems=[], rewards_exp=rewards_exp, rewards_coins=rewards_coins)
    session.add(stage)
    await session.commit()
    await session.refresh(stage)
    return stage


async def delete_stage(session: AsyncSession, stage_id: int) -> bool:
    stage = await get_stage(session, stage_id)
    if stage is None:
        return False
    await session.delete(stage)
    await session.commit()
    return True


async def set_requires(session: AsyncSession, stage_id: int, requires: list[int]) -> Stage:
    stage = await get_stage(session, stage_id)
    if stage is None:
        raise StageNotFoundError(f"Stage {stage_id} not found")
    stage.requires = requires
    await session.commit()
    await session.refresh(stage)
    return stage


async def add_problem(session: AsyncSession, stage_id: int, problem: dict) -> Stage:
    stage = await get_stage(session, stage_id)
    if stage is None:
        raise StageNotFoundError(f"Stage {stage_id} not found")
    stage.problems = [*stage.problems, problem]
    await session.commit()
    await session.refresh(stage)
    return stage


async def remove_problem(session: AsyncSession, stage_id: int, problem_index: int) -> Stage:
    stage = await get_stage(session, stage_id)
    if stage is None:
        raise StageNotFoundError(f"Stage {stage_id} not found")
    if problem_index < 0 or problem_index >= len(stage.problems):
        raise ProblemIndexError(f"Problem index {problem_index} out of range (stage has {len(stage.problems)} problems)")
    stage.problems = [p for i, p in enumerate(stage.problems) if i != problem_index]
    await session.commit()
    await session.refresh(stage)
    return stage
