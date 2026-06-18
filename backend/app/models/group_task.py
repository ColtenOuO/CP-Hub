import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.db import Base

if TYPE_CHECKING:
    from backend.app.models.group_task_problem import GroupTaskProblem


class GroupTask(Base):
    __tablename__ = "group_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(16), default="active")
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reward_exp: Mapped[int]
    reward_coins: Mapped[int]
    created_by: Mapped[int] = mapped_column(BigInteger)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    problems: Mapped[list["GroupTaskProblem"]] = relationship(back_populates="group_task", cascade="all, delete-orphan")
