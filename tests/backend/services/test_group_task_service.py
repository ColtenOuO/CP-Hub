from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.group_task import delete_task, get_task_with_problems
from backend.app.crud.user import get_user_by_discord_id, upsert_account_links
from backend.app.services.group_task.service import ActiveTaskExistsError, GroupTaskService, NoActiveTaskError

DISCORD_ID_A = 900000000000000041
DISCORD_ID_B = 900000000000000042


class StubLeetCodeService:
    def __init__(self, solved_slugs: set[str] | None = None):
        self.solved_slugs = solved_slugs or set()

    async def draw_problems(self, difficulty, count):
        return [
            {
                "title": f"{difficulty} Problem {i}",
                "titleSlug": f"{difficulty.lower()}-problem-{i}",
                "url": f"https://leetcode.com/problems/{difficulty.lower()}-problem-{i}/",
            }
            for i in range(1, count + 1)
        ]

    async def draw_random_problems(
        self,
        difficulty,
        count=1,
        tags=None,
        choosing_window_size=100,
        take_per_window=1,
        max_attempts=30,
    ):
        return await self.draw_problems(difficulty=difficulty, count=count)

    async def verify_problem_solved(self, handle, slug, after):
        return slug in self.solved_slugs


@pytest.fixture(autouse=True)
async def cleanup():
    task_ids: list = []
    yield task_ids

    async with AsyncSessionLocal() as session:
        for task_id in task_ids:
            await delete_task(session, task_id)
        for discord_id in (DISCORD_ID_A, DISCORD_ID_B):
            user = await get_user_by_discord_id(session, discord_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


async def _create_task(service: GroupTaskService, cleanup, **overrides):
    defaults = dict(
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        reward_exp=500,
        reward_coins=200,
        created_by=DISCORD_ID_A,
        channel_id=123,
    )
    defaults.update(overrides)
    async with AsyncSessionLocal() as session:
        task = await service.create_task(session, **defaults)
    cleanup.append(task.id)
    return task


@pytest.mark.asyncio
async def test_create_task_draws_ten_of_each_difficulty(cleanup):
    service = GroupTaskService(StubLeetCodeService())
    task = await _create_task(service, cleanup)

    expected_codes = {f"{prefix}{i}" for prefix in ("E", "M", "H") for i in range(1, 11)}
    assert {p.code for p in task.problems} == expected_codes


@pytest.mark.asyncio
async def test_create_task_rejects_when_active_task_exists(cleanup):
    service = GroupTaskService(StubLeetCodeService())
    await _create_task(service, cleanup)

    async with AsyncSessionLocal() as session:
        with pytest.raises(ActiveTaskExistsError):
            await service.create_task(
                session,
                deadline=datetime.now(timezone.utc) + timedelta(days=1),
                reward_exp=1,
                reward_coins=1,
                created_by=DISCORD_ID_A,
                channel_id=1,
            )


@pytest.mark.asyncio
async def test_delete_active_task_raises_when_none(cleanup):
    service = GroupTaskService(StubLeetCodeService())
    async with AsyncSessionLocal() as session:
        with pytest.raises(NoActiveTaskError):
            await service.delete_active_task(session)


@pytest.mark.asyncio
async def test_claim_and_verify_awards_rewards(cleanup):
    service = GroupTaskService(StubLeetCodeService(solved_slugs={"easy-problem-1"}))

    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="grouptask_svc_a", leetcode_id="solver_a")

    task = await _create_task(service, cleanup)

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        claim_result = await service.claim(session, task, user, ["E1"])
    assert claim_result == {"E1": "認領成功"}

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        verify_result = await service.verify(session, task, user, ["E1"])

    assert len(verify_result.succeeded) == 1
    assert verify_result.succeeded[0].exp == 30
    assert verify_result.succeeded[0].coins == 10
    assert verify_result.failed == []
    assert verify_result.task_completed is False

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
    assert user.stats.coins == 10
    assert user.stats.exp == 30


@pytest.mark.asyncio
async def test_verify_rejects_unclaimed_and_unsolved(cleanup):
    service = GroupTaskService(StubLeetCodeService(solved_slugs=set()))

    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="grouptask_svc_a2", leetcode_id="solver_a2")
        await upsert_account_links(session, discord_id=DISCORD_ID_B, username="grouptask_svc_b2", leetcode_id="solver_b2")

    task = await _create_task(service, cleanup)

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user_b = await get_user_by_discord_id(session, DISCORD_ID_B)
        result = await service.verify(session, task, user_b, ["E1"])
    assert result.succeeded == []
    assert result.failed[0].reason == "你沒有認領此題"

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user_a = await get_user_by_discord_id(session, DISCORD_ID_A)
        await service.claim(session, task, user_a, ["E1"])

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user_a = await get_user_by_discord_id(session, DISCORD_ID_A)
        result = await service.verify(session, task, user_a, ["E1"])
    assert result.succeeded == []
    assert result.failed[0].reason == "尚未偵測到 AC 提交"


@pytest.mark.asyncio
async def test_finalize_completed_awards_bonus_once(cleanup):
    service = GroupTaskService(StubLeetCodeService(solved_slugs={"easy-problem-1", "medium-problem-1"}))

    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="grouptask_svc_finalize", leetcode_id="solver_fin")

    task = await _create_task(service, cleanup, reward_exp=500, reward_coins=200)

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        await service.claim(session, task, user, ["E1", "M1"])

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        await service.verify(session, task, user, ["E1", "M1"])

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
    coins_before_finalize = user.stats.coins  # 10 (easy) + 30 (medium) = 40

    async with AsyncSessionLocal() as session:
        recap = await service.finalize(session, task.id, "completed")
    assert recap is not None
    assert recap.status == "completed"
    assert recap.completed_problems == 2
    assert recap.entries[0].user.username == "grouptask_svc_finalize"
    assert recap.entries[0].total == 2
    assert recap.bonus_exp == 500
    assert recap.bonus_coins == 200

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
    assert user.stats.coins == coins_before_finalize + 200

    async with AsyncSessionLocal() as session:
        recap2 = await service.finalize(session, task.id, "expired")
    assert recap2 is None

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
    assert user.stats.coins == coins_before_finalize + 200


@pytest.mark.asyncio
async def test_finalize_in_same_session_as_completing_verify(cleanup):
    """Regression test: finalize() used to crash with AttributeError on completed_by_user
    when called in the same session as the verify() that completed the last problem,
    because the bulk UPDATE in mark_completed only syncs column attributes (is_completed,
    completed_by) onto identity-mapped objects, not the completed_by_user relationship."""
    all_codes = [f"{prefix}{i}" for prefix in ("E", "M", "H") for i in range(1, 11)]
    solved_slugs = {f"{d}-problem-{i}" for d in ("easy", "medium", "hard") for i in range(1, 11)}
    service = GroupTaskService(StubLeetCodeService(solved_slugs=solved_slugs))

    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="grouptask_svc_same_session", leetcode_id="solver_same")

    task = await _create_task(service, cleanup, reward_exp=500, reward_coins=200)

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        await service.claim(session, task, user, all_codes)

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        verify_result = await service.verify(session, task, user, all_codes)
        assert verify_result.task_completed is True

        recap = await service.finalize(session, task.id, "completed")

    assert recap is not None
    assert recap.completed_problems == 30
    assert recap.entries[0].user.id == user.id
    assert recap.entries[0].total == 30
    assert recap.bonus_exp == 500
    assert recap.bonus_coins == 200


@pytest.mark.asyncio
async def test_finalize_expired_does_not_award_bonus(cleanup):
    service = GroupTaskService(StubLeetCodeService(solved_slugs={"easy-problem-1"}))

    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="grouptask_svc_expired", leetcode_id="solver_exp")

    task = await _create_task(service, cleanup, reward_exp=500, reward_coins=200)

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        await service.claim(session, task, user, ["E1"])

    async with AsyncSessionLocal() as session:
        task = await get_task_with_problems(session, task.id)
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
        await service.verify(session, task, user, ["E1"])

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
    coins_before = user.stats.coins  # 10, from the per-problem reward only

    async with AsyncSessionLocal() as session:
        recap = await service.finalize(session, task.id, "expired")
    assert recap.bonus_exp == 0
    assert recap.bonus_coins == 0
    assert recap.completed_problems == 1

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)
    assert user.stats.coins == coins_before
