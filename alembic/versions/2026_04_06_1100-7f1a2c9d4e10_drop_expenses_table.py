"""drop expenses table

Revision ID: 7f1a2c9d4e10
Revises: 6d2a9d3bcb11
Create Date: 2026-04-06 11:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "7f1a2c9d4e10"
down_revision = "6d2a9d3bcb11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_expenses_hotel_id"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_expense_date"), table_name="expenses")
    op.drop_table("expenses")


def downgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hotel_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expense_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expenses_expense_date"), "expenses", ["expense_date"], unique=False)
    op.create_index(op.f("ix_expenses_hotel_id"), "expenses", ["hotel_id"], unique=False)
