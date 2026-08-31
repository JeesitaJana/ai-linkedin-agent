"""create schedules and research items tables

Revision ID: 20260831_0002
Revises: 20260831_0001
Create Date: 2026-08-31 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0002"
down_revision: str | None = "20260831_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("days", sa.JSON(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_schedules_id"), "schedules", ["id"], unique=False)
    op.create_index(op.f("ix_schedules_active"), "schedules", ["active"], unique=False)
    op.create_table(
        "research_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url", name="uq_research_items_source_url"),
    )
    op.create_index(op.f("ix_research_items_id"), "research_items", ["id"], unique=False)
    op.create_index(op.f("ix_research_items_topic"), "research_items", ["topic"], unique=False)
    op.create_index(op.f("ix_research_items_published_at"), "research_items", ["published_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_research_items_published_at"), table_name="research_items")
    op.drop_index(op.f("ix_research_items_topic"), table_name="research_items")
    op.drop_index(op.f("ix_research_items_id"), table_name="research_items")
    op.drop_table("research_items")
    op.drop_index(op.f("ix_schedules_active"), table_name="schedules")
    op.drop_index(op.f("ix_schedules_id"), table_name="schedules")
    op.drop_table("schedules")
