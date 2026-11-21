"""Decision Engine & Evaluation Harness migration: eval_runs, eval_results, and decision enhancements

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Enhance decisions table with input_hash, tau, decision_token, payment_reference, hold_expires_at
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.add_column(sa.Column('input_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('tau', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('decision_token', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('payment_reference', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('hold_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_decisions_input_hash', ['input_hash'])

    # 2. Create eval_runs table
    op.create_table(
        'eval_runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('total_cases', sa.Integer(), nullable=False),
        sa.Column('split_counts', sa.JSON(), nullable=False),
        sa.Column('tau_chosen', sa.Float(), nullable=False),
        sa.Column('clopper_pearson_upper', sa.Float(), nullable=False),
        sa.Column('wrong_approval_rate', sa.Float(), nullable=False),
        sa.Column('test_metrics', sa.JSON(), nullable=False),
        sa.Column('is_latest', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_eval_runs_is_latest', 'eval_runs', ['is_latest'])
    op.create_index('ix_eval_runs_created_at', 'eval_runs', ['created_at'])

    # 3. Create eval_results table
    op.create_table(
        'eval_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('eval_run_id', sa.String(length=36), sa.ForeignKey('eval_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('split', sa.String(length=16), nullable=False),
        sa.Column('case_id', sa.String(length=64), nullable=False),
        sa.Column('ground_truth_eligible', sa.Boolean(), nullable=False),
        sa.Column('ground_truth_fraud', sa.Boolean(), nullable=False),
        sa.Column('raw_c', sa.Float(), nullable=False),
        sa.Column('calibrated_p', sa.Float(), nullable=False),
        sa.Column('route', sa.String(length=32), nullable=False),
        sa.Column('ask_target', sa.String(length=64), nullable=True),
        sa.Column('ask_rounds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('cost', sa.Float(), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('name_variant_group', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_eval_results_eval_run_id', 'eval_results', ['eval_run_id'])
    op.create_index('ix_eval_results_split', 'eval_results', ['split'])
    op.create_index('ix_eval_results_case_id', 'eval_results', ['case_id'])
    op.create_index('ix_eval_results_route', 'eval_results', ['route'])


def downgrade() -> None:
    op.drop_table('eval_results')
    op.drop_table('eval_runs')
    with op.batch_alter_table('decisions') as batch_op:
        batch_op.drop_index('ix_decisions_input_hash')
        batch_op.drop_column('hold_expires_at')
        batch_op.drop_column('payment_reference')
        batch_op.drop_column('decision_token')
        batch_op.drop_column('tau')
        batch_op.drop_column('input_hash')
