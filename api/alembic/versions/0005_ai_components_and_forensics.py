"""AI Components & Forensics migration: model_calls, document_analyses, scam_scans, scam_verifications

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. model_calls
    op.create_table(
        'model_calls',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('prompt_version', sa.String(length=32), nullable=False),
        sa.Column('input_hash', sa.String(length=64), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('cost_estimate', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_model_calls_model', 'model_calls', ['model'])
    op.create_index('ix_model_calls_input_hash', 'model_calls', ['input_hash'])
    op.create_index('ix_model_calls_ok', 'model_calls', ['ok'])

    # 2. document_analyses
    op.create_table(
        'document_analyses',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.String(length=36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', sa.String(length=36), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('fields', sa.JSON(), nullable=False),
        sa.Column('field_confidences', sa.JSON(), nullable=False),
        sa.Column('blur_score', sa.Float(), nullable=False),
        sa.Column('authenticity_score', sa.Float(), nullable=False),
        sa.Column('qr_result', sa.JSON(), nullable=False),
        sa.Column('suspect_boxes', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_document_analyses_case_id', 'document_analyses', ['case_id'])

    # 3. scam_scans
    op.create_table(
        'scam_scans',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('message_hash', sa.String(length=64), nullable=False),
        sa.Column('redacted_text', sa.Text(), nullable=False),
        sa.Column('verdict', sa.String(length=32), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('red_flags', sa.JSON(), nullable=False),
        sa.Column('voter_breakdown', sa.JSON(), nullable=False),
        sa.Column('feedback', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_scam_scans_message_hash', 'scam_scans', ['message_hash'])
    op.create_index('ix_scam_scans_verdict', 'scam_scans', ['verdict'])

    # 4. scam_verifications
    op.create_table(
        'scam_verifications',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False, unique=True),
        sa.Column('case_id', sa.String(length=36), sa.ForeignKey('cases.id', ondelete='SET NULL'), nullable=True),
        sa.Column('recipient_masked', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_scam_verifications_code', 'scam_verifications', ['code'])

def downgrade() -> None:
    op.drop_table('scam_verifications')
    op.drop_table('scam_scans')
    op.drop_table('document_analyses')
    op.drop_table('model_calls')
