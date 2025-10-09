"""Add telemedicine tables

Revision ID: 0005_telemedicine_tables
Revises: 0004_tiss_multi_convenio
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0005_telemedicine_tables'
down_revision = '0004_tiss_multi_convenio'
branch_labels = None
depends_on = None


def upgrade():
    """Create telemedicine tables."""
    
    # Create telemed_sessions table
    op.create_table('telemed_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('link_token', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('room_id', sa.String(), nullable=False),
        sa.Column('allow_recording', sa.Boolean(), nullable=False, default=False),
        sa.Column('recording_encrypted', sa.Boolean(), nullable=False, default=True),
        sa.Column('max_duration_minutes', sa.Integer(), nullable=False, default=60),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actual_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='scheduled'),
        sa.Column('doctor_consent', sa.Boolean(), nullable=True),
        sa.Column('patient_consent', sa.Boolean(), nullable=True),
        sa.Column('consent_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recording_file_path', sa.String(), nullable=True),
        sa.Column('recording_file_size', sa.Integer(), nullable=True),
        sa.Column('recording_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('recording_encryption_key', sa.String(), nullable=True),
        sa.Column('sfu_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('turn_credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('session_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE')
    )
    
    # Create indexes for telemed_sessions
    op.create_index('idx_telemed_sessions_clinic_id', 'telemed_sessions', ['clinic_id'])
    op.create_index('idx_telemed_sessions_appointment_id', 'telemed_sessions', ['appointment_id'])
    op.create_index('idx_telemed_sessions_doctor_id', 'telemed_sessions', ['doctor_id'])
    op.create_index('idx_telemed_sessions_patient_id', 'telemed_sessions', ['patient_id'])
    op.create_index('idx_telemed_sessions_link_token', 'telemed_sessions', ['link_token'], unique=True)
    op.create_index('idx_telemed_sessions_session_id', 'telemed_sessions', ['session_id'], unique=True)
    op.create_index('idx_telemed_sessions_status', 'telemed_sessions', ['status'])
    op.create_index('idx_telemed_sessions_scheduled_start', 'telemed_sessions', ['scheduled_start'])
    op.create_index('idx_telemed_sessions_created_at', 'telemed_sessions', ['created_at'])
    
    # Create telemed_session_logs table
    op.create_table('telemed_session_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_role', sa.String(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('message', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['telemed_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes for telemed_session_logs
    op.create_index('idx_telemed_session_logs_session_id', 'telemed_session_logs', ['session_id'])
    op.create_index('idx_telemed_session_logs_clinic_id', 'telemed_session_logs', ['clinic_id'])
    op.create_index('idx_telemed_session_logs_event', 'telemed_session_logs', ['event'])
    op.create_index('idx_telemed_session_logs_user_id', 'telemed_session_logs', ['user_id'])
    op.create_index('idx_telemed_session_logs_created_at', 'telemed_session_logs', ['created_at'])
    
    # Create telemed_recordings table
    op.create_table('telemed_recordings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('format', sa.String(), nullable=False, default='webm'),
        sa.Column('encrypted', sa.Boolean(), nullable=False, default=True),
        sa.Column('encryption_key', sa.String(), nullable=True),
        sa.Column('encryption_algorithm', sa.String(), nullable=False, default='AES-256-GCM'),
        sa.Column('processing_status', sa.String(), nullable=False, default='pending'),
        sa.Column('processing_error', sa.String(), nullable=True),
        sa.Column('storage_provider', sa.String(), nullable=False, default='s3'),
        sa.Column('storage_bucket', sa.String(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('recording_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['telemed_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # Create indexes for telemed_recordings
    op.create_index('idx_telemed_recordings_session_id', 'telemed_recordings', ['session_id'])
    op.create_index('idx_telemed_recordings_clinic_id', 'telemed_recordings', ['clinic_id'])
    op.create_index('idx_telemed_recordings_processing_status', 'telemed_recordings', ['processing_status'])
    op.create_index('idx_telemed_recordings_created_at', 'telemed_recordings', ['created_at'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_telemed_sessions_status',
        'telemed_sessions',
        "status IN ('scheduled', 'active', 'ended', 'cancelled', 'failed')"
    )
    
    op.create_check_constraint(
        'ck_telemed_sessions_max_duration',
        'telemed_sessions',
        'max_duration_minutes > 0 AND max_duration_minutes <= 480'
    )
    
    op.create_check_constraint(
        'ck_telemed_session_logs_event',
        'telemed_session_logs',
        "event IN ('created', 'joined', 'left', 'consent_given', 'consent_denied', 'recording_started', 'recording_stopped', 'recording_failed', 'ended', 'error')"
    )
    
    op.create_check_constraint(
        'ck_telemed_session_logs_user_role',
        'telemed_session_logs',
        "user_role IN ('doctor', 'patient', 'admin')"
    )
    
    op.create_check_constraint(
        'ck_telemed_recordings_format',
        'telemed_recordings',
        "format IN ('webm', 'mp4', 'avi', 'mov')"
    )
    
    op.create_check_constraint(
        'ck_telemed_recordings_processing_status',
        'telemed_recordings',
        "processing_status IN ('pending', 'processing', 'encrypted', 'uploaded', 'completed', 'failed')"
    )
    
    op.create_check_constraint(
        'ck_telemed_recordings_storage_provider',
        'telemed_recordings',
        "storage_provider IN ('s3', 'minio', 'local')"
    )
    
    # Add updated_at trigger for telemed_sessions
    op.execute("""
        CREATE TRIGGER trg_telemed_sessions_set_updated_at
        BEFORE UPDATE ON telemed_sessions
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    # Add updated_at trigger for telemed_recordings
    op.execute("""
        CREATE TRIGGER trg_telemed_recordings_set_updated_at
        BEFORE UPDATE ON telemed_recordings
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)


def downgrade():
    """Drop telemedicine tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_telemed_sessions_set_updated_at ON telemed_sessions;")
    op.execute("DROP TRIGGER IF EXISTS trg_telemed_recordings_set_updated_at ON telemed_recordings;")
    
    # Drop check constraints
    op.drop_constraint('ck_telemed_recordings_storage_provider', 'telemed_recordings', type_='check')
    op.drop_constraint('ck_telemed_recordings_processing_status', 'telemed_recordings', type_='check')
    op.drop_constraint('ck_telemed_recordings_format', 'telemed_recordings', type_='check')
    op.drop_constraint('ck_telemed_session_logs_user_role', 'telemed_session_logs', type_='check')
    op.drop_constraint('ck_telemed_session_logs_event', 'telemed_session_logs', type_='check')
    op.drop_constraint('ck_telemed_sessions_max_duration', 'telemed_sessions', type_='check')
    op.drop_constraint('ck_telemed_sessions_status', 'telemed_sessions', type_='check')
    
    # Drop tables
    op.drop_table('telemed_recordings')
    op.drop_table('telemed_session_logs')
    op.drop_table('telemed_sessions')
