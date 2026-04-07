"""
Intent dispatcher — routes AI-extracted intents to the correct service.
"""

import logging
import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.services.availability import AvailabilityService
from app.services.reservation import ReservationService
from app.services.report import ReportService
from app.services.guest_request import GuestRequestService
from app.services.complaint import ComplaintService

logger = logging.getLogger(__name__)


async def dispatch_intent(
    db: AsyncSession,
    hotel_id: uuid.UUID,
    intent: str,
    data: dict,
    sender_phone: str,
    is_owner: bool = False,
    guest_id: uuid.UUID | None = None,
) -> dict:
    """
    Route an intent to the correct service and return the result.

    Returns:
        dict with 'response' (text to send back) and optionally 'notify_owner' flag.
    """
    try:
        if intent == "check_availability":
            return await _handle_check_availability(db, hotel_id, data)

        elif intent == "create_reservation":
            return await _handle_create_reservation(
                db, hotel_id, data, sender_phone
            )

        elif intent == "cancel_reservation":
            return await _handle_cancel_reservation(db, hotel_id, data)

        elif intent == "approve_reservation" and is_owner:
            return await _handle_approve_reservation(db, hotel_id, data, sender_phone)

        elif intent == "reject_reservation" and is_owner:
            return await _handle_reject_reservation(db, hotel_id, data, sender_phone)

        elif intent == "get_report" and is_owner:
            return await _handle_get_report(db, hotel_id, data)

        elif intent == "guest_request":
            return await _handle_guest_request(db, hotel_id, data, guest_id)

        elif intent == "complaint":
            return await _handle_complaint(db, hotel_id, data, guest_id)

        elif intent == "submit_review":
            return await _handle_submit_review(db, hotel_id, data, sender_phone)

        elif intent == "update_profile":
            return await _handle_update_profile(db, hotel_id, data, sender_phone)

        elif intent == "greeting":
            # Check if session has a selected hotel
            return await _handle_greeting_multi_hotel(db, hotel_id, sender_phone)

        elif intent == "hotel_selection":
            # User picked a hotel number from list
            return await _handle_hotel_selection(db, hotel_id, data, sender_phone)

        elif intent == "unknown":
            return {
                "response": "المعذرة طال عمرك، ما فهمت طلبك زين. ياليت تعيد أو تتواصل مع إدارة الفندق مباشرة.",
            }

        else:
            # Owner-only intent sent by non-owner
            if intent in ("approve_reservation", "reject_reservation", "get_report"):
                return {
                    "response": "عذراً، هالخدمة متاحة لمدير الفندق بس.",
                }
            return {
                "response": "العذر والسموحة، ما قدرت انفذ طلبك.",
            }

    except Exception as e:
        logger.error(f"Dispatch error for intent '{intent}': {e}", exc_info=True)
        return {
            "response": "عذراً واجهتنا مشكلة فنية بسيطة، ياليت تحاول مرة ثانية.",
        }


# ── Intent Handlers ──────────────────────────────────────────

async def _handle_check_availability(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict
) -> dict:
    room_type = data.get("room_type", "")
    check_in = _parse_date(data.get("check_in", ""))
    check_out = _parse_date(data.get("check_out", ""))

    availability = await AvailabilityService.check(
        db, hotel_id,
        room_type_name=room_type or None,
        check_in=check_in,
        check_out=check_out,
    )

    if not availability:
        return {"response": "المعذرة طال عمرك، مالقينا غرف من هالنوع بالفندق الحين."}

    rt_map = {
        "one-bedroom": "غرفة وصالة",
        "two-bedroom": "غرفتين وصالة",
        "three-bedroom": "ثلاث غرف وصالة"
    }

    lines = ["📋 *الغرف المتوفرة وأسعارها:*\n"]
    for item in availability:
        room_ar = rt_map.get(item['room_type'], item['room_type'])
        price = int(float(item['daily_rate']))
        lines.append(f"🏨 *{room_ar}*: {price} ريال / الليلة")

    if check_in:
        date_str = _format_arabic_date_range(check_in, check_out) if check_out else f"من {check_in}"
        lines.append(f"\n📅 {date_str}")

    return {"response": "\n".join(lines)}


async def _handle_create_reservation(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, sender_phone: str
) -> dict:
    room_type = data.get("room_type", "")
    check_in = _parse_date(data.get("check_in", ""))
    check_out = _parse_date(data.get("check_out", ""))
    guest_name = data.get("guest_name", "")
    nationality = (data.get("nationality") or "").strip()
    id_number = (data.get("id_number") or "").strip()
    phone = data.get("phone", "") or sender_phone

    logger.info(f"[CREATE_RESERVATION] raw data from AI: {data}")
    logger.info(f"[CREATE_RESERVATION] parsed: room_type='{room_type}', check_in={check_in}, check_out={check_out}")

    if not room_type or not check_in or not check_out or not guest_name:
        missing = []
        if not room_type: missing.append("نوع الغرفة")
        if not check_in: missing.append("تاريخ الدخول")
        if not check_out: missing.append("تاريخ الخروج")
        if not guest_name: missing.append("اسمك الكريم")
        return {
            "response": f"عشان أسجل حجزك، نحتاج الله يعافيك: {'، '.join(missing)}. "
                        "ياليت تزودني بهالبيانات.",
        }

    if check_in and check_out and check_out <= check_in:
        return {"response": "❌ تاريخ الخروج لازم يكون بعد تاريخ الدخول"}

    result = await ReservationService.create_reservation(
        db, hotel_id,
        room_type_name=room_type,
        check_in=check_in,
        check_out=check_out,
        guest_name=guest_name,
        phone=phone,
        nationality=nationality,
        id_number=id_number,
    )

    if result["success"]:
        short_id = f"#{str(result['reservation_id'])[:6].upper()}"
        d_in = _parse_date(result['check_in'])
        d_out = _parse_date(result['check_out'])
        
        rt_map = {
            "one-bedroom": "غرفة وصالة",
            "two-bedroom": "غرفتين وصالة",
            "three-bedroom": "ثلاث غرف وصالة"
        }
        room_ar = rt_map.get(result['room_type'], result['room_type'])
        room_val = f"{room_ar} (رقم {result['room_number']})" if result.get('room_number') else room_ar
        
        date_str = _format_arabic_date_range(d_in, d_out)
        
        response = (
            f"✅ تم تسجيل طلب الحجز بنجاح!\n\n"
            f"📋 رقم الطلب: {short_id}\n"
            f"🏨 الغرفة: {room_val}\n"
            f"📅 {date_str}\n"
            f"💰 الإجمالي: {int(float(result['total_price']))} ريال\n\n"
            f"⏳ حالة الطلب: بانتظار موافقة الإدارة"
        )
        
        # Notify owner
        guest_label = f"{guest_name} ({nationality})" if nationality else guest_name
        owner_msg = (
            f"✅ *طلب حجز جديد*\n\n"
            f"👤 الضيف: {guest_label}\n"
            f"📱 الجوال: {phone}\n"
            f"🏨 الغرفة: {room_val}\n"
            f"📅 {date_str}\n"
            f"💰 الإجمالي: {int(float(result['total_price']))} ريال\n\n"
            f"📋 رقم الطلب: {short_id}\n"
            f"✍️ للرد:\n"
            f"موافق {short_id}\n"
            f"أو رفض {short_id}"
        )
        return {
            "response": response,
            "notify_owner": True,
            "owner_message": owner_msg,
            "reservation_id": result["reservation_id"],
        }
    else:
        return {"response": f"❌ {result['message']}"}


async def _handle_cancel_reservation(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict
) -> dict:
    reservation_id = data.get("reservation_id", "")
    if not reservation_id:
        return {"response": "ياليت تزودني برقم الحجز عشان نلغيه."}

    try:
        res_uuid = uuid.UUID(reservation_id)
    except ValueError:
        return {"response": "رقم الحجز اللي أرسلته غير صحيح."}

    result = await ReservationService.cancel_reservation(db, hotel_id, res_uuid)
    if result["success"]:
        return {"response": f"✅ أبشر، تم إلغاء حجزك بنجاح. نتمنى نشوفك قريب!"}
    else:
        return {"response": f"❌ {result['message']}"}


async def _handle_approve_reservation(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, sender_phone: str
) -> dict:
    reservation_id = str(data.get("reservation_id", "")).replace("#", "").strip()
    res_uuid = None

    if not reservation_id:
        pending_list = await ReservationService.get_pending(db, hotel_id)
        if not pending_list:
            return {"response": "طال عمرك، ما لقيت أي حجز بانتظار الموافقة حالياً."}
        
        if len(pending_list) > 1:
            return {"response": _build_multiple_pending_msg(pending_list)}
        
        # Only one pending
        latest_pending = pending_list[0]
        res_uuid = latest_pending.id
    else:
        try:
            res_uuid = uuid.UUID(reservation_id)
        except ValueError:
            pending_list = await ReservationService.get_pending(db, hotel_id)
            
            # Prevent 1-based index usage to avoid race conditions
            if reservation_id.isdigit():
                return {"response": "عذراً، لمنع تداخل الطلبات يجب كتابة كود الحجز مباشرة (مثلاً: موافق D47BCB) ولا يمكن استخدام الأرقام الترتيبية."}
            else:
                # Match by string prefix across ALL reservations to give better error messages
                from sqlalchemy import select, cast, String
                from app.models.reservation import Reservation
                
                stmt = select(Reservation).where(
                    Reservation.hotel_id == hotel_id,
                    cast(Reservation.id, String).ilike(f"{reservation_id}%")
                )
                all_matched = (await db.execute(stmt)).scalars().all()
                
                if not all_matched:
                    return {"response": "❌ رقم الحجز غير صحيح"}
                elif len(all_matched) > 1:
                    return {"response": "عفواً، الرقم القصير هذا ينطبق على أكثر من حجز، ياليت تزودني برقم أطول شوية."}
                else:
                    res_obj = all_matched[0]
                    if res_obj.status.value == "confirmed":
                        return {"response": f"👍 تم اعتماد هذا الحجز والموافقة عليه مسبقاً."}
                    elif res_obj.status.value == "rejected":
                        return {"response": f"🚫 هذا الحجز تم إيقافه ورفضه مسبقاً."}
                    elif res_obj.status.value != "pending":
                        return {"response": f"⚠️ الحجز هذا حالته الحالية: {res_obj.status.value} ولا يمكن الموافقة عليه الآن."}
                    
                    res_uuid = res_obj.id

    result = await ReservationService.confirm_reservation(db, hotel_id, res_uuid)
    if result["success"]:
        # Log to Audit
        db.add(AuditLog(
            hotel_id=hotel_id, actor_phone=sender_phone,
            action="APPROVE_RESERVATION", target_id=str(res_uuid),
        ))
        return {
            "response": f"✅ تم تأكيد الحجز للمقصد!",
            "notify_guest": True,
            "guest_message": "🎉 أبشرك! تم تأكيد حجزك، وبانتظار تشريفك لنا قريباً.",
            "reservation_id": result["reservation_id"],
        }
    else:
        return {"response": f"❌ {result['message']}"}


async def _handle_reject_reservation(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, sender_phone: str
) -> dict:
    reservation_id = str(data.get("reservation_id", "")).replace("#", "").strip()
    res_uuid = None

    if not reservation_id:
        pending_list = await ReservationService.get_pending(db, hotel_id)
        if not pending_list:
            return {"response": "طال عمرك، ما لقيت أي حجز بانتظار الرفض حالياً."}
        
        if len(pending_list) > 1:
            return {"response": _build_multiple_pending_msg(pending_list)}
        
        # Only one pending
        latest_pending = pending_list[0]
        res_uuid = latest_pending.id
    else:
        try:
            res_uuid = uuid.UUID(reservation_id)
        except ValueError:
            pending_list = await ReservationService.get_pending(db, hotel_id)
            
            # Prevent 1-based index usage
            if reservation_id.isdigit():
                return {"response": "عذراً، لمنع تداخل الطلبات يجب كتابة كود الحجز مباشرة (مثلاً: رفض D47BCB) ولا يمكن استخدام الأرقام الترتيبية."}
            else:
                from sqlalchemy import select, cast, String
                from app.models.reservation import Reservation
                
                stmt = select(Reservation).where(
                    Reservation.hotel_id == hotel_id,
                    cast(Reservation.id, String).ilike(f"{reservation_id}%")
                )
                all_matched = (await db.execute(stmt)).scalars().all()
                
                if not all_matched:
                    return {"response": "❌ رقم الحجز غير صحيح"}
                elif len(all_matched) > 1:
                    return {"response": "عفواً، الرقم القصير هذا ينطبق على أكثر من حجز، ياليت تزودني برقم أطول شوية."}
                else:
                    res_obj = all_matched[0]
                    if res_obj.status.value == "rejected":
                        return {"response": f"👍 تم رفض هذا الحجز مسبقاً."}
                    elif res_obj.status.value == "confirmed":
                        return {"response": f"🚫 هذا الحجز تمت الموافقة عليه مسبقاً ولا يمكن رفضه الآن."}
                    elif res_obj.status.value != "pending":
                        return {"response": f"⚠️ الحجز هذا حالته الحالية: {res_obj.status.value} ولا يمكن رفضه الآن."}
                    
                    res_uuid = res_obj.id

    result = await ReservationService.reject_reservation(db, hotel_id, res_uuid)
    if result["success"]:
        # Log to Audit
        db.add(AuditLog(
            hotel_id=hotel_id, actor_phone=sender_phone,
            action="REJECT_RESERVATION", target_id=str(res_uuid),
        ))
        return {
            "response": f"✅ تم رفض الحجز بنجاح.",
            "notify_guest": True,
            "guest_message": "😔 العذر والسموحة، ما قدرنا نعتمد حجزك هالمرة لظروف معينة. تواصل معنا لأي خيارات ثانية.",
            "reservation_id": result["reservation_id"],
        }
    else:
        return {"response": f"❌ {result['message']}"}


async def _handle_unknown(db: AsyncSession, hotel_id: uuid.UUID, data: dict) -> dict:
    return {
        "response": "🤖 لم أفهم طلبك بشكل واضح\nممكن توضح أكثر؟ 🙏"
    }


async def _handle_get_report(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict
) -> dict:
    report_type = data.get("type", "daily")
    if report_type not in ("daily", "weekly", "monthly"):
        report_type = "daily"

    report_name_ar = {"daily": "يومي", "weekly": "أسبوعي", "monthly": "شهري"}.get(report_type)

    report = await ReportService.generate_report(db, hotel_id, report_type)
    d = report["data"]

    return {
        "response": (
            f"📊 *تقرير {report_name_ar} لحالتك المالية*\n"
            f"📅 {report['period_start']} → {report['period_end']}\n\n"
            f"💰 الدخل: {d['total_income']} ريال\n"
            f"📈 صافي الإيراد: {d['net_profit']} ريال\n"
            f"🏨 إجمالي الحجوزات: {d['reservations_count']}\n"
            f"📊 نسبة الإشغال: {d['occupancy_rate']}%"
        ),
    }


async def _handle_guest_request(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, guest_id: uuid.UUID | None
) -> dict:
    request_type = data.get("request_type", "")
    if not request_type:
        return {"response": "وش اللي محتاجه أقدر أخدمك فيه؟"}

    request = await GuestRequestService.create_request(
        db, hotel_id,
        request_type=request_type,
        guest_id=guest_id,
    )
    return {
        "response": f"✅ أبشر، سجلنا طلبك لـ *{request.request_type}*. "
                    f"ثواني والفريق بيتواصل معك.",
        "notify_owner": True,
        "owner_message": f"🔔 *طلب نزيل جديد*: {request.request_type}",
    }


async def _handle_complaint(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, guest_id: uuid.UUID | None
) -> dict:
    text = data.get("text", "")
    if not text:
        return {"response": "ياليت تكتب لي الشكوى أو الملاحظة اللي مزعلتك."}

    complaint = await ComplaintService.create_complaint(
        db, hotel_id, text=text, guest_id=guest_id
    )
    
    # Check for recurring complaints
    owner_message = f"⚠️ *شكوى جديدة*: {complaint.text}"
    try:
        from app.models.complaint import Complaint, ComplaintStatus
        from sqlalchemy import select
        from app.ai.extractor import detect_recurring_complaints
        
        # Get recent 5 complaints
        stmt = select(Complaint).where(
            Complaint.hotel_id == hotel_id,
            Complaint.id != complaint.id
        ).order_by(Complaint.created_at.desc()).limit(5)
        
        recent_complaints = await db.execute(stmt)
        past_texts = [c.text for c in recent_complaints.scalars()]
        
        if past_texts:
            detection = await detect_recurring_complaints(complaint.text, past_texts)
            if detection.get("is_recurring"):
                issue = detection.get("issue", "نفس المشكلة")
                count = detection.get("count", 3)
                owner_message += f"\n\n🚨 *تنبيه عاجل*: لوحظ تكرار شكوى عن (_{issue}_) حوالي {count} مرات مؤخراً! يرجى الانتباه."
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Recurring complaint check failed: {e}")

    return {
        "response": "نأسف جداً لسماع هذا. رفعنا الملاحظة للإدارة "
                    "وبنتأكد من حلها بأقرب وقت لإرضائك.",
        "notify_owner": True,
        "owner_message": owner_message,
    }


# ── Helpers ──────────────────────────────────────────────────

def _parse_date(date_str: str) -> date | None:
    """Parse a date string (YYYY-MM-DD) or return None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_arabic_date_range(d_in: date, d_out: date) -> str:
    """Format Date range to polite Arabic like 'من 7 إلى 10 أبريل 2026'."""
    months = ["", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", 
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    
    m_in = months[d_in.month]
    m_out = months[d_out.month]
    
    if d_in.year == d_out.year and d_in.month == d_out.month:
        return f"من {d_in.day} إلى {d_out.day} {m_in} {d_in.year}"
    elif d_in.year == d_out.year:
        return f"من {d_in.day} {m_in} إلى {d_out.day} {m_out} {d_in.year}"
    return f"من {d_in.day} {m_in} {d_in.year} إلى {d_out.day} {m_out} {d_out.year}"


def _build_multiple_pending_msg(pending_list: list) -> str:
    """Build a formatted Arabic message listing multiple pending reservations."""
    def num_emoji(num):
        emojis = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣", 
                  "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣", "0": "0️⃣"}
        return "".join(emojis.get(c, c) for c in str(num))

    # Sort by check_in date ascending
    pending_list = sorted(pending_list, key=lambda x: x.check_in)
    
    # Limit to 3 items
    display_list = pending_list[:3]

    lines = ["🔔 يوجد أكثر من طلب حجز بانتظار الموافقة:\n"]
    for i, p in enumerate(display_list, 1):
        short_id = str(p.id)[:6].upper()
        rt_name = p.room_type.name if p.room_type else "غير محدد"
        rt_map = {"one-bedroom": "غرفة وصالة", "two-bedroom": "غرفتين وصالة", "three-bedroom": "ثلاث غرف وصالة"}
        rt_name = rt_map.get(rt_name, rt_name)
        
        highlight = " ⭐ (الأقرب)" if i == 1 else ""
        date_str = _format_arabic_date_range(p.check_in, p.check_out)
        lines.append(
            f"{num_emoji(i)}{highlight}\n"
            f"📋 كود: {short_id}\n"
            f"🏨 غرفة: {rt_name}\n"
            f"📅 {date_str}\n"
            f"💰 {int(p.total_price)} ريال\n"
        )
    
    if len(pending_list) > 3:
        lines.append("... ويوجد حجوزات أخرى\n")
    
    sample_approve = str(display_list[0].id)[:6].upper()
    sample_reject = str(display_list[1].id)[:6].upper() if len(display_list) > 1 else sample_approve
    
    lines.append(
        f"✍️ من فضلك اضغط رد واكتب:\n"
        f"موافق {sample_approve}\n"
        f"أو رفض {sample_reject}"
    )
    return "\n".join(lines)


# ── Multi-Hotel Handlers ─────────────────────────────────────

async def _handle_greeting_multi_hotel(
    db: AsyncSession, current_hotel_id: uuid.UUID, sender_phone: str
) -> dict:
    """Show hotel selection menu to the user."""
    from app.models.hotel import Hotel
    from sqlalchemy import select

    stmt = select(Hotel).where(Hotel.is_active == True).order_by(Hotel.created_at)
    result = await db.execute(stmt)
    hotels = result.scalars().all()

    if len(hotels) == 1:
        # Only one hotel, use classic welcome
        from app.whatsapp.templates import welcome_message
        return {"response": welcome_message(hotels[0].name)}

    lines = [
        "👋 يا هلا وسهلا في RAHATY لإدارة الفنادق!",
        "",
        "🏨 اختر الفندق اللي تبي تتعامل معه:",
        "",
    ]
    for i, h in enumerate(hotels, 1):
        addr = f" — {h.address}" if h.address else ""
        lines.append(f"  {i}️⃣  *{h.name}*{addr}")

    lines.append("")
    lines.append("📝 اكتب *رقم* الفندق (مثلاً: 1)")
    lines.append("أو اكتب *اسم الفندق* مباشرة")

    return {"response": "\n".join(lines)}


async def _handle_hotel_selection(
    db: AsyncSession, current_hotel_id: uuid.UUID, data: dict, sender_phone: str
) -> dict:
    """Handle when user selects a hotel from the list."""
    from app.models.hotel import Hotel
    from sqlalchemy import select

    selection = str(data.get("selection", "")).strip()

    stmt = select(Hotel).where(Hotel.is_active == True).order_by(Hotel.created_at)
    result = await db.execute(stmt)
    hotels = result.scalars().all()

    selected_hotel = None

    # Try numeric selection first
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(hotels):
            selected_hotel = hotels[idx]
    except (ValueError, TypeError):
        pass

    # Try name match
    if not selected_hotel:
        for h in hotels:
            if selection.lower() in h.name.lower():
                selected_hotel = h
                break

    if selected_hotel:
        from app.whatsapp.templates import welcome_message
        return {
            "response": welcome_message(selected_hotel.name),
            "switch_hotel_id": str(selected_hotel.id),
        }

    return {
        "response": "عذراً ما لقيت هالفندق. ياليت تختار الرقم الصحيح من القائمة أو تكتب 'أهلا' عشان تشوف القائمة من جديد.",
    }


async def _handle_submit_review(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, sender_phone: str
) -> dict:
    """Handle guest review submission after checkout."""
    from app.models.guest import Guest
    from app.models.review import Review
    from app.models.reservation import Reservation, ReservationStatus
    from sqlalchemy import select

    rating = data.get("rating")
    comment = data.get("comment", "")

    # Validate rating
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return {"response": "ياليت تختار رقم من 1 إلى 5 ⭐ (1 = ضعيف، 5 = ممتاز)"}
    except (TypeError, ValueError):
        return {"response": "ياليت تختار رقم من 1 إلى 5 ⭐ (1 = ضعيف، 5 = ممتاز)"}

    # Find guest by phone
    stmt = select(Guest).where(
        Guest.hotel_id == hotel_id,
        Guest.phone == sender_phone,
    )
    result = await db.execute(stmt)
    guest = result.scalar_one_or_none()

    if not guest:
        return {"response": "شكراً لاهتمامك! بس ما لقينا حسابك عندنا. تواصل مع إدارة الفندق مباشرة 🙏"}

    # Find the most recent checked_out reservation
    res_stmt = (
        select(Reservation)
        .where(
            Reservation.hotel_id == hotel_id,
            Reservation.guest_id == guest.id,
            Reservation.status == ReservationStatus.CHECKED_OUT,
        )
        .order_by(Reservation.updated_at.desc())
        .limit(1)
    )
    res_result = await db.execute(res_stmt)
    reservation = res_result.scalar_one_or_none()

    # Check if already reviewed this reservation
    if reservation:
        existing = await db.execute(
            select(Review).where(
                Review.guest_id == guest.id,
                Review.reservation_id == reservation.id,
            )
        )
        if existing.scalar_one_or_none():
            return {"response": "شكراً! سبق وسجلنا تقييمك لهذه الإقامة 😊 نتطلع نشوفك مرة ثانية!"}

    category = data.get("category", "general")

    # Generate AI suggested reply
    from app.ai.extractor import generate_review_reply
    suggested_reply = await generate_review_reply(rating, comment, category)
    now = datetime.utcnow()

    if rating >= 4:
        sentiment = "positive"
    elif rating == 3:
        sentiment = "neutral"
    else:
        sentiment = "negative"

    reply_status = "auto_sent" if sentiment == "positive" else "pending_approval"

    # Save review
    review = Review(
        hotel_id=hotel_id,
        guest_id=guest.id,
        reservation_id=reservation.id if reservation else None,
        rating=rating,
        comment=comment if comment else None,
        category=category,
        ai_reply_suggestion=suggested_reply,
        sentiment=sentiment,
        reply_status=reply_status,
        final_reply_text=suggested_reply if sentiment == "positive" else None,
        reply_generated_at=now if suggested_reply else None,
        reply_sent_at=now if sentiment == "positive" else None,
        reply_sent_channel="auto_policy" if sentiment == "positive" else None,
    )
    db.add(review)
    await db.flush()

    # Stars display
    stars = "⭐" * rating

    response_msgs = {
        5: f"واو {stars} شكراً جزيلاً! سعيدين إن تجربتك كانت ممتازة 🎉 نتطلع نشوفك مرة ثانية!",
        4: f"حلو {stars} شكراً! سعيدين إنك ارتحت عندنا 😊 إن شاء الله المرة الجاية تكون أحلى!",
        3: f"شكراً على تقييمك {stars} نقدّر رأيك وإن شاء الله نتحسن أكثر 💪",
        2: f"نعتذر إن التجربة ما كانت بالمستوى المطلوب {stars} ملاحظاتك مهمة لنا وراح نتحسن 🙏",
        1: f"نعتذر جداً {stars} رأيك مهم لنا وراح ناخذه بعين الاعتبار. نتمنى نعوضك المرة الجاية 🙏",
    }

    resp = response_msgs.get(rating, f"شكراً على تقييمك {stars}!")
    if comment:
        resp += f"\n\n📝 ملاحظتك: \"{comment}\" — تم تسجيلها وراح نتابعها."

    return {"response": resp}


async def _handle_update_profile(
    db: AsyncSession, hotel_id: uuid.UUID, data: dict, sender_phone: str
) -> dict:
    """Handle guest updating their name outside of a reservation."""
    from app.services.guest import GuestService

    name = data.get("name")
    if not name:
        return {"response": "المعذرة، ما فهمت الاسم بشكل واضح. ياليت تعطيني الاسم كامل."}

    # Find and update guest
    guest = await GuestService.find_or_create(
        db, hotel_id,
        phone=sender_phone,
        name=name,
        whatsapp_id=sender_phone,
    )

    return {"response": f"تشرفنا يا {name}! تم تحديث اسمك عندنا بالسيستم 😊"}


