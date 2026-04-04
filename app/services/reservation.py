"""
Reservation service — booking workflow with owner approval.
"""

import uuid
from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.reservation import Reservation, ReservationStatus
from app.models.room_type import RoomType
from app.services.availability import AvailabilityService
from app.services.guest import GuestService
from app.utils.pricing import calculate_price


class ReservationService:

    @staticmethod
    async def create_reservation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        room_type_name: str,
        check_in: date,
        check_out: date,
        guest_name: str = "",
        phone: str = "",
        whatsapp_id: str | None = None,
        notes: str | None = None,
        nationality: str = "",
        id_number: str = "",
        total_price: float | None = None,
        status: ReservationStatus | None = None,
    ) -> dict:
        """
        Create a new reservation (status=PENDING, requires owner approval).

        Returns a dict with reservation details and a status message.
        """
        # 1. Find best room type by capacity category
        stmt = select(RoomType).where(RoomType.hotel_id == hotel_id)
        result = await db.execute(stmt)
        all_types = result.scalars().all()

        if not all_types:
            return {
                "success": False,
                "message": "عذراً، الغرف مش متاحة حالياً، لكنها هتتوفر قريباً إن شاء الله.",
            }

        # 1. Direct Room Type Name Lookup matches perfectly thanks to Dynamic AI!
        matched_rt = next((rt for rt in all_types if rt.name == room_type_name), None)
        
        candidates = [matched_rt] if matched_rt else all_types

        # 2. Check availability across candidates
        available_room = None
        room_type = None
        for candidate in candidates:
            available_room = await AvailabilityService.find_available_room(
                db, hotel_id, candidate.id, check_in, check_out
            )
            if available_room:
                room_type = candidate
                break

        # 2b. Fallback: if no individual Room records exist, use total_units count
        if not available_room:
            for candidate in candidates:
                # Count overlapping reservations for this room type
                overlap_stmt = select(func.count(Reservation.id)).where(
                    Reservation.hotel_id == hotel_id,
                    Reservation.room_type_id == candidate.id,
                    Reservation.status.in_([
                        ReservationStatus.PENDING,
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.CHECKED_IN,
                    ]),
                    Reservation.check_in < check_out,
                    Reservation.check_out > check_in,
                )
                overlap_result = await db.execute(overlap_stmt)
                reserved_count = overlap_result.scalar() or 0

                if reserved_count < candidate.total_units:
                    room_type = candidate
                    break  # Found availability via unit count

        if not room_type:
            room_type = candidates[0]
            return {
                "success": False,
                "message": f"عذراً، الغرف من فئة '{room_type.name}' غير متاحة في الفتره دي، لكنها هتتوفر قريباً إن شاء الله.",
            }

        # 3. Find or create guest
        guest = await GuestService.find_or_create(
            db, hotel_id, phone=phone, name=guest_name, whatsapp_id=whatsapp_id,
            nationality=nationality, id_number=id_number,
        )

        # 4. Calculate price or use override
        final_price = total_price if total_price is not None else calculate_price(
            check_in, check_out,
            float(room_type.daily_rate),
            float(room_type.monthly_rate),
        )

        # 5. Create reservation
        reservation = Reservation(
            hotel_id=hotel_id,
            room_id=available_room.id if available_room else None,
            room_type_id=room_type.id,
            guest_id=guest.id,
            check_in=check_in,
            check_out=check_out,
            status=status or ReservationStatus.PENDING,
            total_price=final_price,
            notes=notes,
        )
        db.add(reservation)
        await db.flush()

        return {
            "success": True,
            "message": "Reservation created and pending owner approval.",
            "reservation_id": str(reservation.id),
            "room_number": available_room.room_number if available_room else None,
            "room_type": room_type.name,
            "check_in": str(check_in),
            "check_out": str(check_out),
            "total_price": float(final_price),
            "guest_name": guest.name,
            "status": reservation.status.value,
        }

    @staticmethod
    async def confirm_reservation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> dict:
        """Owner confirms a pending reservation."""
        reservation = await _get_reservation(db, hotel_id, reservation_id)
        if not reservation:
            return {"success": False, "message": "Reservation not found."}

        if reservation.status != ReservationStatus.PENDING:
            return {
                "success": False,
                "message": f"Cannot confirm reservation with status '{reservation.status.value}'.",
            }

        reservation.status = ReservationStatus.CONFIRMED
        await db.flush()

        return {
            "success": True,
            "message": "Reservation confirmed.",
            "reservation_id": str(reservation.id),
            "status": reservation.status.value,
        }

    @staticmethod
    async def reject_reservation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> dict:
        """Owner rejects a pending reservation."""
        reservation = await _get_reservation(db, hotel_id, reservation_id)
        if not reservation:
            return {"success": False, "message": "Reservation not found."}

        if reservation.status != ReservationStatus.PENDING:
            return {
                "success": False,
                "message": f"Cannot reject reservation with status '{reservation.status.value}'.",
            }

        reservation.status = ReservationStatus.REJECTED
        await db.flush()

        return {
            "success": True,
            "message": "Reservation rejected.",
            "reservation_id": str(reservation.id),
            "status": reservation.status.value,
        }

    @staticmethod
    async def cancel_reservation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> dict:
        """Cancel a reservation (by guest or owner)."""
        reservation = await _get_reservation(db, hotel_id, reservation_id)
        if not reservation:
            return {"success": False, "message": "Reservation not found."}

        if reservation.status in (
            ReservationStatus.CHECKED_OUT,
            ReservationStatus.CANCELLED,
            ReservationStatus.REJECTED,
        ):
            return {
                "success": False,
                "message": f"Cannot cancel reservation with status '{reservation.status.value}'.",
            }

        reservation.status = ReservationStatus.CANCELLED
        await db.flush()

        return {
            "success": True,
            "message": "Reservation cancelled.",
            "reservation_id": str(reservation.id),
            "status": reservation.status.value,
        }

    @staticmethod
    async def checkin_reservation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> dict:
        """Dashboard registers physical check-in and occupies room."""
        reservation = await _get_reservation(db, hotel_id, reservation_id)
        if not reservation:
            return {"success": False, "message": "Reservation not found."}

        if reservation.status != ReservationStatus.CONFIRMED:
            return {
                "success": False,
                "message": f"Cannot check in from status '{reservation.status.value}'. Must be 'confirmed'.",
            }

        reservation.status = ReservationStatus.CHECKED_IN
        if reservation.room:
            # Import RoomStatus locally to avoid circular dependencies if any
            from app.models.room import RoomStatus
            reservation.room.status = RoomStatus.OCCUPIED

        await db.flush()

        return {
            "success": True,
            "message": "Reservation checked in successfully.",
            "reservation_id": str(reservation.id),
            "status": reservation.status.value,
        }

    @staticmethod
    async def checkout_reservation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        reservation_id: uuid.UUID,
    ) -> dict:
        """Dashboard registers physical check-out and frees room."""
        reservation = await _get_reservation(db, hotel_id, reservation_id)
        if not reservation:
            return {"success": False, "message": "Reservation not found."}

        if reservation.status != ReservationStatus.CHECKED_IN:
            return {
                "success": False,
                "message": f"Cannot check out from status '{reservation.status.value}'. Must be 'checked_in'.",
            }

        reservation.status = ReservationStatus.CHECKED_OUT
        if reservation.room:
            from app.models.room import RoomStatus
            reservation.room.status = RoomStatus.AVAILABLE

        await db.flush()

        return {
            "success": True,
            "message": "Reservation checked out successfully.",
            "reservation_id": str(reservation.id),
            "status": reservation.status.value,
        }

    @staticmethod
    async def list_reservations(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        status: ReservationStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """List reservations with optional status filter."""
        from sqlalchemy.orm import selectinload
        stmt = select(Reservation).where(Reservation.hotel_id == hotel_id).options(
            selectinload(Reservation.room),
            selectinload(Reservation.guest),
            selectinload(Reservation.room_type)
        )
        count_stmt = select(func.count(Reservation.id)).where(
            Reservation.hotel_id == hotel_id
        )

        if status:
            stmt = stmt.where(Reservation.status == status)
            count_stmt = count_stmt.where(Reservation.status == status)

        stmt = stmt.order_by(Reservation.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(stmt)
        reservations = result.scalars().all()

        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        output = []
        for r in reservations:
            output.append({
                "id": str(r.id),
                "hotel_id": str(r.hotel_id),
                "room_type_id": str(r.room_type_id),
                "room_id": str(r.room_id) if r.room_id else None,
                "guest_name": r.guest.name if hasattr(r, 'guest') and r.guest else "غير محدد",
                "guest_phone": r.guest.phone if hasattr(r, 'guest') and r.guest else "غير متوفر",
                "guest_nationality": r.guest.nationality if hasattr(r, 'guest') and r.guest else "غير محدد",
                "guest_id_number": r.guest.id_number if hasattr(r, 'guest') and r.guest else "غير مسجل",
                "room_number": r.room.room_number if hasattr(r, 'room') and r.room else "غير محدد",
                "check_in": str(r.check_in),
                "check_out": str(r.check_out),
                "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
                "total_price": float(r.total_price) if r.total_price else 0.0,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None
            })

        return {
            "reservations": output,
            "total": total,
        }

    @staticmethod
    async def get_pending(
        db: AsyncSession,
        hotel_id: uuid.UUID,
    ) -> list[Reservation]:
        """Get all pending reservations for owner approval."""
        stmt = select(Reservation).where(
            Reservation.hotel_id == hotel_id,
            Reservation.status == ReservationStatus.PENDING,
        ).options(
            selectinload(Reservation.room_type)
        ).order_by(Reservation.created_at.asc())

        result = await db.execute(stmt)
        return list(result.scalars().all())


async def _get_reservation(
    db: AsyncSession,
    hotel_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> Reservation | None:
    """Helper to get a reservation scoped by hotel."""
    from sqlalchemy.orm import selectinload

    stmt = select(Reservation).where(
        Reservation.id == reservation_id,
        Reservation.hotel_id == hotel_id,
    ).options(selectinload(Reservation.room))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
