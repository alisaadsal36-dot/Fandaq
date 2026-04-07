"""
Report Pydantic schemas.
"""

from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel


class ReportRequest(BaseModel):
    report_type: str  # daily, weekly, monthly
    reference_date: Optional[date_type] = None


class ReportResponse(BaseModel):
    report_type: str
    period_start: str
    period_end: str
    data: dict


class FinancialSummary(BaseModel):
    total_income: float
    net_profit: float
    reservations_count: int
    occupancy_rate: float
    income_by_room_type: dict[str, float]


class StaffPerformanceEntry(BaseModel):
    user_id: str
    full_name: str
    username: str
    role: str
    complaints_resolved: int
    reservations_approved: int
    requests_completed: int
    avg_resolution_hours: float
    avg_approval_hours: float
    avg_request_completion_hours: float
    total_actions: int
    first_response_sla_total: int
    first_response_sla_met: int
    first_response_sla_breached: int
    first_response_sla_rate: float
    resolution_sla_total: int
    resolution_sla_met: int
    resolution_sla_breached: int
    resolution_sla_rate: float
    score: int
    rank: int
    last_activity_at: str | None = None
    weekly_trend: list[dict]


class StaffPerformanceSummary(BaseModel):
    total_staff: int
    active_staff: int
    total_complaints_resolved: int
    total_reservations_approved: int
    total_requests_completed: int
    avg_response_hours: float
    avg_approval_hours: float
    rejection_rate: float
    sla_first_response_target_minutes: int
    sla_resolution_target_hours: int
    first_response_sla_total: int
    first_response_sla_met: int
    first_response_sla_breached: int
    first_response_sla_rate: float
    resolution_sla_total: int
    resolution_sla_met: int
    resolution_sla_breached: int
    resolution_sla_rate: float


class StaffPerformanceResponse(BaseModel):
    period_days: int
    period_start: str
    period_end: str
    summary: StaffPerformanceSummary
    leaderboard: list[StaffPerformanceEntry]
