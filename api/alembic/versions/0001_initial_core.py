"""Initial core migration: tenants, users, refresh_tokens, api_keys, audit_log with triggers

Revision ID: 0001
Revises: 
Create Date: 2026-11-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Tenants Table
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_tenants_code', 'tenants', ['code'])

    # 2. Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='ur'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])

    # 3. Refresh Tokens Table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])

    # 4. API Keys Table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_prefix', sa.String(length=16), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])

    # 5. Audit Log Table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('actor_type', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.String(length=64), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('acting_as', sa.String(length=64), nullable=True),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('prev_hash', sa.String(length=64), nullable=False),
        sa.Column('hash', sa.String(length=64), nullable=False),
        sa.Column('canonical_payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_log_tenant_id', 'audit_log', ['tenant_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_hash', 'audit_log', ['hash'])
    op.create_index('ix_audit_log_request_id', 'audit_log', ['request_id'])

    # Install insert-only triggers for SQLite and PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS audit_log_block_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log is insert-only');
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS audit_log_block_delete
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log is insert-only');
        END;
        """)
    elif bind.dialect.name == 'postgresql':
        op.execute("""
        CREATE OR REPLACE FUNCTION block_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is insert-only';
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS audit_log_block_update ON audit_log;
        CREATE TRIGGER audit_log_block_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION block_audit_log_modification();

        DROP TRIGGER IF EXISTS audit_log_block_delete ON audit_log;
        CREATE TRIGGER audit_log_block_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION block_audit_log_modification();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        op.execute("DROP TRIGGER IF EXISTS audit_log_block_update;")
        op.execute("DROP TRIGGER IF EXISTS audit_log_block_delete;")
    elif bind.dialect.name == 'postgresql':
        op.execute("DROP TRIGGER IF EXISTS audit_log_block_update ON audit_log;")
        op.execute("DROP TRIGGER IF EXISTS audit_log_block_delete ON audit_log;")
        op.execute("DROP FUNCTION IF EXISTS block_audit_log_modification();")

    op.drop_table('audit_log')
    op.drop_table('api_keys')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    op.drop_table('tenants')
