"""
Employee evaluation model — supervisor survey submitted to admin.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    NEEDS_IMPROVEMENT = "needs_improvement"


class EmployeeEvaluation(Base):
    __tablename__ = "employee_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    employee_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)

    supervisor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False, index=True
    )
    supervisor_name: Mapped[str] = mapped_column(String(255), nullable=False)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    commitment_score: Mapped[int] = mapped_column(Integer, nullable=False)
    speed_score: Mapped[int] = mapped_column(Integer, nullable=False)
    communication_score: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False)

    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    supervisor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus), nullable=False, default=EvaluationStatus.SUBMITTED
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    reviewed_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<EmployeeEvaluation {self.employee_name} {self.period_start}->{self.period_end}>"
