"""
Report service — generate daily/weekly/monthly financial reports.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.complaint import Complaint, ComplaintStatus
from app.models.guest_request import GuestRequest, RequestStatus
from app.models.reservation import Reservation, ReservationStatus
from app.models.room import Room
from app.models.room_type import RoomType
from app.models.user import User, UserRole


class ReportService:

    @staticmethod
    async def generate_report(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        report_type: str,
        reference_date: date | None = None,
    ) -> dict:
        """
        Generate a financial report for a hotel.

        report_type: 'daily', 'weekly', 'monthly'
        reference_date: the date to center the report around (defaults to today)
        """
        ref = reference_date or date.today()

        # Calculate period
        if report_type == "daily":
            period_start = ref
            period_end = ref
        elif report_type == "weekly":
            # Monday to Sunday
            period_start = ref - timedelta(days=ref.weekday())
            period_end = period_start + timedelta(days=6)
        elif report_type == "monthly":
            period_start = ref.replace(day=1)
            # Last day of month
            if ref.month == 12:
                period_end = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                period_end = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)
        else:
            period_start = ref
            period_end = ref

        # ── Income ─────────────────────────────────────
        # Sum total_price of confirmed/checked-in/checked-out reservations
        income_stmt = select(func.sum(Reservation.total_price)).where(
            Reservation.hotel_id == hotel_id,
            Reservation.status.in_([
                ReservationStatus.CONFIRMED,
                ReservationStatus.CHECKED_IN,
                ReservationStatus.CHECKED_OUT,
            ]),
            Reservation.check_in <= period_end,
            Reservation.check_out >= period_start,
        )
        income_result = await db.execute(income_stmt)
        total_income = float(income_result.scalar() or 0)

        # Income by room type
        income_by_type_stmt = (
            select(RoomType.name, func.sum(Reservation.total_price))
            .join(RoomType, Reservation.room_type_id == RoomType.id)
            .where(
                Reservation.hotel_id == hotel_id,
                Reservation.status.in_([
                    ReservationStatus.CONFIRMED,
                    ReservationStatus.CHECKED_IN,
                    ReservationStatus.CHECKED_OUT,
                ]),
                Reservation.check_in <= period_end,
                Reservation.check_out >= period_start,
            )
            .group_by(RoomType.name)
        )
        income_by_type_result = await db.execute(income_by_type_stmt)
        income_by_room_type = {
            row[0]: float(row[1]) for row in income_by_type_result.all()
        }

        # ── Reservations count ─────────────────────────
        res_count_stmt = select(func.count(Reservation.id)).where(
            Reservation.hotel_id == hotel_id,
            Reservation.check_in <= period_end,
            Reservation.check_out >= period_start,
            Reservation.status.in_([
                ReservationStatus.CONFIRMED,
                ReservationStatus.CHECKED_IN,
                ReservationStatus.CHECKED_OUT,
            ]),
        )
        res_count_result = await db.execute(res_count_stmt)
        reservations_count = res_count_result.scalar() or 0

        # ── Occupancy rate ─────────────────────────────
        total_rooms_stmt = select(func.count(Room.id)).where(
            Room.hotel_id == hotel_id
        )
        total_rooms_result = await db.execute(total_rooms_stmt)
        total_rooms = total_rooms_result.scalar() or 1  # Avoid division by zero

        days_in_period = max(1, (period_end - period_start).days + 1)
        total_room_nights = total_rooms * days_in_period
        occupancy_rate = (reservations_count / total_room_nights) * 100 if total_room_nights > 0 else 0

        return {
            "report_type": report_type,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "data": {
                "total_income": total_income,
                "net_profit": total_income,
                "reservations_count": reservations_count,
                "occupancy_rate": round(occupancy_rate, 2),
                "income_by_room_type": income_by_room_type,
            },
        }

    @staticmethod
    async def generate_staff_performance(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        period_days: int = 30,
    ) -> dict:
        """Build a leaderboard for staff performance over the selected period."""
        settings = get_settings()
        first_response_sla_hours = max(1, settings.SLA_FIRST_RESPONSE_MINUTES) / 60.0
        resolution_sla_hours = float(max(1, settings.SLA_RESOLUTION_HOURS))

        period_days = max(1, min(period_days, 365))
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=period_days)

        staff_stmt = select(User).where(
            User.hotel_id == hotel_id,
            User.is_active == True,
            User.role.in_([UserRole.EMPLOYEE, UserRole.SUPERVISOR]),
        )
        staff_rows = (await db.execute(staff_stmt)).scalars().all()

        complaint_stats_stmt = (
            select(
                Complaint.resolved_by_user_id,
                func.count(Complaint.id),
                func.avg(
                    func.extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600.0
                ),
                func.max(Complaint.resolved_at),
            )
            .where(
                Complaint.hotel_id == hotel_id,
                Complaint.status == ComplaintStatus.RESOLVED,
                Complaint.resolved_by_user_id.is_not(None),
                Complaint.resolved_at.is_not(None),
                Complaint.resolved_at >= period_start,
            )
            .group_by(Complaint.resolved_by_user_id)
        )
        complaint_stats = {
            row[0]: {
                "count": int(row[1] or 0),
                "avg_hours": float(row[2] or 0),
                "last_activity": row[3],
            }
            for row in (await db.execute(complaint_stats_stmt)).all()
            if row[0] is not None
        }

        reservation_stats_stmt = (
            select(
                Reservation.approved_by_user_id,
                func.count(Reservation.id),
                func.avg(
                    func.extract("epoch", Reservation.approved_at - Reservation.created_at) / 3600.0
                ),
                func.max(Reservation.approved_at),
            )
            .where(
                Reservation.hotel_id == hotel_id,
                Reservation.approved_by_user_id.is_not(None),
                Reservation.approved_at.is_not(None),
                Reservation.approved_at >= period_start,
            )
            .group_by(Reservation.approved_by_user_id)
        )
        reservation_stats = {
            row[0]: {
                "count": int(row[1] or 0),
                "avg_hours": float(row[2] or 0),
                "last_activity": row[3],
            }
            for row in (await db.execute(reservation_stats_stmt)).all()
            if row[0] is not None
        }

        request_stats_stmt = (
            select(
                GuestRequest.completed_by_user_id,
                func.count(GuestRequest.id),
                func.avg(
                    func.extract("epoch", GuestRequest.completed_at - GuestRequest.created_at) / 3600.0
                ),
                func.max(GuestRequest.completed_at),
            )
            .where(
                GuestRequest.hotel_id == hotel_id,
                GuestRequest.status == RequestStatus.COMPLETED,
                GuestRequest.completed_by_user_id.is_not(None),
                GuestRequest.completed_at.is_not(None),
                GuestRequest.completed_at >= period_start,
            )
            .group_by(GuestRequest.completed_by_user_id)
        )
        request_stats = {
            row[0]: {
                "count": int(row[1] or 0),
                "avg_hours": float(row[2] or 0),
                "last_activity": row[3],
            }
            for row in (await db.execute(request_stats_stmt)).all()
            if row[0] is not None
        }

        complaint_events_stmt = select(
            Complaint.resolved_by_user_id,
            Complaint.resolved_at,
        ).where(
            Complaint.hotel_id == hotel_id,
            Complaint.status == ComplaintStatus.RESOLVED,
            Complaint.resolved_by_user_id.is_not(None),
            Complaint.resolved_at.is_not(None),
            Complaint.resolved_at >= period_start,
        )
        complaint_events = (await db.execute(complaint_events_stmt)).all()

        reservation_events_stmt = select(
            Reservation.approved_by_user_id,
            Reservation.approved_at,
        ).where(
            Reservation.hotel_id == hotel_id,
            Reservation.approved_by_user_id.is_not(None),
            Reservation.approved_at.is_not(None),
            Reservation.approved_at >= period_start,
        )
        reservation_events = (await db.execute(reservation_events_stmt)).all()

        request_events_stmt = select(
            GuestRequest.completed_by_user_id,
            GuestRequest.completed_at,
        ).where(
            GuestRequest.hotel_id == hotel_id,
            GuestRequest.status == RequestStatus.COMPLETED,
            GuestRequest.completed_by_user_id.is_not(None),
            GuestRequest.completed_at.is_not(None),
            GuestRequest.completed_at >= period_start,
        )
        request_events = (await db.execute(request_events_stmt)).all()

        week_window = 6
        today = period_end.date()
        current_week_monday = today - timedelta(days=today.weekday())
        week_starts = [current_week_monday - timedelta(days=7 * i) for i in range(week_window - 1, -1, -1)]
        week_key_set = {w.isoformat() for w in week_starts}

        weekly_by_user: dict[uuid.UUID, dict[str, int]] = {}

        def _add_weekly_event(user_id, event_dt):
            if user_id is None or event_dt is None:
                return
            event_date = event_dt.date()
            week_start = event_date - timedelta(days=event_date.weekday())
            week_key = week_start.isoformat()
            if week_key not in week_key_set:
                return
            if user_id not in weekly_by_user:
                weekly_by_user[user_id] = {}
            weekly_by_user[user_id][week_key] = weekly_by_user[user_id].get(week_key, 0) + 1

        for row in complaint_events:
            _add_weekly_event(row[0], row[1])
        for row in reservation_events:
            _add_weekly_event(row[0], row[1])
        for row in request_events:
            _add_weekly_event(row[0], row[1])

        sla_first_response_by_user: dict[uuid.UUID, dict[str, int]] = {}
        sla_resolution_by_user: dict[uuid.UUID, dict[str, int]] = {}

        def _track_sla(container: dict[uuid.UUID, dict[str, int]], user_id, actual_hours, threshold_hours):
            if user_id is None or actual_hours is None:
                return
            stats = container.setdefault(user_id, {"total": 0, "met": 0})
            stats["total"] += 1
            if float(actual_hours) <= threshold_hours:
                stats["met"] += 1

        complaint_first_response_events = (
            await db.execute(
                select(
                    Complaint.first_response_by_user_id,
                    func.extract("epoch", Complaint.acknowledged_at - Complaint.created_at) / 3600.0,
                ).where(
                    Complaint.hotel_id == hotel_id,
                    Complaint.first_response_by_user_id.is_not(None),
                    Complaint.acknowledged_at.is_not(None),
                    Complaint.created_at.is_not(None),
                    Complaint.acknowledged_at >= period_start,
                )
            )
        ).all()
        for user_id, hours in complaint_first_response_events:
            _track_sla(sla_first_response_by_user, user_id, hours, first_response_sla_hours)

        request_first_response_events = (
            await db.execute(
                select(
                    GuestRequest.first_response_by_user_id,
                    func.extract("epoch", GuestRequest.acknowledged_at - GuestRequest.created_at) / 3600.0,
                ).where(
                    GuestRequest.hotel_id == hotel_id,
                    GuestRequest.first_response_by_user_id.is_not(None),
                    GuestRequest.acknowledged_at.is_not(None),
                    GuestRequest.created_at.is_not(None),
                    GuestRequest.acknowledged_at >= period_start,
                )
            )
        ).all()
        for user_id, hours in request_first_response_events:
            _track_sla(sla_first_response_by_user, user_id, hours, first_response_sla_hours)

        complaint_resolution_events = (
            await db.execute(
                select(
                    Complaint.resolved_by_user_id,
                    func.extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600.0,
                ).where(
                    Complaint.hotel_id == hotel_id,
                    Complaint.resolved_by_user_id.is_not(None),
                    Complaint.resolved_at.is_not(None),
                    Complaint.created_at.is_not(None),
                    Complaint.resolved_at >= period_start,
                )
            )
        ).all()
        for user_id, hours in complaint_resolution_events:
            _track_sla(sla_resolution_by_user, user_id, hours, resolution_sla_hours)

        request_resolution_events = (
            await db.execute(
                select(
                    GuestRequest.completed_by_user_id,
                    func.extract("epoch", GuestRequest.completed_at - GuestRequest.created_at) / 3600.0,
                ).where(
                    GuestRequest.hotel_id == hotel_id,
                    GuestRequest.completed_by_user_id.is_not(None),
                    GuestRequest.completed_at.is_not(None),
                    GuestRequest.created_at.is_not(None),
                    GuestRequest.completed_at >= period_start,
                )
            )
        ).all()
        for user_id, hours in request_resolution_events:
            _track_sla(sla_resolution_by_user, user_id, hours, resolution_sla_hours)

        decision_counts_stmt = (
            select(
                func.count(Reservation.id).filter(Reservation.status == ReservationStatus.REJECTED),
                func.count(Reservation.id).filter(
                    Reservation.status.in_([
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.CHECKED_IN,
                        ReservationStatus.CHECKED_OUT,
                    ])
                ),
            )
            .where(
                Reservation.hotel_id == hotel_id,
                Reservation.created_at >= period_start,
            )
        )
        rejected_count, accepted_count = (await db.execute(decision_counts_stmt)).one()
        rejected_count = int(rejected_count or 0)
        accepted_count = int(accepted_count or 0)
        total_decisions = rejected_count + accepted_count
        rejection_rate = round((rejected_count / total_decisions) * 100, 2) if total_decisions > 0 else 0.0

        overall_approval_stmt = select(
            func.avg(
                func.extract("epoch", Reservation.approved_at - Reservation.created_at) / 3600.0
            )
        ).where(
            Reservation.hotel_id == hotel_id,
            Reservation.approved_at.is_not(None),
            Reservation.approved_at >= period_start,
        )
        overall_avg_approval_hours = float((await db.execute(overall_approval_stmt)).scalar() or 0.0)

        leaderboard = []
        total_resolved = 0
        weighted_resolution_hours = 0.0

        for idx, user in enumerate(staff_rows):
            c_data = complaint_stats.get(user.id, {})
            r_data = reservation_stats.get(user.id, {})
            req_data = request_stats.get(user.id, {})
            first_response_sla = sla_first_response_by_user.get(user.id, {"total": 0, "met": 0})
            resolution_sla = sla_resolution_by_user.get(user.id, {"total": 0, "met": 0})

            complaints_resolved = int(c_data.get("count", 0))
            reservations_approved = int(r_data.get("count", 0))
            requests_completed = int(req_data.get("count", 0))
            avg_resolution_hours = float(c_data.get("avg_hours", 0.0))
            avg_approval_hours = float(r_data.get("avg_hours", 0.0))
            avg_request_completion_hours = float(req_data.get("avg_hours", 0.0))
            total_actions = complaints_resolved + reservations_approved + requests_completed
            first_response_total = int(first_response_sla.get("total", 0))
            first_response_met = int(first_response_sla.get("met", 0))
            resolution_total = int(resolution_sla.get("total", 0))
            resolution_met = int(resolution_sla.get("met", 0))

            first_response_compliance_rate = (
                (first_response_met / first_response_total) * 100 if first_response_total > 0 else 0.0
            )
            resolution_compliance_rate = (
                (resolution_met / resolution_total) * 100 if resolution_total > 0 else 0.0
            )

            speed_bonus = 0
            if complaints_resolved > 0:
                # Rewards faster resolution with up to +10 bonus points.
                speed_bonus = max(0, 10 - int(avg_resolution_hours // 2))

            sla_bonus = int((first_response_compliance_rate + resolution_compliance_rate) / 20)

            score = (
                complaints_resolved * 5
                + reservations_approved * 3
                + requests_completed * 2
                + speed_bonus
                + sla_bonus
            )

            last_activity_candidates = [
                c_data.get("last_activity"),
                r_data.get("last_activity"),
                req_data.get("last_activity"),
            ]
            last_activity_candidates = [d for d in last_activity_candidates if d is not None]
            last_activity = max(last_activity_candidates) if last_activity_candidates else None

            total_resolved += complaints_resolved
            weighted_resolution_hours += avg_resolution_hours * complaints_resolved

            leaderboard.append({
                "user_id": str(user.id),
                "full_name": user.full_name,
                "username": user.username,
                "role": user.role.value,
                "complaints_resolved": complaints_resolved,
                "reservations_approved": reservations_approved,
                "requests_completed": requests_completed,
                "avg_resolution_hours": round(avg_resolution_hours, 2),
                "avg_approval_hours": round(avg_approval_hours, 2),
                "avg_request_completion_hours": round(avg_request_completion_hours, 2),
                "total_actions": total_actions,
                "first_response_sla_total": first_response_total,
                "first_response_sla_met": first_response_met,
                "first_response_sla_breached": max(0, first_response_total - first_response_met),
                "first_response_sla_rate": round(first_response_compliance_rate, 2),
                "resolution_sla_total": resolution_total,
                "resolution_sla_met": resolution_met,
                "resolution_sla_breached": max(0, resolution_total - resolution_met),
                "resolution_sla_rate": round(resolution_compliance_rate, 2),
                "score": score,
                "rank": idx + 1,
                "last_activity_at": last_activity.isoformat() if last_activity else None,
                "weekly_trend": [
                    {
                        "week_start": w.isoformat(),
                        "actions": weekly_by_user.get(user.id, {}).get(w.isoformat(), 0),
                    }
                    for w in week_starts
                ],
                "_sort_last_activity": last_activity,
            })

        leaderboard.sort(
            key=lambda row: (
                row["score"],
                row["total_actions"],
                row["complaints_resolved"],
                row["_sort_last_activity"] or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        for rank, row in enumerate(leaderboard, start=1):
            row["rank"] = rank
            row.pop("_sort_last_activity", None)

        active_staff = sum(1 for row in leaderboard if row["total_actions"] > 0)
        avg_response_hours = (
            round(weighted_resolution_hours / total_resolved, 2) if total_resolved > 0 else 0.0
        )
        first_response_total_all = sum(row["first_response_sla_total"] for row in leaderboard)
        first_response_met_all = sum(row["first_response_sla_met"] for row in leaderboard)
        resolution_total_all = sum(row["resolution_sla_total"] for row in leaderboard)
        resolution_met_all = sum(row["resolution_sla_met"] for row in leaderboard)

        return {
            "period_days": period_days,
            "period_start": period_start.date().isoformat(),
            "period_end": period_end.date().isoformat(),
            "summary": {
                "total_staff": len(staff_rows),
                "active_staff": active_staff,
                "total_complaints_resolved": sum(r["complaints_resolved"] for r in leaderboard),
                "total_reservations_approved": sum(r["reservations_approved"] for r in leaderboard),
                "total_requests_completed": sum(r["requests_completed"] for r in leaderboard),
                "avg_response_hours": avg_response_hours,
                "avg_approval_hours": round(overall_avg_approval_hours, 2),
                "rejection_rate": rejection_rate,
                "sla_first_response_target_minutes": settings.SLA_FIRST_RESPONSE_MINUTES,
                "sla_resolution_target_hours": settings.SLA_RESOLUTION_HOURS,
                "first_response_sla_total": first_response_total_all,
                "first_response_sla_met": first_response_met_all,
                "first_response_sla_breached": max(0, first_response_total_all - first_response_met_all),
                "first_response_sla_rate": round(
                    (first_response_met_all / first_response_total_all) * 100, 2
                ) if first_response_total_all > 0 else 0.0,
                "resolution_sla_total": resolution_total_all,
                "resolution_sla_met": resolution_met_all,
                "resolution_sla_breached": max(0, resolution_total_all - resolution_met_all),
                "resolution_sla_rate": round(
                    (resolution_met_all / resolution_total_all) * 100, 2
                ) if resolution_total_all > 0 else 0.0,
            },
            "leaderboard": leaderboard,
        }
