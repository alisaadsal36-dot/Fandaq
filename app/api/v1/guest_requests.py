"""
Guest Requests API — manage service requests per hotel.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role_for_hotel
from app.database import get_db
from app.models.user import User, UserRole
from app.models.guest_request import RequestStatus
from app.schemas.guest_request import (
    GuestRequestCreate, GuestRequestResponse,
    GuestRequestStatusUpdate, GuestRequestListResponse,
    GuestRequestAssignRequest, GuestRequestFulfillmentCreate,
)
from app.services.guest_request import GuestRequestService

router = APIRouter(
    dependencies=[Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.EMPLOYEE))]
)


@router.post(
    "/hotels/{hotel_id}/guest-requests",
    response_model=GuestRequestResponse,
    status_code=201,
)
async def create_guest_request(
    hotel_id: uuid.UUID,
    data: GuestRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new guest request."""
    request = await GuestRequestService.create_request(
        db, hotel_id,
        request_type=data.request_type,
        guest_id=data.guest_id,
        details=data.details,
    )
    return request


@router.get(
    "/hotels/{hotel_id}/guest-requests",
    response_model=GuestRequestListResponse,
)
async def list_guest_requests(
    hotel_id: uuid.UUID,
    status: RequestStatus | None = None,
    skip: int = 0,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List guest requests with optional status filter."""
    result = await GuestRequestService.list_requests(
        db, hotel_id, status=status, skip=skip, limit=limit
    )
    return result


@router.patch(
    "/hotels/{hotel_id}/guest-requests/{request_id}",
    response_model=GuestRequestResponse,
)
async def update_request_status(
    hotel_id: uuid.UUID,
    request_id: uuid.UUID,
    data: GuestRequestStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.EMPLOYEE)),
):
    """Update guest request status."""
    request = await GuestRequestService.update_status(
        db, hotel_id, request_id, data.status, actor_user=current_user
    )
    if not request:
        raise HTTPException(status_code=404, detail="Guest request not found")
    return request


@router.patch(
    "/hotels/{hotel_id}/guest-requests/{request_id}/assign",
    response_model=GuestRequestResponse,
)
async def assign_guest_request(
    hotel_id: uuid.UUID,
    request_id: uuid.UUID,
    data: GuestRequestAssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR)),
):
    """Assign guest request to staff member (supervisor/admin only)."""
    from sqlalchemy import select

    assigned_to = (await db.execute(
        select(User).where(
            User.id == data.assigned_to_user_id,
            User.hotel_id == hotel_id,
            User.is_active == True,
            User.role.in_([UserRole.SUPERVISOR, UserRole.EMPLOYEE]),
        )
    )).scalar_one_or_none()
    if not assigned_to:
        raise HTTPException(status_code=404, detail="Assigned user not found in this hotel")

    request = await GuestRequestService.assign_request(
        db=db,
        hotel_id=hotel_id,
        request_id=request_id,
        assigned_to_user=assigned_to,
    )
    if not request:
        raise HTTPException(status_code=404, detail="Guest request not found")
    return request


@router.post(
    "/hotels/{hotel_id}/guest-requests/{request_id}/fulfillment",
    response_model=GuestRequestResponse,
)
async def add_guest_request_fulfillment(
    hotel_id: uuid.UUID,
    request_id: uuid.UUID,
    data: GuestRequestFulfillmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.EMPLOYEE)),
):
    """Append fulfillment timeline entry (e.g., towel delivered)."""
    request = await GuestRequestService.add_fulfillment_detail(
        db=db,
        hotel_id=hotel_id,
        request_id=request_id,
        item=data.item,
        detail_status=data.status,
        notes=data.notes,
        actor_user=current_user,
    )
    if not request:
        raise HTTPException(status_code=404, detail="Guest request not found")
    return request
