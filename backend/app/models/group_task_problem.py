import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.db import Base

if TYPE_CHECKING:
    from backend.app.models.group_task import GroupTask
    from backend.app.models.user import User


class GroupTaskProblem(Base):
    __tablename__ = "group_task_problems"
    __table_args__ = (UniqueConstraint("group_task_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_tasks.id"))
    code: Mapped[str] = mapped_column(String(8))
    difficulty: Mapped[str] = mapped_column(String(8))
    title: Mapped[str]
    url: Mapped[str]
    title_slug: Mapped[str]
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_completed: Mapped[bool] = mapped_column(default=False)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    group_task: Mapped["GroupTask"] = relationship(back_populates="problems")
    claimed_by_user: Mapped["User | None"] = relationship(foreign_keys=[claimed_by])
    completed_by_user: Mapped["User | None"] = relationship(foreign_keys=[completed_by])
