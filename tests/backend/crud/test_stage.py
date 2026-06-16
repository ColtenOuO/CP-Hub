import pytest

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.stage import (
    advance_problem,
    award_rewards,
    complete_stage,
    create_progress,
    get_all_progress,
    get_progress,
)
from backend.app.crud.user import get_user_by_discord_id, upsert_account_links

DISCORD_ID = 900000000000000010


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID)
        if user is not None:
            await session.delete(user)
        await session.commit()


@pytest.fixture
async def user():
    async with AsyncSessionLocal() as session:
        u = await upsert_account_links(session, discord_id=DISCORD_ID, username="stage_test_user")
    return u


@pytest.mark.asyncio
async def test_get_progress_not_found(user):
    async with AsyncSessionLocal() as session:
        result = await get_progress(session, user.id, stage_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_create_progress(user):
    async with AsyncSessionLocal() as session:
        progress = await create_progress(session, user.id, stage_id=1)

    assert progress.user_id == user.id
    assert progress.stage_id == 1
    assert progress.current_problem_index == 0
    assert progress.is_completed is False
    assert progress.completed_at is None
    assert progress.assigned_at is not None


@pytest.mark.asyncio
async def test_get_progress_found(user):
    async with AsyncSessionLocal() as session:
        await create_progress(session, user.id, stage_id=1)

    async with AsyncSessionLocal() as session:
        result = await get_progress(session, user.id, stage_id=1)

    assert result is not None
    assert result.stage_id == 1


@pytest.mark.asyncio
async def test_get_all_progress_empty(user):
    async with AsyncSessionLocal() as session:
        result = await get_all_progress(session, user.id)
    assert result == []


@pytest.mark.asyncio
async def test_get_all_progress_multiple(user):
    async with AsyncSessionLocal() as session:
        await create_progress(session, user.id, stage_id=1)
        await create_progress(session, user.id, stage_id=2)

    async with AsyncSessionLocal() as session:
        result = await get_all_progress(session, user.id)

    assert len(result) == 2
    stage_ids = {p.stage_id for p in result}
    assert stage_ids == {1, 2}


@pytest.mark.asyncio
async def test_advance_problem(user):
    async with AsyncSessionLocal() as session:
        progress = await create_progress(session, user.id, stage_id=1)
        original_assigned_at = progress.assigned_at

    async with AsyncSessionLocal() as session:
        progress = await get_progress(session, user.id, stage_id=1)
        await advance_problem(session, progress, next_index=1)

    async with AsyncSessionLocal() as session:
        progress = await get_progress(session, user.id, stage_id=1)

    assert progress.current_problem_index == 1
    assert progress.assigned_at > original_assigned_at


@pytest.mark.asyncio
async def test_complete_stage(user):
    async with AsyncSessionLocal() as session:
        await create_progress(session, user.id, stage_id=1)

    async with AsyncSessionLocal() as session:
        progress = await get_progress(session, user.id, stage_id=1)
        await complete_stage(session, progress)

    async with AsyncSessionLocal() as session:
        progress = await get_progress(session, user.id, stage_id=1)

    assert progress.is_completed is True
    assert progress.completed_at is not None


@pytest.mark.asyncio
async def test_award_rewards(user):
    async with AsyncSessionLocal() as session:
        u = await get_user_by_discord_id(session, DISCORD_ID)
        await award_rewards(session, u.stats, exp=150, coins=75)

    async with AsyncSessionLocal() as session:
        u = await get_user_by_discord_id(session, DISCORD_ID)

    assert u.stats.exp == 150
    assert u.stats.coins == 75


@pytest.mark.asyncio
async def test_award_rewards_accumulates(user):
    async with AsyncSessionLocal() as session:
        u = await get_user_by_discord_id(session, DISCORD_ID)
        await award_rewards(session, u.stats, exp=100, coins=50)

    async with AsyncSessionLocal() as session:
        u = await get_user_by_discord_id(session, DISCORD_ID)
        await award_rewards(session, u.stats, exp=50, coins=25)

    async with AsyncSessionLocal() as session:
        u = await get_user_by_discord_id(session, DISCORD_ID)

    assert u.stats.exp == 150
    assert u.stats.coins == 75
