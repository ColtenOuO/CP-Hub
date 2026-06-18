import pytest

from backend.app.core.db import AsyncSessionLocal
from backend.app.crud.platform_stats import (
    get_cache_by_user_id,
    get_top_by_codeforces,
    get_top_by_leetcode,
    get_users_with_any_platform_link,
    upsert_codeforces_stats,
    upsert_leetcode_stats,
)
from backend.app.crud.user import get_top_by_coins, get_top_by_level, get_user_by_discord_id, upsert_account_links

DISCORD_ID_A = 900000000000000011
DISCORD_ID_B = 900000000000000012
DISCORD_ID_C = 900000000000000013


@pytest.fixture(autouse=True)
async def cleanup_users():
    yield

    async with AsyncSessionLocal() as session:
        for discord_id in (DISCORD_ID_A, DISCORD_ID_B, DISCORD_ID_C):
            user = await get_user_by_discord_id(session, discord_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


@pytest.mark.asyncio
async def test_upsert_leetcode_stats_is_update_not_insert():
    async with AsyncSessionLocal() as session:
        user = await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a", leetcode_id="neal_wu")

    async with AsyncSessionLocal() as session:
        await upsert_leetcode_stats(session, user.id, easy=1, medium=2, hard=3)

    async with AsyncSessionLocal() as session:
        await upsert_leetcode_stats(session, user.id, easy=10, medium=20, hard=30)
        cache = await get_cache_by_user_id(session, user.id)

    assert cache.leetcode_easy == 10
    assert cache.leetcode_medium == 20
    assert cache.leetcode_hard == 30
    assert cache.leetcode_synced_at is not None


@pytest.mark.asyncio
async def test_upsert_codeforces_stats():
    async with AsyncSessionLocal() as session:
        user = await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a", codeforces_id="tourist")

    async with AsyncSessionLocal() as session:
        await upsert_codeforces_stats(session, user.id, solved=42)
        cache = await get_cache_by_user_id(session, user.id)

    assert cache.codeforces_solved == 42
    assert cache.codeforces_synced_at is not None


@pytest.mark.asyncio
async def test_get_users_with_any_platform_link_excludes_unlinked():
    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a", leetcode_id="neal_wu")
        await upsert_account_links(session, discord_id=DISCORD_ID_B, username="test_platform_b", codeforces_id="tourist")
        await upsert_account_links(session, discord_id=DISCORD_ID_C, username="test_platform_c")

    async with AsyncSessionLocal() as session:
        linked = await get_users_with_any_platform_link(session)

    linked_discord_ids = {u.discord_id for u in linked}
    assert DISCORD_ID_A in linked_discord_ids
    assert DISCORD_ID_B in linked_discord_ids
    assert DISCORD_ID_C not in linked_discord_ids


@pytest.mark.asyncio
async def test_get_top_by_leetcode_orders_by_total_and_excludes_unsynced():
    async with AsyncSessionLocal() as session:
        user_a = await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a", leetcode_id="neal_wu")
        user_b = await upsert_account_links(session, discord_id=DISCORD_ID_B, username="test_platform_b", leetcode_id="errichto")
        await upsert_account_links(session, discord_id=DISCORD_ID_C, username="test_platform_c", leetcode_id="some_other_id")

    async with AsyncSessionLocal() as session:
        await upsert_leetcode_stats(session, user_a.id, easy=1, medium=1, hard=1)
        await upsert_leetcode_stats(session, user_b.id, easy=10, medium=10, hard=10)

    async with AsyncSessionLocal() as session:
        top = await get_top_by_leetcode(session, limit=10)

    top_usernames = [user.username for user, _ in top]
    assert top_usernames.index("test_platform_b") < top_usernames.index("test_platform_a")
    assert "test_platform_c" not in top_usernames


@pytest.mark.asyncio
async def test_get_top_by_codeforces_orders_by_solved_and_excludes_unsynced():
    async with AsyncSessionLocal() as session:
        user_a = await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a", codeforces_id="tourist")
        user_b = await upsert_account_links(session, discord_id=DISCORD_ID_B, username="test_platform_b", codeforces_id="errichto")
        await upsert_account_links(session, discord_id=DISCORD_ID_C, username="test_platform_c", codeforces_id="some_other_handle")

    async with AsyncSessionLocal() as session:
        await upsert_codeforces_stats(session, user_a.id, solved=5)
        await upsert_codeforces_stats(session, user_b.id, solved=50)

    async with AsyncSessionLocal() as session:
        top = await get_top_by_codeforces(session, limit=10)

    top_usernames = [user.username for user, _ in top]
    assert top_usernames.index("test_platform_b") < top_usernames.index("test_platform_a")
    assert "test_platform_c" not in top_usernames


@pytest.mark.asyncio
async def test_get_top_by_level_orders_by_level_then_exp():
    # Use an implausibly high level so these two synthetic users sort above any
    # real users already in this shared dev database, keeping them within the limit.
    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a")
        await upsert_account_links(session, discord_id=DISCORD_ID_B, username="test_platform_b")

    async with AsyncSessionLocal() as session:
        user_a = await get_user_by_discord_id(session, DISCORD_ID_A)
        user_b = await get_user_by_discord_id(session, DISCORD_ID_B)
        user_a.stats.level = 999999
        user_a.stats.exp = 10
        user_b.stats.level = 999999
        user_b.stats.exp = 50
        await session.commit()

    async with AsyncSessionLocal() as session:
        top = await get_top_by_level(session, limit=10)

    top_usernames = [user.username for user in top]
    assert top_usernames.index("test_platform_b") < top_usernames.index("test_platform_a")


@pytest.mark.asyncio
async def test_get_top_by_coins_orders_by_coins_desc():
    # Use an implausibly high coin amount so these two synthetic users sort above any
    # real users already in this shared dev database, keeping them within the limit.
    async with AsyncSessionLocal() as session:
        await upsert_account_links(session, discord_id=DISCORD_ID_A, username="test_platform_a")
        await upsert_account_links(session, discord_id=DISCORD_ID_B, username="test_platform_b")

    async with AsyncSessionLocal() as session:
        user_a = await get_user_by_discord_id(session, DISCORD_ID_A)
        user_b = await get_user_by_discord_id(session, DISCORD_ID_B)
        user_a.stats.coins = 999999
        user_b.stats.coins = 9999999
        await session.commit()

    async with AsyncSessionLocal() as session:
        top = await get_top_by_coins(session, limit=10)

    top_usernames = [user.username for user in top]
    assert top_usernames.index("test_platform_b") < top_usernames.index("test_platform_a")
