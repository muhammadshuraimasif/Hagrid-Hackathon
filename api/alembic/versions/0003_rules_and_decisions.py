"""Rules and Decisions migration: rule_sets, decisions, immutability triggers

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Rule Sets Table
    op.create_table(
        'rule_sets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('author', sa.String(length=255), nullable=False),
        sa.Column('effective_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('twin_report', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('tenant_id', 'version', name='uq_rule_sets_tenant_version')
    )
    op.create_index('ix_rule_sets_tenant_id', 'rule_sets', ['tenant_id'])
    op.create_index('ix_rule_sets_status', 'rule_sets', ['status'])
    op.create_index('ix_rule_sets_content_hash', 'rule_sets', ['content_hash'])

    # 2. Decisions Table
    op.create_table(
        'decisions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.String(length=36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_version_id', sa.String(length=36), sa.ForeignKey('rule_sets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('rule_version', sa.Integer(), nullable=False),
        sa.Column('rule_hash', sa.String(length=64), nullable=False),
        sa.Column('route', sa.String(length=32), nullable=False),
        sa.Column('p', sa.Float(), nullable=False),
        sa.Column('expected_cost', sa.Float(), nullable=False),
        sa.Column('input_snapshot', sa.JSON(), nullable=False),
        sa.Column('trace', sa.JSON(), nullable=False),
        sa.Column('citizen_reason', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_decisions_tenant_id', 'decisions', ['tenant_id'])
    op.create_index('ix_decisions_case_id', 'decisions', ['case_id'])
    op.create_index('ix_decisions_rule_version_id', 'decisions', ['rule_version_id'])
    op.create_index('ix_decisions_route', 'decisions', ['route'])
    op.create_index('ix_decisions_created_at', 'decisions', ['created_at'])

    # 3. DB Triggers for Immutability of Published Rule Sets
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS rule_sets_block_published_update
        BEFORE UPDATE ON rule_sets
        BEGIN
            SELECT CASE
                WHEN OLD.status = 'published' AND (
                    NEW.status NOT IN ('published', 'retired') OR
                    NEW.definition != OLD.definition OR
                    NEW.content_hash != OLD.content_hash OR
                    NEW.version != OLD.version
                )
                THEN RAISE(ABORT, 'Published rule sets are immutable')
                WHEN OLD.status = 'retired'
                THEN RAISE(ABORT, 'Retired rule sets are immutable')
            END;
        END;
        """)
        op.execute("""
        CREATE TRIGGER IF NOT EXISTS rule_sets_block_published_delete
        BEFORE DELETE ON rule_sets
        BEGIN
            SELECT CASE
                WHEN OLD.status IN ('published', 'retired')
                THEN RAISE(ABORT, 'Published rule sets cannot be deleted')
            END;
        END;
        """)
    elif dialect == 'postgresql':
        op.execute("""
        CREATE OR REPLACE FUNCTION block_rule_sets_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'published' AND (
                NEW.status NOT IN ('published', 'retired') OR
                NEW.definition::text != OLD.definition::text OR
                NEW.content_hash != OLD.content_hash OR
                NEW.version != OLD.version
            ) THEN
                RAISE EXCEPTION 'Published rule sets are immutable';
            END IF;
            IF OLD.status = 'retired' THEN
                RAISE EXCEPTION 'Retired rule sets are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER rule_sets_block_published_update
        BEFORE UPDATE ON rule_sets
        FOR EACH ROW EXECUTE FUNCTION block_rule_sets_modification();

        CREATE OR REPLACE FUNCTION block_rule_sets_deletion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IN ('published', 'retired') THEN
                RAISE EXCEPTION 'Published rule sets cannot be deleted';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER rule_sets_block_published_delete
        BEFORE DELETE ON rule_sets
        FOR EACH ROW EXECUTE FUNCTION block_rule_sets_deletion();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        op.execute("DROP TRIGGER IF EXISTS rule_sets_block_published_update;")
        op.execute("DROP TRIGGER IF EXISTS rule_sets_block_published_delete;")
    elif dialect == 'postgresql':
        op.execute("DROP TRIGGER IF EXISTS rule_sets_block_published_update ON rule_sets;")
        op.execute("DROP FUNCTION IF EXISTS block_rule_sets_modification();")
        op.execute("DROP TRIGGER IF EXISTS rule_sets_block_published_delete ON rule_sets;")
        op.execute("DROP FUNCTION IF EXISTS block_rule_sets_deletion();")

    op.drop_table('decisions')
    op.drop_table('rule_sets')
