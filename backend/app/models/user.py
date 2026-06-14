import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.db import Base

if TYPE_CHECKING:
    from backend.app.models.user_stats import UserStats


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    atcoder_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    codeforces_id: Mapped[str | None] = mapped_column(String(32), unique=True)

    stats: Mapped["UserStats"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
