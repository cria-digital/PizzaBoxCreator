"""add audit_log table and enable multi-user admin_account

Revision ID: 68d32d782435
Revises: 9c9d5c013d3d
Create Date: 2026-08-19
"""
from alembic import context, op
import sqlalchemy as sa

revision = '68d32d782435'
down_revision = '9c9d5c013d3d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.execute("ALTER TABLE admin_account DROP CONSTRAINT IF EXISTS admin_account_id_check")
        op.execute("ALTER TABLE admin_account DROP CONSTRAINT IF EXISTS admin_single_row")
        op.execute(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_by VARCHAR"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS audit_log ("
            "id SERIAL PRIMARY KEY, "
            "order_id INTEGER REFERENCES orders(id), "
            "username VARCHAR NOT NULL, "
            "action VARCHAR NOT NULL, "
            "details JSON, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_log_order ON audit_log (order_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (username)"
        )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_account_username "
            "ON admin_account (username)"
        )
        return

    # Allow multiple admin users (remove single-row constraint if it exists).
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    dialect = conn.dialect.name

    if dialect == "postgresql":
        constraints = conn.execute(sa.text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'admin_account'::regclass AND contype = 'c'"
        )).scalars().all()
        for constraint_name in constraints:
            op.drop_constraint(constraint_name, 'admin_account', type_='check')

        has_unique_username = conn.execute(sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = 'admin_account' "
            "AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%username%'"
        )).scalar()
        if not has_unique_username:
            op.create_unique_constraint('uq_admin_account_username', 'admin_account', ['username'])

    # Track who created each order (idempotent).
    has_col = "created_by" in {col["name"] for col in inspector.get_columns("orders")}
    if not has_col:
        op.add_column('orders', sa.Column('created_by', sa.String(), nullable=True))

    # Audit log: immutable record of who did what and when (idempotent).
    if "audit_log" not in set(inspector.get_table_names()):
        op.create_table(
            'audit_log',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=True),
            sa.Column('username', sa.String(), nullable=False),
            sa.Column('action', sa.String(), nullable=False),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
        )
        op.create_index('idx_audit_log_order', 'audit_log', ['order_id'], unique=False)
        op.create_index('idx_audit_log_user', 'audit_log', ['username'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_audit_log_user', table_name='audit_log')
    op.drop_index('idx_audit_log_order', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_column('orders', 'created_by')
    op.create_check_constraint('admin_account_id_check', 'admin_account', 'id = 1')
