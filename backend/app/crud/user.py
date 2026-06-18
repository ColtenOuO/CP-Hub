from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.user import User
from backend.app.models.user_stats import UserStats


class AccountIDAlreadyLinkedError(Exception):
    """Raised when one or more of the given platform account IDs are already linked to another user."""

    def __init__(self, conflicts: dict[str, str]):
        self.conflicts = conflicts
        super().__init__(f"Account IDs already linked to another user: {conflicts}")


async def get_user_by_discord_id(session: AsyncSession, discord_id: int) -> User | None:
    result = await session.execute(select(User).where(User.discord_id == discord_id).options(selectinload(User.stats)))
    return result.scalar_one_or_none()


async def get_top_by_level(session: AsyncSession, limit: int = 10) -> list[User]:
    result = await session.execute(
        select(User)
        .join(UserStats, UserStats.user_id == User.id)
        .options(selectinload(User.stats))
        .order_by(UserStats.level.desc(), UserStats.exp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_top_by_coins(session: AsyncSession, limit: int = 10) -> list[User]:
    result = await session.execute(
        select(User).join(UserStats, UserStats.user_id == User.id).options(selectinload(User.stats)).order_by(UserStats.coins.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def upsert_account_links(
    session: AsyncSession,
    discord_id: int,
    username: str,
    leetcode_id: str | None = None,
    codeforces_id: str | None = None,
    atcoder_id: str | None = None,
) -> User:
    """Creates a user with the given platform account IDs if none exists for the discord_id, otherwise updates it."""
    user = await get_user_by_discord_id(session, discord_id)

    new_links = {"leetcode_id": leetcode_id, "codeforces_id": codeforces_id, "atcoder_id": atcoder_id}

    conflicts: dict[str, str] = {}
    for field, value in new_links.items():
        if value is None:
            continue

        result = await session.execute(select(User).where(getattr(User, field) == value))
        other_user = result.scalar_one_or_none()

        if other_user is not None and (user is None or other_user.id != user.id):
            conflicts[field] = value

    if conflicts:
        raise AccountIDAlreadyLinkedError(conflicts)

    if user is None:
        user = User(discord_id=discord_id, username=username, stats=UserStats())
        session.add(user)

    for field, value in new_links.items():
        if value is not None:
            setattr(user, field, value)

    await session.commit()
    return user
