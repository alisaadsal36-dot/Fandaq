"""
Employee evaluation service.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_evaluation import EmployeeEvaluation, EvaluationStatus
from app.models.user import User, UserRole


class EmployeeEvaluationService:

    @staticmethod
    async def create_evaluation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        supervisor: User,
        employee: User,
        payload: dict,
    ) -> EmployeeEvaluation:
        if payload["period_end"] < payload["period_start"]:
            raise ValueError("تاريخ نهاية الفترة يجب أن يكون بعد تاريخ البداية")

        evaluation = EmployeeEvaluation(
            hotel_id=hotel_id,
            employee_user_id=employee.id,
            employee_name=employee.full_name,
            supervisor_user_id=supervisor.id,
            supervisor_name=supervisor.full_name,
            period_start=payload["period_start"],
            period_end=payload["period_end"],
            commitment_score=payload["commitment_score"],
            speed_score=payload["speed_score"],
            communication_score=payload["communication_score"],
            quality_score=payload["quality_score"],
            strengths=payload.get("strengths"),
            improvement_areas=payload.get("improvement_areas"),
            supervisor_notes=payload.get("supervisor_notes"),
            status=EvaluationStatus.SUBMITTED,
        )
        db.add(evaluation)
        await db.flush()
        return evaluation

    @staticmethod
    async def list_evaluations(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        current_user: User,
        status: EvaluationStatus | None = None,
    ) -> list[EmployeeEvaluation]:
        stmt = select(EmployeeEvaluation).where(EmployeeEvaluation.hotel_id == hotel_id)

        if current_user.role == UserRole.SUPERVISOR:
            stmt = stmt.where(EmployeeEvaluation.supervisor_user_id == current_user.id)

        if status:
            stmt = stmt.where(EmployeeEvaluation.status == status)

        stmt = stmt.order_by(EmployeeEvaluation.submitted_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def review_evaluation(
        db: AsyncSession,
        hotel_id: uuid.UUID,
        evaluation_id: uuid.UUID,
        reviewer: User,
        status: EvaluationStatus,
        admin_notes: str | None,
    ) -> EmployeeEvaluation | None:
        stmt = select(EmployeeEvaluation).where(
            EmployeeEvaluation.hotel_id == hotel_id,
            EmployeeEvaluation.id == evaluation_id,
        )
        evaluation = (await db.execute(stmt)).scalar_one_or_none()
        if not evaluation:
            return None

        if status == EvaluationStatus.SUBMITTED:
            raise ValueError("لا يمكن اعتماد حالة submitted في المراجعة")

        evaluation.status = status
        evaluation.reviewed_at = datetime.utcnow()
        evaluation.reviewed_by_user_id = reviewer.id
        evaluation.reviewed_by_name = reviewer.full_name
        evaluation.admin_notes = admin_notes
        await db.flush()
        return evaluation

    @staticmethod
    async def list_eligible_employees(db: AsyncSession, hotel_id: uuid.UUID) -> list[User]:
        stmt = select(User).where(
            User.hotel_id == hotel_id,
            User.is_active == True,
            User.role.in_([UserRole.EMPLOYEE, UserRole.SUPERVISOR]),
        ).order_by(User.full_name.asc())
        return list((await db.execute(stmt)).scalars().all())
