"""
Complaint model — guest complaint tracking.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ComplaintStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    guest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guests.id", ondelete="SET NULL"),
        nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus), default=ComplaintStatus.OPEN, nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Time of first response/acknowledgement"
    )
    first_response_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="User who first acknowledged this complaint"
    )
    first_response_by_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot name of first responder"
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="User assigned by supervisor/admin to resolve this complaint"
    )
    assigned_to_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot name of assigned resolver"
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="User who resolved this complaint"
    )
    resolved_by_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot name of resolver"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    hotel = relationship("Hotel", back_populates="complaints")
    guest = relationship("Guest", back_populates="complaints")

    def __repr__(self) -> str:
        return f"<Complaint {self.id} ({self.status.value})>"
