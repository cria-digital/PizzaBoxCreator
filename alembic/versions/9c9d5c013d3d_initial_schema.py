"""initial schema — create all 7 tables from scratch

Revision ID: 9c9d5c013d3d
Revises:
Create Date: 2026-08-19 15:05:25.633503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c9d5c013d3d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("phone", sa.String, unique=True, nullable=False),
        sa.Column("instagram", sa.String, nullable=True),
        sa.Column("logo_path", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_clients_phone", "clients", ["phone"], unique=True)

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String, unique=True, nullable=False),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("size_cm", sa.Integer, nullable=True),
        sa.Column("product_type", sa.String, nullable=False, server_default="pizza"),
        sa.Column("editable_fields", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("calibration", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("thumbnail", sa.String, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE order_status AS ENUM (
                'draft', 'preview_sent', 'revision', 'approved', 'production', 'delivered'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="draft"),
        sa.Column("quantidade", sa.Integer, nullable=True),
        sa.Column("edit_data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("output_psd", sa.String, nullable=True),
        sa.Column("preview_jpg", sa.String, nullable=True),
        sa.Column("cmyk_psd", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orders_client", "orders", ["client_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_revisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("edit_data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("preview_jpg", sa.String, nullable=True),
        sa.Column("preview_source", sa.String, nullable=False, server_default="psd"),
        sa.Column("feedback", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_order_revision", "order_revisions", ["order_id", "revision_number"])
    op.create_index("ix_revisions_order", "order_revisions", ["order_id"])

    op.create_table(
        "whatsapp_messages",
        sa.Column("wamid", sa.String, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_wa_messages_order", "whatsapp_messages", ["order_id"])

    op.execute("""
        CREATE TABLE admin_account (
            id SERIAL PRIMARY KEY,
            username VARCHAR NOT NULL UNIQUE,
            password_hash VARCHAR NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE whatsapp_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            token VARCHAR,
            phone_number_id VARCHAR,
            verify_token VARCHAR,
            app_secret VARCHAR,
            api_version VARCHAR NOT NULL DEFAULT 'v21.0',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.drop_table("whatsapp_config")
    op.drop_table("admin_account")
    op.drop_index("ix_wa_messages_order", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
    op.drop_index("ix_revisions_order", table_name="order_revisions")
    op.drop_constraint("uq_order_revision", "order_revisions", type_="unique")
    op.drop_table("order_revisions")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_client", table_name="orders")
    op.drop_table("orders")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.drop_table("templates")
    op.drop_index("ix_clients_phone", table_name="clients")
    op.drop_table("clients")
