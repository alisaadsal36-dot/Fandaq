"""
Models package — import all models so SQLAlchemy registers them.
"""

from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.room import Room, RoomStatus
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatus
from app.models.complaint import Complaint, ComplaintStatus
from app.models.guest_request import GuestRequest, RequestStatus
from app.models.whatsapp_session import WhatsAppSession
from app.models.processed_message import ProcessedMessage
from app.models.audit_log import AuditLog
from app.models.review import Review
from app.models.daily_pricing import DailyPricing
from app.models.competitor import Competitor
from app.models.user import User, UserRole
from app.models.employee_evaluation import EmployeeEvaluation, EvaluationStatus

__all__ = [
    "Hotel",
    "RoomType",
    "Room",
    "RoomStatus",
    "Guest",
    "Reservation",
    "ReservationStatus",
    "Complaint",
    "ComplaintStatus",
    "GuestRequest",
    "RequestStatus",
    "WhatsAppSession",
    "Review",
    "DailyPricing",
    "Competitor",
    "User",
    "UserRole",
    "EmployeeEvaluation",
    "EvaluationStatus",
]
