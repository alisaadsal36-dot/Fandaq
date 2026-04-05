"""
Background Scheduler — runs daily automated tasks:
  - Competitor price scraping (8:00 AM)
  - Pre-arrival guest reminders (6:00 PM)
  - Smart financial alerts (9:00 PM)
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.reservation import Reservation, ReservationStatus
from app.models.expense import Expense
from app.models.hotel import Hotel
from app.whatsapp.client import whatsapp_client

logger = logging.getLogger(__name__)


# ══════════════════════════════════════
#  COMPETITOR SCRAPING
# ══════════════════════════════════════

async def scrape_competitors_job():
    """Placeholder for competitor scraping — to be implemented with Playwright."""
    logger.info("🔍 Competitor scraping job triggered (placeholder).")
    # TODO: Implement Playwright-based scraping when ready


# ══════════════════════════════════════
#  PRE-ARRIVAL REMINDERS
# ══════════════════════════════════════

async def send_pre_arrival_reminders():
    """Sends WhatsApp reminders to guests checking in tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    logger.info(f"🔔 Running pre-arrival reminders for: {tomorrow}")

    async with async_session_factory() as db:
        stmt = (
            select(Reservation)
            .where(
                Reservation.check_in == tomorrow,
                Reservation.status == ReservationStatus.CONFIRMED,
            )
            .options(
                selectinload(Reservation.guest),
                selectinload(Reservation.hotel),
                selectinload(Reservation.room_type),
            )
        )
        result = await db.execute(stmt)
        reservations = result.scalars().all()

        if not reservations:
            logger.info("No reservations checking in tomorrow.")
            return

        sent_count = 0
        for res in reservations:
            guest = res.guest
            hotel = res.hotel
            room_type = res.room_type

            if not guest or not hotel or not guest.phone:
                continue

            guest_name = guest.name if guest.name and guest.name not in ("Sir", "WhatsApp User") else "ضيفنا الكريم"

            message = (
                f"مساء الخير {guest_name} 🌙\n\n"
                f"نذكّرك بأن حجزك في *{hotel.name}* غداً إن شاء الله.\n\n"
                f"📋 *تفاصيل حجزك:*\n"
                f"• نوع الغرفة: {room_type.name if room_type else 'غير محدد'}\n"
                f"• تاريخ الدخول: {res.check_in}\n"
                f"• تاريخ الخروج: {res.check_out}\n"
                f"• المبلغ: {res.total_price} ريال\n\n"
                f"⏰ وقت الدخول من الساعة 3:00 عصراً\n\n"
                f"لو تحتاج أي مساعدة، تواصل معنا هنا مباشرة.\n"
                f"بانتظارك! 🏨✨"
            )

            try:
                await whatsapp_client.send_text_message(
                    phone_number_id=hotel.whatsapp_phone_number_id,
                    to=guest.phone,
                    message=message,
                )
                sent_count += 1
                logger.info(f"✅ Reminder sent to {guest_name} ({guest.phone})")
            except Exception as e:
                logger.error(f"❌ Failed to send reminder to {guest.phone}: {e}")

        logger.info(f"🔔 Reminders complete: {sent_count}/{len(reservations)} sent.")


# ══════════════════════════════════════
#  SMART FINANCIAL ALERTS
# ══════════════════════════════════════

async def send_financial_alerts():
    """
    Compares today's expenses vs the 7-day average.
    If today's expenses exceed the average by >30%, alert the owner via WhatsApp.
    Also alerts if today's income is 0 but there were expenses.
    """
    today = date.today()
    week_ago = today - timedelta(days=7)
    logger.info(f"💰 Running financial alerts for: {today}")

    async with async_session_factory() as db:
        # Get all active hotels
        hotels_result = await db.execute(
            select(Hotel).where(Hotel.is_active == True)
        )
        hotels = hotels_result.scalars().all()

        for hotel in hotels:
            # Today's expenses
            today_exp = await db.execute(
                select(func.sum(Expense.amount)).where(
                    Expense.hotel_id == hotel.id,
                    Expense.date == today,
                )
            )
            today_expenses = float(today_exp.scalar() or 0)

            # Last 7 days average expenses (excluding today)
            avg_exp = await db.execute(
                select(func.avg(Expense.amount)).where(
                    Expense.hotel_id == hotel.id,
                    Expense.date >= week_ago,
                    Expense.date < today,
                )
            )
            avg_expenses = float(avg_exp.scalar() or 0)

            # Today's income
            today_inc = await db.execute(
                select(func.sum(Reservation.total_price)).where(
                    Reservation.hotel_id == hotel.id,
                    Reservation.status.in_([
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.CHECKED_IN,
                        ReservationStatus.CHECKED_OUT,
                    ]),
                    Reservation.check_in == today,
                )
            )
            today_income = float(today_inc.scalar() or 0)

            # Build alert messages
            alerts = []

            # Check expense spike (>30% above average)
            if avg_expenses > 0 and today_expenses > avg_expenses * 1.3:
                spike_pct = round(((today_expenses - avg_expenses) / avg_expenses) * 100)
                alerts.append(
                    f"⚠️ *تنبيه مصروفات:* مصاريف اليوم ({today_expenses} ريال) "
                    f"أعلى من المتوسط الأسبوعي ({round(avg_expenses)} ريال) بنسبة {spike_pct}%"
                )

            # Check zero income with expenses
            if today_income == 0 and today_expenses > 0:
                alerts.append(
                    f"📉 *تنبيه دخل:* لا يوجد دخل اليوم لكن تم تسجيل مصاريف بقيمة {today_expenses} ريال"
                )

            # Check high expense day (absolute threshold)
            if today_expenses > 5000:
                alerts.append(
                    f"🔴 *مصاريف مرتفعة:* تم صرف {today_expenses} ريال اليوم!"
                )

            if not alerts:
                continue

            # Send alert to owner
            summary = (
                f"📊 *تقرير مالي ذكي — {hotel.name}*\n"
                f"📅 {today}\n\n"
                + "\n\n".join(alerts)
                + f"\n\n💵 ملخص اليوم:\n"
                f"• الدخل: {today_income} ريال\n"
                f"• المصاريف: {today_expenses} ريال\n"
                f"• الصافي: {today_income - today_expenses} ريال"
            )

            try:
                await whatsapp_client.send_text_message(
                    phone_number_id=hotel.whatsapp_phone_number_id,
                    to=hotel.owner_whatsapp,
                    message=summary,
                )
                logger.info(f"⚠️ Financial alert sent to owner of {hotel.name}")
            except Exception as e:
                logger.error(f"❌ Failed to send financial alert for {hotel.name}: {e}")

    logger.info("💰 Financial alerts complete.")


# ══════════════════════════════════════
#  AUTOMATED DAILY PRICING REPORTS
# ══════════════════════════════════════

async def send_automated_daily_pricing_reports():
    """
    Sends the combined pricing + staff report daily at midnight.
    At 00:00 we send yesterday's report so the day is complete.
    """
    report_date = date.today() - timedelta(days=1)
    logger.info(f"📊 Running automated midnight reports for: {report_date}")

    async with async_session_factory() as db:
        # Get active hotels
        hotels_result = await db.execute(select(Hotel).where(Hotel.is_active == True))
        hotels = hotels_result.scalars().all()

        from app.services.report_delivery import send_combined_pricing_staff_report
        for hotel in hotels:
            try:
                result = await send_combined_pricing_staff_report(
                    db=db,
                    hotel=hotel,
                    report_date=report_date,
                    staff_days=30,
                )
                if result.get("success"):
                    logger.info("✅ Combined pricing+staff report sent for %s to %s", hotel.name, result.get("recipients", []))
                else:
                    logger.warning("⚠️ Combined report skipped for %s: %s", hotel.name, result.get("message"))
            except Exception as e:
                logger.error(f"❌ Failed combined report send for {hotel.name}: {e}")

    logger.info("📊 Pricing reports complete.")


async def poll_email_replies_job():
    """Polls for unread emails from owners to process AI commands."""
    from app.services.email_agent import EmailAgentService
    logger.info("📩 Email Agent: Polling for new owner commands...")
    await EmailAgentService.poll_and_process()


# ══════════════════════════════════════
#  SCHEDULER INIT
# ══════════════════════════════════════

def init_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrape_competitors_job, "cron", hour=8, minute=0)
    scheduler.add_job(send_pre_arrival_reminders, "cron", hour=18, minute=0)
    scheduler.add_job(send_financial_alerts, "cron", hour=21, minute=0)
    scheduler.add_job(send_automated_daily_pricing_reports, "cron", hour=0, minute=0)
    
    # Poll owner emails on a safer cadence to avoid overlap on slow IMAP cycles.
    scheduler.add_job(
        poll_email_replies_job,
        "interval",
        seconds=30,
        id="poll_email_replies_job",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("✅ Scheduler: Scraper, Reminders, Finance, MidnightReport(00:00) + EmailAgent(30s)")
