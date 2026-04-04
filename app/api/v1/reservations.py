"""
Reservations API — list, confirm, reject, cancel reservations.
"""

import uuid
import asyncio
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.reservation import ReservationStatus
from app.schemas.reservation import (
    ReservationCreate, ReservationResponse,
    ReservationActionResponse, ReservationListResponse, ReservationDetailResponse,
)
from app.services.reservation import ReservationService
from app.services.availability import AvailabilityService
from app.schemas.room import AvailabilityResponse

router = APIRouter()


# ── Availability ─────────────────────────────────────

@router.get(
    "/hotels/{hotel_id}/availability",
    response_model=list[AvailabilityResponse],
)
async def check_availability(
    hotel_id: uuid.UUID,
    room_type: str | None = None,
    check_in: date | None = None,
    check_out: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Check room availability for a hotel."""
    results = await AvailabilityService.check(
        db, hotel_id,
        room_type_name=room_type,
        check_in=check_in,
        check_out=check_out,
    )
    return results


# ── Reservations ─────────────────────────────────────

@router.post(
    "/hotels/{hotel_id}/reservations",
    response_model=dict,
    status_code=201,
)
async def create_reservation(
    hotel_id: uuid.UUID,
    data: ReservationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a reservation (status=pending)."""
    result = await ReservationService.create_reservation(
        db, hotel_id,
        room_type_name=data.room_type,
        check_in=data.check_in,
        check_out=data.check_out,
        guest_name=data.guest_name,
        phone=data.phone,
        notes=data.notes,
        total_price=data.total_price,
        status=data.status,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/hotels/{hotel_id}/reservations")
async def list_reservations(
    hotel_id: uuid.UUID,
    status: ReservationStatus | None = None,
    skip: int = 0,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List reservations with optional status filter."""
    result = await ReservationService.list_reservations(
        db, hotel_id, status=status, skip=skip, limit=limit
    )
    return result


@router.get("/hotels/{hotel_id}/reservations/pending")
async def list_pending_reservations(
    hotel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all pending reservations awaiting owner approval."""
    reservations = await ReservationService.get_pending(db, hotel_id)
    return {"reservations": reservations, "total": len(reservations)}


@router.post(
    "/hotels/{hotel_id}/reservations/{reservation_id}/confirm",
    response_model=dict,
)
async def confirm_reservation(
    hotel_id: uuid.UUID,
    reservation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Confirm a pending reservation (owner action)."""
    result = await ReservationService.confirm_reservation(db, hotel_id, reservation_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    # Send WhatsApp notification to guest in background (don't block response)
    asyncio.create_task(_send_confirm_notification(hotel_id, reservation_id))

    return result


async def _send_confirm_notification(hotel_id, reservation_id):
    """Background: notify guest their reservation was confirmed."""
    try:
        from app.database import async_session_factory
        from app.models.reservation import Reservation
        from app.models.guest import Guest
        from app.models.hotel import Hotel
        from app.whatsapp.client import whatsapp_client
        from app.services.whatsapp_session import WhatsAppSessionService
        from sqlalchemy import select
        
        async with async_session_factory() as db:
            stmt = (
                select(Guest.phone, Hotel.whatsapp_phone_number_id, Hotel.whatsapp_api_token, Hotel.telegram_bot_token)
                .join(Reservation, Reservation.guest_id == Guest.id)
                .join(Hotel, Hotel.id == Reservation.hotel_id)
                .where(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            )
            res_db = await db.execute(stmt)
            row = res_db.first()
            if row:
                guest_phone, phone_number_id, wa_token, tg_token = row
                if guest_phone and (phone_number_id or tg_token):
                    message = "🎉 أبشرك! تم تأكيد حجزك من قبل الإدارة، وبانتظار تشريفك لنا قريباً."
                    if guest_phone.startswith("tg_") or (guest_phone.isdigit() and len(guest_phone) <= 10):
                        from app.config import get_settings
                        settings = get_settings()
                        await whatsapp_client.send_telegram_message(
                            bot_token=tg_token or settings.TELEGRAM_BOT_TOKEN,
                            chat_id=guest_phone,
                            message=message
                        )
                    else:
                        await whatsapp_client.send_text_message(
                            phone_number_id=phone_number_id,
                            to=guest_phone,
                            message=message,
                            api_token=wa_token,
                        )
                    # Save notification to history so AI has context
                    session = await WhatsAppSessionService.get_or_create_session(db, hotel_id, guest_phone)
                    await WhatsAppSessionService.append_to_history(db, session.id, role="assistant", content=message)
                    await db.commit()
    except Exception as e:
        import logging
        logging.error(f"Failed to send confirm notification: {e}")


@router.post(
    "/hotels/{hotel_id}/reservations/{reservation_id}/reject",
    response_model=dict,
)
async def reject_reservation(
    hotel_id: uuid.UUID,
    reservation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending reservation (owner action)."""
    result = await ReservationService.reject_reservation(db, hotel_id, reservation_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    # Send WhatsApp notification to guest in background
    asyncio.create_task(_send_reject_notification(hotel_id, reservation_id))

    return result


async def _send_reject_notification(hotel_id, reservation_id):
    """Background: notify guest their reservation was rejected."""
    try:
        from app.database import async_session_factory
        from app.models.reservation import Reservation
        from app.models.guest import Guest
        from app.models.hotel import Hotel
        from app.whatsapp.client import whatsapp_client
        from app.services.whatsapp_session import WhatsAppSessionService
        from sqlalchemy import select
        
        async with async_session_factory() as db:
            stmt = (
                select(Guest.phone, Hotel.whatsapp_phone_number_id, Hotel.whatsapp_api_token, Hotel.telegram_bot_token)
                .join(Reservation, Reservation.guest_id == Guest.id)
                .join(Hotel, Hotel.id == Reservation.hotel_id)
                .where(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            )
            res_db = await db.execute(stmt)
            row = res_db.first()
            if row:
                guest_phone, phone_number_id, wa_token, tg_token = row
                if guest_phone and (phone_number_id or tg_token):
                    message = "😔 العذر والسموحة، ما قدرنا نعتمد حجزك هالمرة لظروف معينة. تواصل معنا لأي خيارات ثانية."
                    if guest_phone.startswith("tg_") or (guest_phone.isdigit() and len(guest_phone) <= 10):
                        from app.config import get_settings
                        settings = get_settings()
                        await whatsapp_client.send_telegram_message(
                            bot_token=tg_token or settings.TELEGRAM_BOT_TOKEN,
                            chat_id=guest_phone,
                            message=message
                        )
                    else:
                        await whatsapp_client.send_text_message(
                            phone_number_id=phone_number_id,
                            to=guest_phone,
                            message=message,
                            api_token=wa_token,
                        )
                    # Save notification to history so AI has context
                    session = await WhatsAppSessionService.get_or_create_session(db, hotel_id, guest_phone)
                    await WhatsAppSessionService.append_to_history(db, session.id, role="assistant", content=message)
                    await db.commit()
    except Exception as e:
        import logging
        logging.error(f"Failed to send reject notification: {e}")


@router.post(
    "/hotels/{hotel_id}/reservations/{reservation_id}/cancel",
    response_model=dict,
)
async def cancel_reservation(
    hotel_id: uuid.UUID,
    reservation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a confirmed reservation."""
    result = await ReservationService.cancel_reservation(db, hotel_id, reservation_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post(
    "/hotels/{hotel_id}/reservations/{reservation_id}/checkin",
    response_model=dict,
)
async def checkin_reservation(
    hotel_id: uuid.UUID,
    reservation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check in a confirmed reservation."""
    result = await ReservationService.checkin_reservation(db, hotel_id, reservation_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
        
    # Send welcome message in background
    asyncio.create_task(_send_checkin_welcome(hotel_id, reservation_id))
    
    return result

async def _send_checkin_welcome(hotel_id, reservation_id):
    """Background: send welcome message to guest upon check-in."""
    try:
        from app.database import async_session_factory
        from app.models.reservation import Reservation
        from app.models.guest import Guest
        from app.models.hotel import Hotel
        from app.models.room import Room
        from app.whatsapp.client import whatsapp_client
        from app.services.whatsapp_session import WhatsAppSessionService
        from sqlalchemy import select
        
        async with async_session_factory() as db:
            stmt = (
                select(Guest.phone, Guest.name, Hotel.whatsapp_phone_number_id, Hotel.name.label("hotel_name"), Hotel.whatsapp_api_token, Hotel.telegram_bot_token, Room.room_number)
                .join(Reservation, Reservation.guest_id == Guest.id)
                .join(Hotel, Hotel.id == Reservation.hotel_id)
                .outerjoin(Room, Room.id == Reservation.room_id)
                .where(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            )
            res_db = await db.execute(stmt)
            row = res_db.first()
            if row:
                guest_phone, guest_name, phone_number_id, hotel_name, wa_token, tg_token, room_number = row
                if guest_phone and (phone_number_id or tg_token):
                    room_text = f" (غرفة {room_number})" if room_number else ""
                    welcome_msg = (
                        f"أهلاً وسهلاً بك يا {guest_name or 'ضيفنا الكريم'}! 💐\n\n"
                        f"أسعدنا جداً وصولك وتواجدك معنا في *{hotel_name}*{room_text}.\n\n"
                        f"نتمنى لك إقامة سعيدة ومريحة. إذا احتجت أي شيء، طلب خدمة، أو عندك استفسار، تقدر تكلمني هنا مباشرة على مدار الساعة 🕒.\n\n"
                        f"إقامة سعيدة! 🏨✨"
                    )
                    if guest_phone.startswith("tg_") or (guest_phone.isdigit() and len(guest_phone) <= 10):
                        from app.config import get_settings
                        settings = get_settings()
                        if tg_token or settings.TELEGRAM_BOT_TOKEN:
                            await whatsapp_client.send_telegram_message(
                                bot_token=tg_token or settings.TELEGRAM_BOT_TOKEN,
                                chat_id=guest_phone,
                                message=welcome_msg
                            )
                    elif phone_number_id:
                        await whatsapp_client.send_text_message(
                            phone_number_id=phone_number_id,
                            to=guest_phone,
                            message=welcome_msg,
                            api_token=wa_token,
                        )
                    # Save welcome to history so AI has context
                    session = await WhatsAppSessionService.get_or_create_session(db, hotel_id, guest_phone)
                    await WhatsAppSessionService.append_to_history(db, session.id, role="assistant", content=welcome_msg)
                    await db.commit()
    except Exception as e:
        import logging
        logging.error(f"Failed to send checkin welcome notification: {e}")


@router.post(
    "/hotels/{hotel_id}/reservations/{reservation_id}/checkout",
    response_model=dict,
)
async def checkout_reservation(
    hotel_id: uuid.UUID,
    reservation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check out a checked-in reservation."""
    result = await ReservationService.checkout_reservation(db, hotel_id, reservation_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    # Send rating request in background
    asyncio.create_task(_send_checkout_rating(hotel_id, reservation_id))

    return result


async def _send_checkout_rating(hotel_id, reservation_id):
    """Background: send rating request to guest after checkout."""
    try:
        from app.database import async_session_factory
        from app.models.reservation import Reservation
        from app.models.guest import Guest
        from app.models.hotel import Hotel
        from app.whatsapp.client import whatsapp_client
        from sqlalchemy import select

        async with async_session_factory() as db:
            stmt = (
            select(Guest.phone, Guest.name, Hotel.whatsapp_phone_number_id, Hotel.name.label("hotel_name"), Hotel.whatsapp_api_token, Hotel.telegram_bot_token)
            .join(Reservation, Reservation.guest_id == Guest.id)
            .join(Hotel, Hotel.id == Reservation.hotel_id)
            .where(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        )
        res_db = await db.execute(stmt)
        row = res_db.first()
        if row:
            guest_phone, guest_name, phone_number_id, hotel_name, wa_token, tg_token = row
            if guest_phone and (phone_number_id or tg_token):
                rating_msg = (
                    f"شكراً لإقامتك معنا يا {guest_name or 'ضيفنا الكريم'}! 🙏✨\n\n"
                    f"نتمنى إن تجربتك في *{hotel_name}* كانت مريحة وتليق بمقامك.\n\n"
                    f"ياليت تقيّم إقامتك من 1 إلى 5 ⭐\n"
                    f"(1 = ضعيف، 5 = ممتاز)\n\n"
                    f"وإذا عندك أي ملاحظات أو اقتراحات، لا تتردد تكتبها معه 📝\n\n"
                    f"مثال: *5 كل شي كان ممتاز*\n"
                    f"أو: *3 الغرفة حلوة بس التكييف يحتاج صيانة*"
                )
                if guest_phone.startswith("tg_") or (guest_phone.isdigit() and len(guest_phone) <= 10):
                    from app.config import get_settings
                    settings = get_settings()
                    await whatsapp_client.send_telegram_message(
                        bot_token=tg_token or settings.TELEGRAM_BOT_TOKEN,
                        chat_id=guest_phone,
                        message=rating_msg
                    )
                else:
                    await whatsapp_client.send_text_message(
                        phone_number_id=phone_number_id,
                        to=guest_phone,
                        message=rating_msg,
                        api_token=wa_token,
                    )
                
                # Append to AI conversational history so the AI knows it asked for a review
                from app.services.whatsapp_session import WhatsAppSessionService
                session = await WhatsAppSessionService.get_or_create_session(db, hotel_id, guest_phone)
                await WhatsAppSessionService.append_to_history(db, session.id, role="assistant", content=rating_msg)
                
                # Set pending_rating flag so webhook can intercept rating responses
                from sqlalchemy import update as sql_update
                from app.models.whatsapp_session import WhatsAppSession
                ctx = session.context or {}
                ctx["pending_rating"] = True
                await db.execute(
                    sql_update(WhatsAppSession)
                    .where(WhatsAppSession.id == session.id)
                    .values(context=ctx)
                )
                await db.commit()
    except Exception as e:
        import logging
        logging.error(f"Failed to send checkout rating request: {e}")

