"""
GuestRequest Pydantic schemas.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.guest_request import RequestStatus


class GuestRequestCreate(BaseModel):
    request_type: str = Field(..., min_length=1, max_length=100)
    details: str | None = None
    guest_id: uuid.UUID | None = None


class GuestRequestStatusUpdate(BaseModel):
    status: RequestStatus


class GuestRequestAssignRequest(BaseModel):
    assigned_to_user_id: uuid.UUID


class GuestRequestFulfillmentCreate(BaseModel):
    item: str = Field(..., min_length=1, max_length=200)
    status: str = Field(..., pattern="^(delivered|pending|failed)$")
    notes: str | None = Field(default=None, max_length=500)


class GuestRequestResponse(BaseModel):
    id: uuid.UUID
    hotel_id: uuid.UUID
    guest_id: uuid.UUID | None
    request_type: str
    details: str | None
    status: RequestStatus
    assigned_to_user_id: uuid.UUID | None = None
    assigned_to_name: str | None = None
    assigned_at: datetime | None = None
    fulfillment_status: str | None = None
    fulfillment_details: list[dict] = Field(default_factory=list)
    acknowledged_at: datetime | None = None
    first_response_by_name: str | None = None
    created_at: datetime
    completed_at: datetime | None
    completed_by_name: str | None = None

    model_config = {"from_attributes": True}


class GuestRequestListResponse(BaseModel):
    requests: list[GuestRequestResponse]
    total: int
