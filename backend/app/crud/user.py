from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.user_stats import UserStats


class LeetCodeIDAlreadyLinkedError(Exception):
    """Raised when the given LeetCode ID is already linked to another user."""


async def get_user_by_discord_id(session: AsyncSession, discord_id: int) -> User | None:
    result = await session.execute(select(User).where(User.discord_id == discord_id))
    return result.scalar_one_or_none()


async def upsert_leetcode_link(session: AsyncSession, discord_id: int, username: str, leetcode_id: str) -> User:
    """Creates a user with the given LeetCode ID if none exists for the discord_id, otherwise updates it."""
    user = await get_user_by_discord_id(session, discord_id)

    if user is None:
        user = User(discord_id=discord_id, username=username, leetcode_id=leetcode_id, stats=UserStats())
        session.add(user)
    else:
        user.leetcode_id = leetcode_id

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise LeetCodeIDAlreadyLinkedError(f"LeetCode ID '{leetcode_id}' is already linked to another account.") from exc

    return user
