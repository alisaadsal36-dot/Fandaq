"""
Employee evaluations API — supervisor survey and admin review.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role_for_hotel
from app.database import get_db
from app.models.employee_evaluation import EvaluationStatus
from app.models.user import User, UserRole
from app.schemas.complaint import AssignableStaffItem, AssignableStaffResponse
from app.schemas.employee_evaluation import (
    EmployeeEvaluationCreate,
    EmployeeEvaluationListResponse,
    EmployeeEvaluationResponse,
    EmployeeEvaluationReview,
)
from app.services.employee_evaluation import EmployeeEvaluationService

router = APIRouter()


@router.get(
    "/hotels/{hotel_id}/employee-evaluations/eligible-employees",
    response_model=AssignableStaffResponse,
)
async def eligible_employees(
    hotel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR)),
):
    users = await EmployeeEvaluationService.list_eligible_employees(db, hotel_id)
    return AssignableStaffResponse(
        users=[AssignableStaffItem(id=u.id, full_name=u.full_name, role=u.role.value) for u in users]
    )


@router.post(
    "/hotels/{hotel_id}/employee-evaluations",
    response_model=EmployeeEvaluationResponse,
    status_code=201,
)
async def create_employee_evaluation(
    hotel_id: uuid.UUID,
    data: EmployeeEvaluationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR)),
):
    employee = (await db.execute(
        select(User).where(
            User.id == data.employee_user_id,
            User.hotel_id == hotel_id,
            User.is_active == True,
            User.role.in_([UserRole.EMPLOYEE, UserRole.SUPERVISOR]),
        )
    )).scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="الموظف غير موجود في هذا الفندق")

    if current_user.role == UserRole.SUPERVISOR and employee.id == current_user.id:
        raise HTTPException(status_code=400, detail="لا يمكن للمشرف تقييم نفسه")

    try:
        evaluation = await EmployeeEvaluationService.create_evaluation(
            db=db,
            hotel_id=hotel_id,
            supervisor=current_user,
            employee=employee,
            payload=data.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return evaluation


@router.get(
    "/hotels/{hotel_id}/employee-evaluations",
    response_model=EmployeeEvaluationListResponse,
)
async def list_employee_evaluations(
    hotel_id: uuid.UUID,
    status: EvaluationStatus | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role_for_hotel(UserRole.ADMIN, UserRole.SUPERVISOR)),
):
    evaluations = await EmployeeEvaluationService.list_evaluations(
        db=db,
        hotel_id=hotel_id,
        current_user=current_user,
        status=status,
    )
    return EmployeeEvaluationListResponse(evaluations=evaluations, total=len(evaluations))


@router.patch(
    "/hotels/{hotel_id}/employee-evaluations/{evaluation_id}/review",
    response_model=EmployeeEvaluationResponse,
)
async def review_employee_evaluation(
    hotel_id: uuid.UUID,
    evaluation_id: uuid.UUID,
    data: EmployeeEvaluationReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role_for_hotel(UserRole.ADMIN)),
):
    try:
        evaluation = await EmployeeEvaluationService.review_evaluation(
            db=db,
            hotel_id=hotel_id,
            evaluation_id=evaluation_id,
            reviewer=current_user,
            status=data.status,
            admin_notes=data.admin_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not evaluation:
        raise HTTPException(status_code=404, detail="التقييم غير موجود")
    return evaluation
