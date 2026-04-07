"""
Employee evaluation schemas.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.employee_evaluation import EvaluationStatus


class EmployeeEvaluationCreate(BaseModel):
    employee_user_id: uuid.UUID
    period_start: date
    period_end: date
    commitment_score: int = Field(..., ge=1, le=5)
    speed_score: int = Field(..., ge=1, le=5)
    communication_score: int = Field(..., ge=1, le=5)
    quality_score: int = Field(..., ge=1, le=5)
    strengths: str | None = Field(default=None, max_length=2000)
    improvement_areas: str | None = Field(default=None, max_length=2000)
    supervisor_notes: str | None = Field(default=None, max_length=2000)


class EmployeeEvaluationReview(BaseModel):
    status: EvaluationStatus = Field(..., description="approved or needs_improvement")
    admin_notes: str | None = Field(default=None, max_length=2000)


class EmployeeEvaluationResponse(BaseModel):
    id: uuid.UUID
    hotel_id: uuid.UUID
    employee_user_id: uuid.UUID
    employee_name: str
    supervisor_user_id: uuid.UUID
    supervisor_name: str
    period_start: date
    period_end: date
    commitment_score: int
    speed_score: int
    communication_score: int
    quality_score: int
    strengths: str | None = None
    improvement_areas: str | None = None
    supervisor_notes: str | None = None
    status: EvaluationStatus
    submitted_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_user_id: uuid.UUID | None = None
    reviewed_by_name: str | None = None
    admin_notes: str | None = None

    model_config = {"from_attributes": True}


class EmployeeEvaluationListResponse(BaseModel):
    evaluations: list[EmployeeEvaluationResponse]
    total: int
