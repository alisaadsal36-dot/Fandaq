"""
Guest request service — handle service requests.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guest_request import GuestRequest, RequestStatus
from app.models.user import User


class GuestRequestService:

    @staticmethod
    async def create_request(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        request_type: str,
        guest_id: uuid.UUID | None = None,
        details: str | None = None,
    ) -> GuestRequest:
        """Create a new guest request."""
        request = GuestRequest(
            hotel_id=hotel_id,
            guest_id=guest_id,
            request_type=request_type.strip().lower(),
            details=details,
            status=RequestStatus.OPEN,
        )
        db.add(request)
        await db.flush()
        return request

    @staticmethod
    async def update_status(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        request_id: uuid.UUID,
        status: RequestStatus,
        actor_user: User | None = None,
    ) -> GuestRequest | None:
        """Update the status of a guest request."""
        stmt = select(GuestRequest).where(
            GuestRequest.id == request_id,
            GuestRequest.hotel_id == hotel_id,
        )
        result = await db.execute(stmt)
        request = result.scalar_one_or_none()

        if not request:
            return None

        previous_status = request.status
        request.status = status

        if status == RequestStatus.IN_PROGRESS and previous_status == RequestStatus.OPEN:
            if not request.acknowledged_at:
                request.acknowledged_at = datetime.utcnow()
            if actor_user and not request.first_response_by_user_id:
                request.first_response_by_user_id = actor_user.id
                request.first_response_by_name = actor_user.full_name

        if status == RequestStatus.COMPLETED:
            if not request.acknowledged_at:
                request.acknowledged_at = datetime.utcnow()
            if actor_user and not request.first_response_by_user_id:
                request.first_response_by_user_id = actor_user.id
                request.first_response_by_name = actor_user.full_name
            request.completed_at = datetime.utcnow()
            if actor_user:
                request.completed_by_user_id = actor_user.id
                request.completed_by_name = actor_user.full_name
        elif status == RequestStatus.OPEN:
            request.acknowledged_at = None
            request.first_response_by_user_id = None
            request.first_response_by_name = None
            request.completed_by_user_id = None
            request.completed_by_name = None
            request.completed_at = None

        await db.flush()
        return request

    @staticmethod
    async def assign_request(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        request_id: uuid.UUID,
        assigned_to_user: User,
    ) -> GuestRequest | None:
        """Assign request to a staff member and move to in-progress when needed."""
        stmt = select(GuestRequest).where(
            GuestRequest.id == request_id,
            GuestRequest.hotel_id == hotel_id,
        )
        request = (await db.execute(stmt)).scalar_one_or_none()
        if not request:
            return None

        request.assigned_to_user_id = assigned_to_user.id
        request.assigned_to_name = assigned_to_user.full_name
        request.assigned_at = datetime.utcnow()

        if request.status == RequestStatus.OPEN:
            request.status = RequestStatus.IN_PROGRESS
            if not request.acknowledged_at:
                request.acknowledged_at = datetime.utcnow()

        await db.flush()
        return request

    @staticmethod
    async def add_fulfillment_detail(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        request_id: uuid.UUID,
        item: str,
        detail_status: str,
        actor_user: User,
        notes: str | None = None,
    ) -> GuestRequest | None:
        """Append a fulfillment timeline item such as towel delivered."""
        stmt = select(GuestRequest).where(
            GuestRequest.id == request_id,
            GuestRequest.hotel_id == hotel_id,
        )
        request = (await db.execute(stmt)).scalar_one_or_none()
        if not request:
            return None

        timeline = list(request.fulfillment_details or [])
        timeline.append({
            "timestamp": datetime.utcnow().isoformat(),
            "item": item,
            "status": detail_status,
            "notes": notes,
            "actor_name": actor_user.full_name,
        })
        request.fulfillment_details = timeline

        statuses = [str(x.get("status", "")).lower() for x in timeline]
        if statuses and all(s == "delivered" for s in statuses):
            request.fulfillment_status = "completed"
            request.status = RequestStatus.COMPLETED
            if not request.completed_at:
                request.completed_at = datetime.utcnow()
            request.completed_by_user_id = actor_user.id
            request.completed_by_name = actor_user.full_name
        elif any(s == "failed" for s in statuses):
            request.fulfillment_status = "failed"
            if request.status == RequestStatus.OPEN:
                request.status = RequestStatus.IN_PROGRESS
        elif any(s == "delivered" for s in statuses):
            request.fulfillment_status = "partial"
            if request.status == RequestStatus.OPEN:
                request.status = RequestStatus.IN_PROGRESS
        else:
            request.fulfillment_status = "pending"

        if not request.acknowledged_at:
            request.acknowledged_at = datetime.utcnow()
        if not request.first_response_by_user_id:
            request.first_response_by_user_id = actor_user.id
            request.first_response_by_name = actor_user.full_name

        await db.flush()
        return request

    @staticmethod
    async def list_requests(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        status: RequestStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """List guest requests with optional status filter."""
        stmt = select(GuestRequest).where(GuestRequest.hotel_id == hotel_id)
        count_stmt = select(func.count(GuestRequest.id)).where(
            GuestRequest.hotel_id == hotel_id
        )

        if status:
            stmt = stmt.where(GuestRequest.status == status)
            count_stmt = count_stmt.where(GuestRequest.status == status)

        stmt = stmt.order_by(GuestRequest.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(stmt)
        requests = result.scalars().all()

        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        return {"requests": requests, "total": total}
