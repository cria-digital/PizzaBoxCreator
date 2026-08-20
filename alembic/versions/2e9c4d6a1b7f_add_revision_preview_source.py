"""add preview_source to order revisions

Revision ID: 2e9c4d6a1b7f
Revises: 68d32d782435
Create Date: 2026-08-20
"""

from alembic import context, op
import sqlalchemy as sa


revision = "2e9c4d6a1b7f"
down_revision = "68d32d782435"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.execute(
            "ALTER TABLE order_revisions "
            "ADD COLUMN IF NOT EXISTS preview_source VARCHAR NOT NULL DEFAULT 'psd'"
        )
        return

    conn = op.get_bind()
    has_col = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'order_revisions' AND column_name = 'preview_source'"
    )).scalar()
    if not has_col:
        op.add_column(
            "order_revisions",
            sa.Column("preview_source", sa.String(), nullable=False, server_default="psd"),
        )


def downgrade() -> None:
    op.drop_column("order_revisions", "preview_source")
