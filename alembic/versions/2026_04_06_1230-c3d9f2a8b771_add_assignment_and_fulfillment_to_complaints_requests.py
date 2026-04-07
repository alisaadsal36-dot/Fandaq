"""add assignment and fulfillment to complaints and guest requests

Revision ID: c3d9f2a8b771
Revises: 7f1a2c9d4e10
Create Date: 2026-04-06 12:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d9f2a8b771"
down_revision: Union[str, None] = "7f1a2c9d4e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("assigned_to_user_id", sa.UUID(), nullable=True, comment="User assigned by supervisor/admin to resolve this complaint"))
    op.add_column("complaints", sa.Column("assigned_to_name", sa.String(length=255), nullable=True, comment="Snapshot name of assigned resolver"))
    op.add_column("complaints", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_complaints_assigned_to_user_id"), "complaints", ["assigned_to_user_id"], unique=False)
    op.create_foreign_key(
        "fk_complaints_assigned_to_user_id_users",
        "complaints",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("guest_requests", sa.Column("assigned_to_user_id", sa.UUID(), nullable=True, comment="User assigned by supervisor/admin to execute this request"))
    op.add_column("guest_requests", sa.Column("assigned_to_name", sa.String(length=255), nullable=True, comment="Snapshot name of assigned executor"))
    op.add_column("guest_requests", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("guest_requests", sa.Column("fulfillment_status", sa.String(length=30), nullable=True, comment="pending, partial, completed, failed"))
    op.add_column("guest_requests", sa.Column("fulfillment_details", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json"), comment="Timeline of fulfillment steps"))
    op.create_index(op.f("ix_guest_requests_assigned_to_user_id"), "guest_requests", ["assigned_to_user_id"], unique=False)
    op.create_foreign_key(
        "fk_guest_requests_assigned_to_user_id_users",
        "guest_requests",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_guest_requests_assigned_to_user_id_users", "guest_requests", type_="foreignkey")
    op.drop_index(op.f("ix_guest_requests_assigned_to_user_id"), table_name="guest_requests")
    op.drop_column("guest_requests", "fulfillment_details")
    op.drop_column("guest_requests", "fulfillment_status")
    op.drop_column("guest_requests", "assigned_at")
    op.drop_column("guest_requests", "assigned_to_name")
    op.drop_column("guest_requests", "assigned_to_user_id")

    op.drop_constraint("fk_complaints_assigned_to_user_id_users", "complaints", type_="foreignkey")
    op.drop_index(op.f("ix_complaints_assigned_to_user_id"), table_name="complaints")
    op.drop_column("complaints", "assigned_at")
    op.drop_column("complaints", "assigned_to_name")
    op.drop_column("complaints", "assigned_to_user_id")
