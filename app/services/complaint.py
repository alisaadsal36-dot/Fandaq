"""
Complaint service — track and manage guest complaints.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import User


class ComplaintService:

    @staticmethod
    async def create_complaint(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        text: str,
        guest_id: uuid.UUID | None = None,
    ) -> Complaint:
        """Create a new complaint."""
        complaint = Complaint(
            hotel_id=hotel_id,
            guest_id=guest_id,
            text=text,
            status=ComplaintStatus.OPEN,
        )
        db.add(complaint)
        await db.flush()
        return complaint

    @staticmethod
    async def update_status(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        complaint_id: uuid.UUID,
        status: ComplaintStatus,
        actor_user: User | None = None,
    ) -> Complaint | None:
        """Update complaint status."""
        from sqlalchemy.orm import joinedload
        stmt = select(Complaint).options(joinedload(Complaint.guest)).where(
            Complaint.id == complaint_id,
            Complaint.hotel_id == hotel_id,
        )
        result = await db.execute(stmt)
        complaint = result.scalar_one_or_none()

        if not complaint:
            return None

        previous_status = complaint.status
        complaint.status = status

        if status == ComplaintStatus.IN_PROGRESS and previous_status == ComplaintStatus.OPEN:
            if not complaint.acknowledged_at:
                complaint.acknowledged_at = datetime.utcnow()
            if actor_user and not complaint.first_response_by_user_id:
                complaint.first_response_by_user_id = actor_user.id
                complaint.first_response_by_name = actor_user.full_name

        if status == ComplaintStatus.RESOLVED:
            if not complaint.acknowledged_at:
                complaint.acknowledged_at = datetime.utcnow()
            if actor_user and not complaint.first_response_by_user_id:
                complaint.first_response_by_user_id = actor_user.id
                complaint.first_response_by_name = actor_user.full_name
            complaint.resolved_at = datetime.utcnow()
            if actor_user:
                complaint.resolved_by_user_id = actor_user.id
                complaint.resolved_by_name = actor_user.full_name
        elif status in (ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS):
            if status == ComplaintStatus.OPEN:
                complaint.acknowledged_at = None
                complaint.first_response_by_user_id = None
                complaint.first_response_by_name = None
                complaint.resolved_by_user_id = None
                complaint.resolved_by_name = None
                complaint.resolved_at = None

        await db.flush()
        return complaint

    @staticmethod
    async def assign_complaint(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        complaint_id: uuid.UUID,
        assigned_to_user: User,
    ) -> Complaint | None:
        """Assign complaint to a resolver (employee/supervisor) by hotel supervisor/admin."""
        from sqlalchemy.orm import joinedload

        stmt = select(Complaint).options(joinedload(Complaint.guest)).where(
            Complaint.id == complaint_id,
            Complaint.hotel_id == hotel_id,
        )
        complaint = (await db.execute(stmt)).scalar_one_or_none()
        if not complaint:
            return None

        complaint.assigned_to_user_id = assigned_to_user.id
        complaint.assigned_to_name = assigned_to_user.full_name
        complaint.assigned_at = datetime.utcnow()

        if complaint.status == ComplaintStatus.OPEN:
            complaint.status = ComplaintStatus.IN_PROGRESS
            if not complaint.acknowledged_at:
                complaint.acknowledged_at = datetime.utcnow()

        await db.flush()
        return complaint

    @staticmethod
    async def list_complaints(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        status: ComplaintStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """List complaints with optional status filter."""
        from sqlalchemy.orm import joinedload
        from app.models.reservation import Reservation, ReservationStatus
        from app.models.room import Room
        
        stmt = select(Complaint).options(joinedload(Complaint.guest)).where(Complaint.hotel_id == hotel_id)
        count_stmt = select(func.count(Complaint.id)).where(Complaint.hotel_id == hotel_id)

        if status:
            stmt = stmt.where(Complaint.status == status)
            count_stmt = count_stmt.where(Complaint.status == status)

        stmt = stmt.order_by(Complaint.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(stmt)
        complaints = result.scalars().all()

        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        # Enrich with guest name, phone, and active room number
        enriched_complaints = []
        for c in complaints:
            # Set transient fields
            c.guest_name = c.guest.name if c.guest else None
            c.guest_phone = c.guest.phone if c.guest else None
            c.room_number = None
            
            if c.guest:
                # Find an active reservation for this guest
                res_stmt = select(Room.room_number).join(Reservation, Reservation.room_id == Room.id).where(
                    Reservation.guest_id == c.guest_id,
                    Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN])
                ).order_by(Reservation.created_at.desc()).limit(1)
                
                res_result = await db.execute(res_stmt)
                room_num = res_result.scalar_one_or_none()
                if room_num:
                    c.room_number = room_num
                    
            enriched_complaints.append(c)

        return {"complaints": enriched_complaints, "total": total}

