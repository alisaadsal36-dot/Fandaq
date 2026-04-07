import uuid
from datetime import date, timedelta

import pytest

from app.ai.dispatcher import _handle_create_reservation


@pytest.mark.asyncio
async def test_create_reservation_allows_missing_nationality(monkeypatch):
    hotel_id = uuid.uuid4()

    async def fake_create_reservation(db, hotel_id, room_type_name, check_in, check_out, guest_name, phone, nationality, id_number):
        assert nationality == ""
        assert id_number == ""
        return {
            "success": True,
            "reservation_id": str(uuid.uuid4()),
            "room_number": "101",
            "room_type": room_type_name,
            "check_in": str(check_in),
            "check_out": str(check_out),
            "total_price": 450,
            "guest_name": guest_name,
            "status": "pending",
        }

    monkeypatch.setattr(
        "app.ai.dispatcher.ReservationService.create_reservation",
        fake_create_reservation,
    )

    tomorrow = date.today() + timedelta(days=1)
    checkout = tomorrow + timedelta(days=2)
    data = {
        "room_type": "one-bedroom",
        "check_in": tomorrow.isoformat(),
        "check_out": checkout.isoformat(),
        "guest_name": "Ahmed",
    }

    result = await _handle_create_reservation(
        db=None,
        hotel_id=hotel_id,
        data=data,
        sender_phone="+966500000000",
    )

    assert "تم تسجيل طلب الحجز بنجاح" in result["response"]
    assert result.get("notify_owner") is True
    assert "👤 الضيف: Ahmed\n" in result["owner_message"]


@pytest.mark.asyncio
async def test_create_reservation_requires_core_four_fields():
    hotel_id = uuid.uuid4()

    data = {
        "room_type": "",
        "check_in": "",
        "check_out": "",
        "guest_name": "",
        "nationality": "Saudi",
    }

    result = await _handle_create_reservation(
        db=None,
        hotel_id=hotel_id,
        data=data,
        sender_phone="+966500000000",
    )

    assert "نوع الغرفة" in result["response"]
    assert "تاريخ الدخول" in result["response"]
    assert "تاريخ الخروج" in result["response"]
    assert "اسمك الكريم" in result["response"]
    assert "جنسيتك" not in result["response"]
