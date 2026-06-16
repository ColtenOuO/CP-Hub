import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.db import Base

if TYPE_CHECKING:
    from backend.app.models.user import User


class UserStageProgress(Base):
    __tablename__ = "user_stage_progress"
    __table_args__ = (UniqueConstraint("user_id", "stage_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    stage_id: Mapped[int]
    current_problem_index: Mapped[int] = mapped_column(default=0)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    user: Mapped["User"] = relationship(back_populates="stage_progress")
