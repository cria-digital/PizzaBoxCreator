"""add crm profiles, interactions, reengagement and funnel history

Revision ID: 7b4a9d2c1e6f
Revises: 2e9c4d6a1b7f
Create Date: 2026-09-02
"""

from alembic import context, op
import sqlalchemy as sa


revision = "7b4a9d2c1e6f"
down_revision = "2e9c4d6a1b7f"
branch_labels = None
depends_on = None


CLASSIFICATIONS = "'new','active','vip','at_risk','abandoned','inactive'"
STAGES = (
    "'lead','qualified','order_created','preview_sent','revision','approved',"
    "'production','delivered'"
)
ORDER_STATUSES = "'draft','preview_sent','revision','approved','production','delivered'"


def upgrade() -> None:
    if context.is_offline_mode():
        op.execute(
            "CREATE TABLE IF NOT EXISTS crm_profiles ("
            "id SERIAL PRIMARY KEY, "
            "client_id INTEGER NOT NULL UNIQUE REFERENCES clients(id), "
            "classification VARCHAR NOT NULL DEFAULT 'new', "
            "lifecycle_stage VARCHAR NOT NULL DEFAULT 'lead', "
            "score INTEGER, "
            "last_contact_at TIMESTAMPTZ, "
            "last_order_at TIMESTAMPTZ, "
            "last_classified_at TIMESTAMPTZ, "
            "next_reengagement_at TIMESTAMPTZ, "
            "reengagement_paused BOOLEAN NOT NULL DEFAULT FALSE, "
            "classification_reason TEXT, "
            "classification_data JSON NOT NULL DEFAULT '{}', "
            "rule_version VARCHAR, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
            "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS crm_interactions ("
            "id SERIAL PRIMARY KEY, "
            "client_id INTEGER NOT NULL REFERENCES clients(id), "
            "order_id INTEGER REFERENCES orders(id), "
            "channel VARCHAR NOT NULL, direction VARCHAR NOT NULL, "
            "event_type VARCHAR NOT NULL, payload JSON NOT NULL DEFAULT '{}', "
            "occurred_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
            "idempotency_key VARCHAR UNIQUE)"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS crm_classification_events ("
            "id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), "
            "previous_classification VARCHAR, new_classification VARCHAR NOT NULL, "
            "reason TEXT NOT NULL, evidence JSON NOT NULL DEFAULT '{}', "
            "rule_version VARCHAR NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS crm_reengagement_tasks ("
            "id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), "
            "order_id INTEGER REFERENCES orders(id), reason VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL DEFAULT 'pending', scheduled_for TIMESTAMPTZ NOT NULL, "
            "attempt_count INTEGER NOT NULL DEFAULT 0, sent_at TIMESTAMPTZ, last_error TEXT, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS order_status_events ("
            "id SERIAL PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), "
            "from_status VARCHAR, to_status VARCHAR NOT NULL, source VARCHAR NOT NULL DEFAULT 'system', "
            "actor VARCHAR, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        for table, columns in _indexes().items():
            for name, col in columns:
                op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col})")
        return

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "crm_profiles" not in tables:
        op.create_table(
            "crm_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, unique=True),
            sa.Column("classification", sa.String(), nullable=False, server_default="new"),
            sa.Column("lifecycle_stage", sa.String(), nullable=False, server_default="lead"),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_classified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_reengagement_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reengagement_paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("classification_reason", sa.Text(), nullable=True),
            sa.Column("classification_data", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("rule_version", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(f"classification IN ({CLASSIFICATIONS})", name="ck_crm_profiles_classification"),
            sa.CheckConstraint(f"lifecycle_stage IN ({STAGES})", name="ck_crm_profiles_lifecycle_stage"),
        )

    if "crm_interactions" not in tables:
        op.create_table(
            "crm_interactions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("direction", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("idempotency_key", sa.String(), nullable=True, unique=True),
            sa.CheckConstraint("channel IN ('whatsapp','web','api','system')", name="ck_crm_interactions_channel"),
            sa.CheckConstraint("direction IN ('inbound','outbound','internal')", name="ck_crm_interactions_direction"),
        )

    if "crm_classification_events" not in tables:
        op.create_table(
            "crm_classification_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("previous_classification", sa.String(), nullable=True),
            sa.Column("new_classification", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("rule_version", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                f"previous_classification IS NULL OR previous_classification IN ({CLASSIFICATIONS})",
                name="ck_crm_classification_events_previous",
            ),
            sa.CheckConstraint(
                f"new_classification IN ({CLASSIFICATIONS})",
                name="ck_crm_classification_events_new",
            ),
        )

    if "crm_reengagement_tasks" not in tables:
        op.create_table(
            "crm_reengagement_tasks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("status IN ('pending','sent','skipped','failed')", name="ck_crm_reengagement_status"),
        )

    if "order_status_events" not in tables:
        op.create_table(
            "order_status_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("from_status", sa.String(), nullable=True),
            sa.Column("to_status", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False, server_default="system"),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(f"from_status IS NULL OR from_status IN ({ORDER_STATUSES})", name="ck_order_status_events_from"),
            sa.CheckConstraint(f"to_status IN ({ORDER_STATUSES})", name="ck_order_status_events_to"),
        )

    for table, columns in _indexes().items():
        existing = {idx["name"] for idx in sa.inspect(conn).get_indexes(table)}
        for name, cols in columns:
            if name not in existing:
                op.create_index(name, table, [cols], unique=False)


def downgrade() -> None:
    for table in (
        "order_status_events",
        "crm_reengagement_tasks",
        "crm_classification_events",
        "crm_interactions",
        "crm_profiles",
    ):
        op.drop_table(table)


def _indexes() -> dict[str, list[tuple[str, str]]]:
    return {
        "crm_profiles": [
            ("idx_crm_profiles_classification", "classification"),
            ("idx_crm_profiles_lifecycle_stage", "lifecycle_stage"),
            ("idx_crm_profiles_next_reengagement", "next_reengagement_at"),
        ],
        "crm_interactions": [
            ("idx_crm_interactions_client", "client_id"),
            ("idx_crm_interactions_order", "order_id"),
            ("idx_crm_interactions_event_type", "event_type"),
            ("idx_crm_interactions_occurred_at", "occurred_at"),
        ],
        "crm_classification_events": [
            ("idx_crm_classification_events_client", "client_id"),
            ("idx_crm_classification_events_created", "created_at"),
        ],
        "crm_reengagement_tasks": [
            ("idx_crm_reengagement_client", "client_id"),
            ("idx_crm_reengagement_status", "status"),
            ("idx_crm_reengagement_scheduled", "scheduled_for"),
        ],
        "order_status_events": [
            ("idx_order_status_events_order", "order_id"),
            ("idx_order_status_events_status", "to_status"),
            ("idx_order_status_events_created", "created_at"),
        ],
    }
