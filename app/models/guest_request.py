"""
GuestRequest model — service requests from guests.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RequestStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class GuestRequest(Base):
    __tablename__ = "guest_requests"

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
    request_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. towels, room_cleaning, extra_bed"
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.OPEN, nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Time of first response/acknowledgement"
    )
    first_response_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="User who first acknowledged this request"
    )
    first_response_by_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot name of first responder"
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="User assigned by supervisor/admin to execute this request"
    )
    assigned_to_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot name of assigned executor"
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fulfillment_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="pending, partial, completed, failed"
    )
    fulfillment_details: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Timeline of fulfillment steps"
    )
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="User who completed this request"
    )
    completed_by_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot name of completer"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    hotel = relationship("Hotel", back_populates="guest_requests")
    guest = relationship("Guest", back_populates="guest_requests")

    def __repr__(self) -> str:
        return f"<GuestRequest {self.request_type} ({self.status.value})>"
