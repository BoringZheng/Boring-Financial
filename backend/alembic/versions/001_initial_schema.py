"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-14 22:56:04.792825

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('email', sa.String(255), nullable=True, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('preferences', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('name', sa.String(128), nullable=False, index=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'category_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('subcategory_name', sa.String(128), nullable=True),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('merchant_pattern', sa.String(255), nullable=True),
        sa.Column('keyword_pattern', sa.String(255), nullable=True),
        sa.Column('is_regex', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'import_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('status', sa.String(32), default='queued'),
        sa.Column('source_count', sa.Integer(), default=0),
        sa.Column('total_count', sa.Integer(), default=0),
        sa.Column('processed_count', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'uploaded_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('import_batches.id'), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('stored_path', sa.String(500), nullable=False),
        sa.Column('platform', sa.String(32), nullable=True),
        sa.Column('status', sa.String(32), default='queued'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('import_batches.id'), nullable=False, index=True),
        sa.Column('uploaded_file_id', sa.Integer(), sa.ForeignKey('uploaded_files.id'), nullable=True),
        sa.Column('platform', sa.String(32), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=False), nullable=False, index=True),
        sa.Column('type', sa.String(32), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(8), default='CNY'),
        sa.Column('merchant', sa.String(255), nullable=True),
        sa.Column('item', sa.String(255), nullable=True),
        sa.Column('method', sa.String(128), nullable=True),
        sa.Column('status', sa.String(128), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('merchant_norm', sa.String(255), default=''),
        sa.Column('item_norm', sa.String(255), default=''),
        sa.Column('note_norm', sa.Text(), default=''),
        sa.Column('dedupe_hash', sa.String(64), nullable=False, index=True),
        sa.Column('auto_category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('auto_subcategory_name', sa.String(128), nullable=True),
        sa.Column('auto_confidence', sa.Numeric(5, 4), nullable=True),
        sa.Column('auto_provider', sa.String(64), nullable=True),
        sa.Column('auto_reason', sa.Text(), nullable=True),
        sa.Column('final_category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('needs_review', sa.Boolean(), default=True),
        sa.Column('api_retry_count', sa.Integer(), default=0),
        sa.Column('api_retry_provider', sa.String(64), nullable=True),
        sa.Column('api_retry_last_error', sa.Text(), nullable=True),
        sa.Column('requeue_batch_ts', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('user_id', 'dedupe_hash', name='uq_user_transaction_hash'),
    )

    op.create_table(
        'classification_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id'), nullable=False, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('subcategory_name', sa.String(128), nullable=True),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('prompt_version', sa.String(32), default='v1'),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'classification_caches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('text_hash', sa.String(64), nullable=False, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('subcategory_name', sa.String(128), nullable=True),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'provider', 'text_hash', name='uq_user_provider_cache_hash'),
    )

    op.create_table(
        'report_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('status', sa.String(32), default='queued'),
        sa.Column('date_from', sa.DateTime(timezone=False), nullable=True),
        sa.Column('date_to', sa.DateTime(timezone=False), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'generated_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('report_jobs.id'), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('plan', sa.String(64), default='free', nullable=True),
        sa.Column('subscription_status', sa.String(32), default='active', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'organization_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('role', sa.String(16), default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),
    )


def downgrade() -> None:
    op.drop_table('organization_members')
    op.drop_table('organizations')
    op.drop_table('generated_reports')
    op.drop_table('report_jobs')
    op.drop_table('classification_caches')
    op.drop_table('classification_results')
    op.drop_table('transactions')
    op.drop_table('uploaded_files')
    op.drop_table('import_batches')
    op.drop_table('category_rules')
    op.drop_table('categories')
    op.drop_table('users')
