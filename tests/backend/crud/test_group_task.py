from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.group_task import (
    create_task,
    delete_task,
    finalize_task,
    get_active_task,
    get_claimed_incomplete_by_user,
    get_problems_by_codes,
    mark_claimed,
    mark_completed,
    mark_unclaimed,
)
from backend.app.crud.user import get_user_by_discord_id, upsert_account_links

DISCORD_ID_A = 900000000000000031

SAMPLE_PROBLEMS = [
    {"code": "E1", "difficulty": "easy", "title": "Two Sum", "url": "https://leetcode.com/problems/two-sum/", "title_slug": "two-sum"},
    {
        "code": "M1",
        "difficulty": "medium",
        "title": "Add Two Numbers",
        "url": "https://leetcode.com/problems/add-two-numbers/",
        "title_slug": "add-two-numbers",
    },
]


@pytest.fixture(autouse=True)
async def cleanup():
    created_task_ids: list = []
    yield created_task_ids

    async with AsyncSessionLocal() as session:
        for task_id in created_task_ids:
            await delete_task(session, task_id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        if user is not None:
            await session.delete(user)
        await session.commit()


async def _make_task(cleanup):
    async with AsyncSessionLocal() as session:
        task = await create_task(
            session,
            deadline=datetime.now(timezone.utc) + timedelta(days=1),
            reward_exp=100,
            reward_coins=50,
            created_by=DISCORD_ID_A,
            channel_id=123456,
            problems=SAMPLE_PROBLEMS,
        )
    cleanup.append(task.id)
    return task


@pytest.mark.asyncio
async def test_create_task_writes_problems(cleanup):
    task = await _make_task(cleanup)

    assert task.status == "active"
    assert {p.code for p in task.problems} == {"E1", "M1"}


@pytest.mark.asyncio
async def test_get_active_task_only_returns_active(cleanup):
    task = await _make_task(cleanup)

    async with AsyncSessionLocal() as session:
        active = await get_active_task(session)
    assert active is not None
    assert active.id == task.id

    async with AsyncSessionLocal() as session:
        await finalize_task(session, task.id, "completed")

    async with AsyncSessionLocal() as session:
        active = await get_active_task(session)
    assert active is None


@pytest.mark.asyncio
async def test_claim_unclaim_and_complete_cycle(cleanup):
    task = await _make_task(cleanup)

    async with AsyncSessionLocal() as session:
        user = await upsert_account_links(session, discord_id=DISCORD_ID_A, username="grouptask_crud_a", leetcode_id="neal_wu")

    async with AsyncSessionLocal() as session:
        [problem] = await get_problems_by_codes(session, task.id, ["E1"])
        await mark_claimed(session, problem, user.id)

    async with AsyncSessionLocal() as session:
        [problem] = await get_problems_by_codes(session, task.id, ["E1"])
        assert problem.claimed_by == user.id
        assert problem.claimed_at is not None

        claimed = await get_claimed_incomplete_by_user(session, task.id, user.id)
        assert {p.code for p in claimed} == {"E1"}

        await mark_unclaimed(session, problem)

    async with AsyncSessionLocal() as session:
        [problem] = await get_problems_by_codes(session, task.id, ["E1"])
        assert problem.claimed_by is None

        await mark_claimed(session, problem, user.id)
        await mark_completed(session, problem, user.id)

    async with AsyncSessionLocal() as session:
        [problem] = await get_problems_by_codes(session, task.id, ["E1"])
        assert problem.is_completed is True
        assert problem.completed_by == user.id

        claimed = await get_claimed_incomplete_by_user(session, task.id, user.id)
        assert claimed == []


@pytest.mark.asyncio
async def test_finalize_task_is_idempotent(cleanup):
    task = await _make_task(cleanup)

    async with AsyncSessionLocal() as session:
        result1 = await finalize_task(session, task.id, "completed")
    assert result1 is not None
    assert result1.status == "completed"

    async with AsyncSessionLocal() as session:
        result2 = await finalize_task(session, task.id, "expired")
    assert result2 is None
