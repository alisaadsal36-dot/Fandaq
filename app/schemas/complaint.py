"""
Complaint Pydantic schemas.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.complaint import ComplaintStatus


class ComplaintCreate(BaseModel):
    text: str = Field(..., min_length=1)
    guest_id: uuid.UUID | None = None


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus


class ComplaintAssignRequest(BaseModel):
    assigned_to_user_id: uuid.UUID


class ComplaintResponse(BaseModel):
    id: uuid.UUID
    hotel_id: uuid.UUID
    guest_id: uuid.UUID | None
    guest_name: str | None = None
    guest_phone: str | None = None
    room_number: str | None = None
    text: str
    status: ComplaintStatus
    assigned_to_user_id: uuid.UUID | None = None
    assigned_to_name: str | None = None
    assigned_at: datetime | None = None
    acknowledged_at: datetime | None = None
    first_response_by_name: str | None = None
    resolved_by_name: str | None = None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ComplaintListResponse(BaseModel):
    complaints: list[ComplaintResponse]
    total: int


class AssignableStaffItem(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str


class AssignableStaffResponse(BaseModel):
    users: list[AssignableStaffItem]
