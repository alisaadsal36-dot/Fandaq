"""
Hotel model — the root entity for multi-tenancy.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    whatsapp_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        comment="Meta WhatsApp Business phone number ID"
    )
    owner_whatsapp: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Owner phone number for approval messages"
    )
    owner_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Owner email address for receiving reports"
    )
    webhook_verify_token: Mapped[str] = mapped_column(
        String(255), nullable=True,
        comment="Per-hotel webhook verification token"
    )
    telegram_owner_chat_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True,
        comment="Telegram chat ID of the hotel owner for notifications"
    )
    whatsapp_api_token: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Per-hotel WhatsApp Business API token"
    )
    telegram_bot_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Per-hotel Telegram Bot API token"
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    room_types = relationship("RoomType", back_populates="hotel", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="hotel", cascade="all, delete-orphan")
    guests = relationship("Guest", back_populates="hotel", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="hotel", cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="hotel", cascade="all, delete-orphan")
    guest_requests = relationship("GuestRequest", back_populates="hotel", cascade="all, delete-orphan")
    whatsapp_sessions = relationship("WhatsAppSession", back_populates="hotel", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="hotel", cascade="all, delete-orphan")
    daily_prices = relationship("DailyPricing", back_populates="hotel", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="hotel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Hotel {self.name} ({self.id})>"
