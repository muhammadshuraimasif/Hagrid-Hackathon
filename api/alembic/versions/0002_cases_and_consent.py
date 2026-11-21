"""Cases and Consent migration: persons, cases, case_events, documents, helper_grants, consents, consent_events

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Persons Table
    op.create_table(
        'persons',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cnic_encrypted', sa.Text(), nullable=False),
        sa.Column('cnic_hash', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('canonical_name', sa.String(length=255), nullable=False),
        sa.Column('father_name', sa.String(length=255), nullable=True),
        sa.Column('dob', sa.String(length=32), nullable=True),
        sa.Column('field_states', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_persons_tenant_id', 'persons', ['tenant_id'])
    op.create_index('ix_persons_user_id', 'persons', ['user_id'])
    op.create_index('ix_persons_cnic_hash', 'persons', ['cnic_hash'])
    op.create_index('ix_persons_canonical_name', 'persons', ['canonical_name'])

    # 2. Cases Table
    op.create_table(
        'cases',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', sa.String(length=36), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('creator_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_officer_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT'),
        sa.Column('step_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_cases_tenant_id', 'cases', ['tenant_id'])
    op.create_index('ix_cases_person_id', 'cases', ['person_id'])
    op.create_index('ix_cases_creator_user_id', 'cases', ['creator_user_id'])
    op.create_index('ix_cases_assigned_officer_id', 'cases', ['assigned_officer_id'])
    op.create_index('ix_cases_status', 'cases', ['status'])

    # 3. Case Events Table
    op.create_table(
        'case_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('case_id', sa.String(length=36), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_uuid', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_case_events_case_id', 'case_events', ['case_id'])
    op.create_index('ix_case_events_tenant_id', 'case_events', ['tenant_id'])
    op.create_index('ix_case_events_event_type', 'case_events', ['event_type'])
    op.create_unique_constraint('uq_case_event_client_uuid', 'case_events', ['case_id', 'client_uuid'])

    # 4. Documents Table
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.String(length=36), sa.ForeignKey('cases.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploader_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('storage_path', sa.String(length=512), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('chunks_received', sa.JSON(), nullable=False),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_documents_tenant_id', 'documents', ['tenant_id'])
    op.create_index('ix_documents_case_id', 'documents', ['case_id'])
    op.create_index('ix_documents_uploader_id', 'documents', ['uploader_id'])

    # 5. Helper Grants Table
    op.create_table(
        'helper_grants',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('helper_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', sa.String(length=36), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('receipt_id', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_helper_grants_tenant_id', 'helper_grants', ['tenant_id'])
    op.create_index('ix_helper_grants_helper_user_id', 'helper_grants', ['helper_user_id'])
    op.create_index('ix_helper_grants_person_id', 'helper_grants', ['person_id'])

    # 6. Consents Table
    op.create_table(
        'consents',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', sa.String(length=36), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('granted_to_type', sa.String(length=32), nullable=False),
        sa.Column('granted_to_id', sa.String(length=36), nullable=True),
        sa.Column('scope', sa.JSON(), nullable=False),
        sa.Column('purpose', sa.String(length=255), nullable=False),
        sa.Column('expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('receipt_id', sa.String(length=64), nullable=False),
        sa.Column('epoch', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_consents_tenant_id', 'consents', ['tenant_id'])
    op.create_index('ix_consents_person_id', 'consents', ['person_id'])

    # 7. Consent Events Table
    op.create_table(
        'consent_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('consent_id', sa.String(length=36), sa.ForeignKey('consents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('person_id', sa.String(length=36), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('epoch', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_consent_events_tenant_id', 'consent_events', ['tenant_id'])
    op.create_index('ix_consent_events_consent_id', 'consent_events', ['consent_id'])
    op.create_index('ix_consent_events_person_id', 'consent_events', ['person_id'])


def downgrade() -> None:
    op.drop_table('consent_events')
    op.drop_table('consents')
    op.drop_table('helper_grants')
    op.drop_table('documents')
    op.drop_table('case_events')
    op.drop_table('cases')
    op.drop_table('persons')
