import pytest

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.user import LeetCodeIDAlreadyLinkedError, get_user_by_discord_id, upsert_leetcode_link

DISCORD_ID_A = 900000000000000001
DISCORD_ID_B = 900000000000000002


@pytest.fixture(autouse=True)
async def cleanup_users():
    yield

    async with AsyncSessionLocal() as session:
        for discord_id in (DISCORD_ID_A, DISCORD_ID_B):
            user = await get_user_by_discord_id(session, discord_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


@pytest.mark.asyncio
async def test_get_user_by_discord_id_not_found():
    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)

    assert user is None


@pytest.mark.asyncio
async def test_upsert_leetcode_link_creates_user():
    async with AsyncSessionLocal() as session:
        user = await upsert_leetcode_link(session, discord_id=DISCORD_ID_A, username="test_user_a", leetcode_id="neal_wu")

        assert user.discord_id == DISCORD_ID_A
        assert user.leetcode_id == "neal_wu"
        assert user.stats.level == 1
        assert user.stats.coins == 0


@pytest.mark.asyncio
async def test_upsert_leetcode_link_updates_existing_user():
    async with AsyncSessionLocal() as session:
        await upsert_leetcode_link(session, discord_id=DISCORD_ID_A, username="test_user_a", leetcode_id="neal_wu")

    async with AsyncSessionLocal() as session:
        user = await upsert_leetcode_link(session, discord_id=DISCORD_ID_A, username="test_user_a", leetcode_id="votrubac")

        assert user.leetcode_id == "votrubac"

    async with AsyncSessionLocal() as session:
        user = await get_user_by_discord_id(session, DISCORD_ID_A)

        assert user.leetcode_id == "votrubac"


@pytest.mark.asyncio
async def test_upsert_leetcode_link_rejects_duplicate_leetcode_id():
    async with AsyncSessionLocal() as session:
        await upsert_leetcode_link(session, discord_id=DISCORD_ID_A, username="test_user_a", leetcode_id="neal_wu")

    async with AsyncSessionLocal() as session:
        with pytest.raises(LeetCodeIDAlreadyLinkedError):
            await upsert_leetcode_link(session, discord_id=DISCORD_ID_B, username="test_user_b", leetcode_id="neal_wu")
