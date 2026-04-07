"""add employee evaluations table

Revision ID: 8e4b1c2f9d6a
Revises: c3d9f2a8b771
Create Date: 2026-04-06 14:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8e4b1c2f9d6a"
down_revision: Union[str, None] = "c3d9f2a8b771"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hotel_id", sa.UUID(), nullable=False),
        sa.Column("employee_user_id", sa.UUID(), nullable=False),
        sa.Column("employee_name", sa.String(length=255), nullable=False),
        sa.Column("supervisor_user_id", sa.UUID(), nullable=False),
        sa.Column("supervisor_name", sa.String(length=255), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("commitment_score", sa.Integer(), nullable=False),
        sa.Column("speed_score", sa.Integer(), nullable=False),
        sa.Column("communication_score", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("improvement_areas", sa.Text(), nullable=True),
        sa.Column("supervisor_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("SUBMITTED", "APPROVED", "NEEDS_IMPROVEMENT", name="evaluationstatus"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_by_name", sa.String(length=255), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supervisor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_employee_evaluations_hotel_id"), "employee_evaluations", ["hotel_id"], unique=False)
    op.create_index(op.f("ix_employee_evaluations_employee_user_id"), "employee_evaluations", ["employee_user_id"], unique=False)
    op.create_index(op.f("ix_employee_evaluations_supervisor_user_id"), "employee_evaluations", ["supervisor_user_id"], unique=False)
    op.create_index(op.f("ix_employee_evaluations_reviewed_by_user_id"), "employee_evaluations", ["reviewed_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_employee_evaluations_reviewed_by_user_id"), table_name="employee_evaluations")
    op.drop_index(op.f("ix_employee_evaluations_supervisor_user_id"), table_name="employee_evaluations")
    op.drop_index(op.f("ix_employee_evaluations_employee_user_id"), table_name="employee_evaluations")
    op.drop_index(op.f("ix_employee_evaluations_hotel_id"), table_name="employee_evaluations")
    op.drop_table("employee_evaluations")
    op.execute("DROP TYPE IF EXISTS evaluationstatus")
