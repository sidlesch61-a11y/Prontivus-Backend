"""Add TISS Multi-Convênio tables

Revision ID: 0004_tiss_multi_convenio
Revises: 0003_digital_prescriptions
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004_tiss_multi_convenio'
down_revision = '0003_digital_prescriptions'
branch_labels = None
depends_on = None


def upgrade():
    """Add TISS Multi-Convênio tables."""
    
    # Create tiss_providers table
    op.create_table('tiss_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('cnpj', sa.String(), nullable=False),
        sa.Column('endpoint_url', sa.String(), nullable=False),
        sa.Column('environment', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('password_encrypted', sa.String(), nullable=False),
        sa.Column('certificate_path', sa.String(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('last_test_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_successful_request', sa.DateTime(timezone=True), nullable=True),
        sa.Column('config_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create tiss_jobs table
    op.create_table('tiss_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_type', sa.String(), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('procedure_code', sa.String(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('response_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ethical_lock_type', sa.String(), nullable=True),
        sa.Column('ethical_lock_reason', sa.Text(), nullable=True),
        sa.Column('manual_review_required', sa.Boolean(), nullable=False),
        sa.Column('job_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['tiss_providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create tiss_logs table
    op.create_table('tiss_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('level', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('request_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('response_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('response_status_code', sa.Integer(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('operation', sa.String(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['tiss_providers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['tiss_jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create tiss_ethical_locks table
    op.create_table('tiss_ethical_locks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lock_type', sa.String(), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('procedure_code', sa.String(), nullable=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('conflicting_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('manual_review_required', sa.Boolean(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('lock_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['conflicting_job_id'], ['tiss_jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for tiss_providers
    op.create_index('idx_tiss_providers_clinic', 'tiss_providers', ['clinic_id'])
    op.create_index('idx_tiss_providers_code', 'tiss_providers', ['clinic_id', 'code'], unique=True)
    op.create_index('idx_tiss_providers_status', 'tiss_providers', ['status'])
    op.create_index('idx_tiss_providers_environment', 'tiss_providers', ['environment'])
    
    # Create indexes for tiss_jobs
    op.create_index('idx_tiss_jobs_clinic', 'tiss_jobs', ['clinic_id'])
    op.create_index('idx_tiss_jobs_provider', 'tiss_jobs', ['provider_id'])
    op.create_index('idx_tiss_jobs_status', 'tiss_jobs', ['status'])
    op.create_index('idx_tiss_jobs_type', 'tiss_jobs', ['job_type'])
    op.create_index('idx_tiss_jobs_invoice', 'tiss_jobs', ['invoice_id'])
    op.create_index('idx_tiss_jobs_scheduled', 'tiss_jobs', ['scheduled_at'])
    op.create_index('idx_tiss_jobs_retry', 'tiss_jobs', ['next_retry_at'])
    op.create_index('idx_tiss_jobs_priority', 'tiss_jobs', ['priority'])
    
    # Create indexes for tiss_logs
    op.create_index('idx_tiss_logs_clinic', 'tiss_logs', ['clinic_id'])
    op.create_index('idx_tiss_logs_provider', 'tiss_logs', ['provider_id'])
    op.create_index('idx_tiss_logs_job', 'tiss_logs', ['job_id'])
    op.create_index('idx_tiss_logs_level', 'tiss_logs', ['level'])
    op.create_index('idx_tiss_logs_operation', 'tiss_logs', ['operation'])
    op.create_index('idx_tiss_logs_created', 'tiss_logs', ['created_at'])
    
    # Create indexes for tiss_ethical_locks
    op.create_index('idx_tiss_ethical_locks_clinic', 'tiss_ethical_locks', ['clinic_id'])
    op.create_index('idx_tiss_ethical_locks_type', 'tiss_ethical_locks', ['lock_type'])
    op.create_index('idx_tiss_ethical_locks_invoice', 'tiss_ethical_locks', ['invoice_id'])
    op.create_index('idx_tiss_ethical_locks_patient', 'tiss_ethical_locks', ['patient_id'])
    op.create_index('idx_tiss_ethical_locks_resolved', 'tiss_ethical_locks', ['resolved'])
    op.create_index('idx_tiss_ethical_locks_created', 'tiss_ethical_locks', ['created_at'])
    
    # Create unique constraints for ethical locks
    op.create_unique_constraint(
        'uq_tiss_jobs_clinic_invoice_procedure',
        'tiss_jobs',
        ['clinic_id', 'invoice_id', 'procedure_code'],
        postgresql_where=sa.text("status != 'rejected'")
    )
    
    # Add check constraints
    op.create_check_constraint(
        'ck_tiss_providers_status',
        'tiss_providers',
        "status IN ('active', 'inactive', 'suspended', 'testing')"
    )
    
    op.create_check_constraint(
        'ck_tiss_jobs_status',
        'tiss_jobs',
        "status IN ('pending', 'processing', 'sent', 'accepted', 'rejected', 'failed', 'cancelled', 'manual_review')"
    )
    
    op.create_check_constraint(
        'ck_tiss_jobs_type',
        'tiss_jobs',
        "job_type IN ('invoice', 'sadt', 'consultation', 'procedure')"
    )
    
    op.create_check_constraint(
        'ck_tiss_logs_level',
        'tiss_logs',
        "level IN ('info', 'warning', 'error', 'debug')"
    )
    
    op.create_check_constraint(
        'ck_tiss_ethical_locks_type',
        'tiss_ethical_locks',
        "lock_type IN ('duplicate_invoice', 'cid_collision', 'procedure_collision', 'patient_collision')"
    )
    
    # Create triggers for updated_at
    op.execute("""
        CREATE TRIGGER trg_tiss_providers_set_updated_at
        BEFORE UPDATE ON tiss_providers
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_tiss_jobs_set_updated_at
        BEFORE UPDATE ON tiss_jobs
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_tiss_ethical_locks_set_updated_at
        BEFORE UPDATE ON tiss_ethical_locks
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade():
    """Remove TISS Multi-Convênio tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_tiss_ethical_locks_set_updated_at ON tiss_ethical_locks;")
    op.execute("DROP TRIGGER IF EXISTS trg_tiss_jobs_set_updated_at ON tiss_jobs;")
    op.execute("DROP TRIGGER IF EXISTS trg_tiss_providers_set_updated_at ON tiss_providers;")
    
    # Drop check constraints
    op.drop_constraint('ck_tiss_ethical_locks_type', 'tiss_ethical_locks', type_='check')
    op.drop_constraint('ck_tiss_logs_level', 'tiss_logs', type_='check')
    op.drop_constraint('ck_tiss_jobs_type', 'tiss_jobs', type_='check')
    op.drop_constraint('ck_tiss_jobs_status', 'tiss_jobs', type_='check')
    op.drop_constraint('ck_tiss_providers_status', 'tiss_providers', type_='check')
    
    # Drop unique constraints
    op.drop_constraint('uq_tiss_jobs_clinic_invoice_procedure', 'tiss_jobs', type_='unique')
    
    # Drop indexes
    op.drop_index('idx_tiss_ethical_locks_created', table_name='tiss_ethical_locks')
    op.drop_index('idx_tiss_ethical_locks_resolved', table_name='tiss_ethical_locks')
    op.drop_index('idx_tiss_ethical_locks_patient', table_name='tiss_ethical_locks')
    op.drop_index('idx_tiss_ethical_locks_invoice', table_name='tiss_ethical_locks')
    op.drop_index('idx_tiss_ethical_locks_type', table_name='tiss_ethical_locks')
    op.drop_index('idx_tiss_ethical_locks_clinic', table_name='tiss_ethical_locks')
    
    op.drop_index('idx_tiss_logs_created', table_name='tiss_logs')
    op.drop_index('idx_tiss_logs_operation', table_name='tiss_logs')
    op.drop_index('idx_tiss_logs_level', table_name='tiss_logs')
    op.drop_index('idx_tiss_logs_job', table_name='tiss_logs')
    op.drop_index('idx_tiss_logs_provider', table_name='tiss_logs')
    op.drop_index('idx_tiss_logs_clinic', table_name='tiss_logs')
    
    op.drop_index('idx_tiss_jobs_priority', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_retry', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_scheduled', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_invoice', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_type', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_status', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_provider', table_name='tiss_jobs')
    op.drop_index('idx_tiss_jobs_clinic', table_name='tiss_jobs')
    
    op.drop_index('idx_tiss_providers_environment', table_name='tiss_providers')
    op.drop_index('idx_tiss_providers_status', table_name='tiss_providers')
    op.drop_index('idx_tiss_providers_code', table_name='tiss_providers')
    op.drop_index('idx_tiss_providers_clinic', table_name='tiss_providers')
    
    # Drop tables
    op.drop_table('tiss_ethical_locks')
    op.drop_table('tiss_logs')
    op.drop_table('tiss_jobs')
    op.drop_table('tiss_providers')
