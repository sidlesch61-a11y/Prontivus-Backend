"""
Comprehensive CliniCore/Prontivus Database Schema Update
Based on detailed specifications for all approved features.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0011_comprehensive_clinicore_schema'
down_revision = '0010_comprehensive_schema_update'
branch_labels = None
depends_on = None

def upgrade():
    """Create comprehensive CliniCore/Prontivus schema with all features."""
    
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    
    # Utility function for auto-updating timestamps
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$;
    """)
    
    # ========================================
    # 1. CORE UPDATES - Users and Roles
    # ========================================
    
    # Update users table with new features
    op.add_column('users', sa.Column('twofa_enabled', sa.Boolean(), nullable=False, default=False))
    op.add_column('users', sa.Column('twofa_secret', sa.Text(), nullable=True))  # Encrypted
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('crm_number', sa.Text(), nullable=True))  # Only for doctors
    op.add_column('users', sa.Column('signature_cert_ref', sa.Text(), nullable=True))  # A1 cert reference
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, default=True))
    
    # Update roles table for RBAC
    op.add_column('roles', sa.Column('permissions', postgresql.JSONB(), nullable=True, default='[]'))
    
    # Create user_roles junction table
    op.create_table('user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'role_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 2. EMR (Prontuário Eletrônico Avançado)
    # ========================================
    
    # Update patients table
    op.add_column('patients', sa.Column('medical_history', postgresql.JSONB(), nullable=True, default='{}'))
    
    # Update medical_records table
    op.add_column('medical_records', sa.Column('consultation_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('medical_records', sa.Column('anamnese', postgresql.JSONB(), nullable=True))
    op.add_column('medical_records', sa.Column('physical_exam', postgresql.JSONB(), nullable=True))
    op.add_column('medical_records', sa.Column('evolution', postgresql.JSONB(), nullable=True))
    op.add_column('medical_records', sa.Column('conduct', postgresql.JSONB(), nullable=True))
    op.add_column('medical_records', sa.Column('diagnosis', postgresql.JSONB(), nullable=True))  # List of {cid_code, description, confirmed}
    op.add_column('medical_records', sa.Column('attachments_count', sa.Integer(), nullable=False, default=0))
    op.add_column('medical_records', sa.Column('locked', sa.Boolean(), nullable=False, default=False))
    op.add_column('medical_records', sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('medical_records', sa.Column('lock_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('medical_records', sa.Column('status', sa.String(), nullable=False, default='draft'))
    
    # Add foreign key for consultation_id
    op.create_foreign_key('fk_medical_records_consultation', 'medical_records', 'consultations', ['consultation_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_medical_records_locked_by', 'medical_records', 'users', ['locked_by'], ['id'], ondelete='SET NULL')
    
    # Create record_attachments table
    op.create_table('record_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('file_type', sa.Text(), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 3. AI Consultation & Audio Processing
    # ========================================
    
    op.create_table('ai_recordings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consent_given', sa.Boolean(), nullable=False, default=False),
        sa.Column('consent_meta', postgresql.JSONB(), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('duration_sec', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='recording'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_table('ai_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('recording_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transcript_text', sa.Text(), nullable=True),
        sa.Column('summary_json', postgresql.JSONB(), nullable=True),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['recording_id'], ['ai_recordings.id'], ondelete='CASCADE')
    )
    
    op.create_table('ai_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('transcription_model', sa.Text(), nullable=True),
        sa.Column('analysis_model', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('config', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 4. Digital Prescription (PAdES ICP-Brasil + QR Verification)
    # ========================================
    
    op.create_table('prescriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('items', postgresql.JSONB(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='draft'),
        sa.Column('signed_pdf_path', sa.Text(), nullable=True),
        sa.Column('signature_meta', postgresql.JSONB(), nullable=True),
        sa.Column('qr_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_table('prescriptions_audit',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('prescription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 5. TISS Multi-Convênio Integration
    # ========================================
    
    op.create_table('tiss_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('environment', sa.String(), nullable=False),
        sa.Column('wsdl_url', sa.Text(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('password_encrypted', sa.Text(), nullable=False),
        sa.Column('token', sa.Text(), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_test_result', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    op.create_table('tiss_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', sa.Text(), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('procedure_code', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['tiss_providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_table('tiss_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_payload', postgresql.JSONB(), nullable=True),
        sa.Column('response_payload', postgresql.JSONB(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['tiss_jobs.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 6. Health Plan API Integration Panel
    # ========================================
    
    op.create_table('health_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=False),
        sa.Column('client_id', sa.Text(), nullable=False),
        sa.Column('client_secret_encrypted', sa.Text(), nullable=False),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('environment', sa.String(), nullable=False),
        sa.Column('requires_doctor_identification', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_connection_status', sa.String(), nullable=True),
        sa.Column('last_connection_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 7. Native Telemedicine Platform (WebRTC + Recordings + Consent)
    # ========================================
    
    op.create_table('telemed_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('room_token', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='scheduled'),
        sa.Column('allow_recording', sa.Boolean(), nullable=False, default=False),
        sa.Column('recording_path', sa.Text(), nullable=True),
        sa.Column('consent_given', sa.Boolean(), nullable=False, default=False),
        sa.Column('consent_meta', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_sec', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE')
    )
    
    op.create_table('telemed_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event', sa.Text(), nullable=False),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['telemed_sessions.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 8. Waiting Queue & Finalization Flow
    # ========================================
    
    op.create_table('waiting_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='waiting'),
        sa.Column('called_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL')
    )
    
    # ========================================
    # 9. Security, Audit, and Access Control
    # ========================================
    
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('method', sa.Text(), nullable=False),
        sa.Column('entity', sa.Text(), nullable=False),
        sa.Column('entity_id', sa.Text(), nullable=True),
        sa.Column('old_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        sa.Column('ip', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    op.create_table('user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jwt_id', sa.Text(), nullable=False),
        sa.Column('last_ip', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    op.create_table('login_2fa_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('totp_code', sa.Text(), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 10. Offline Sync & Idempotency
    # ========================================
    
    op.create_table('client_sync_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_event_id', sa.Text(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False),
        sa.Column('server_entity_id', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # 11. Trava Ética / Anti-Collision
    # ========================================
    
    op.create_table('edit_locks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.func.gen_random_uuid()),
        sa.Column('entity_type', sa.Text(), nullable=False),
        sa.Column('entity_id', sa.Text(), nullable=False),
        sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lock_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['locked_by'], ['users.id'], ondelete='CASCADE')
    )
    
    # ========================================
    # INDEXES FOR PERFORMANCE
    # ========================================
    
    # Users indexes
    op.create_index('idx_users_twofa_enabled', 'users', ['twofa_enabled'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    op.create_index('idx_users_crm_number', 'users', ['crm_number'])
    op.create_index('idx_users_last_login', 'users', ['last_login_at'])
    
    # Medical records indexes
    op.create_index('idx_medical_records_consultation', 'medical_records', ['consultation_id'])
    op.create_index('idx_medical_records_status', 'medical_records', ['status'])
    op.create_index('idx_medical_records_locked', 'medical_records', ['locked'])
    op.create_index('idx_medical_records_locked_by', 'medical_records', ['locked_by'])
    
    # Record attachments indexes
    op.create_index('idx_record_attachments_record', 'record_attachments', ['record_id'])
    op.create_index('idx_record_attachments_uploaded_by', 'record_attachments', ['uploaded_by'])
    
    # AI recordings indexes
    op.create_index('idx_ai_recordings_consultation', 'ai_recordings', ['consultation_id'])
    op.create_index('idx_ai_recordings_status', 'ai_recordings', ['status'])
    op.create_index('idx_ai_recordings_doctor', 'ai_recordings', ['doctor_id'])
    
    # AI summaries indexes
    op.create_index('idx_ai_summaries_recording', 'ai_summaries', ['recording_id'])
    op.create_index('idx_ai_summaries_status', 'ai_summaries', ['status'])
    op.create_index('idx_ai_summaries_provider', 'ai_summaries', ['provider'])
    
    # AI settings indexes
    op.create_index('idx_ai_settings_clinic', 'ai_settings', ['clinic_id'])
    op.create_index('idx_ai_settings_provider', 'ai_settings', ['provider'])
    op.create_index('idx_ai_settings_active', 'ai_settings', ['active'])
    
    # Prescriptions indexes
    op.create_index('idx_prescriptions_patient', 'prescriptions', ['patient_id'])
    op.create_index('idx_prescriptions_doctor', 'prescriptions', ['doctor_id'])
    op.create_index('idx_prescriptions_status', 'prescriptions', ['status'])
    op.create_index('idx_prescriptions_type', 'prescriptions', ['type'])
    op.create_index('idx_prescriptions_qr_token', 'prescriptions', ['qr_token'])
    
    # Prescriptions audit indexes
    op.create_index('idx_prescriptions_audit_prescription', 'prescriptions_audit', ['prescription_id'])
    op.create_index('idx_prescriptions_audit_user', 'prescriptions_audit', ['user_id'])
    op.create_index('idx_prescriptions_audit_event', 'prescriptions_audit', ['event'])
    
    # TISS providers indexes
    op.create_index('idx_tiss_providers_clinic', 'tiss_providers', ['clinic_id'])
    op.create_index('idx_tiss_providers_active', 'tiss_providers', ['active'])
    op.create_index('idx_tiss_providers_environment', 'tiss_providers', ['environment'])
    
    # TISS jobs indexes
    op.create_index('idx_tiss_jobs_clinic', 'tiss_jobs', ['clinic_id'])
    op.create_index('idx_tiss_jobs_provider', 'tiss_jobs', ['provider_id'])
    op.create_index('idx_tiss_jobs_status', 'tiss_jobs', ['status'])
    op.create_index('idx_tiss_jobs_invoice', 'tiss_jobs', ['invoice_id'])
    op.create_index('idx_tiss_jobs_patient', 'tiss_jobs', ['patient_id'])
    
    # TISS logs indexes
    op.create_index('idx_tiss_logs_job', 'tiss_logs', ['job_id'])
    op.create_index('idx_tiss_logs_status_code', 'tiss_logs', ['status_code'])
    
    # Health providers indexes
    op.create_index('idx_health_providers_clinic', 'health_providers', ['clinic_id'])
    op.create_index('idx_health_providers_active', 'health_providers', ['active'])
    op.create_index('idx_health_providers_environment', 'health_providers', ['environment'])
    
    # Telemed sessions indexes
    op.create_index('idx_telemed_sessions_appointment', 'telemed_sessions', ['appointment_id'])
    op.create_index('idx_telemed_sessions_status', 'telemed_sessions', ['status'])
    op.create_index('idx_telemed_sessions_room_token', 'telemed_sessions', ['room_token'])
    op.create_index('idx_telemed_sessions_doctor', 'telemed_sessions', ['doctor_id'])
    op.create_index('idx_telemed_sessions_patient', 'telemed_sessions', ['patient_id'])
    
    # Telemed logs indexes
    op.create_index('idx_telemed_logs_session', 'telemed_logs', ['session_id'])
    op.create_index('idx_telemed_logs_event', 'telemed_logs', ['event'])
    
    # Waiting queue indexes
    op.create_index('idx_waiting_queue_clinic', 'waiting_queue', ['clinic_id'])
    op.create_index('idx_waiting_queue_doctor', 'waiting_queue', ['doctor_id'])
    op.create_index('idx_waiting_queue_status', 'waiting_queue', ['status'])
    op.create_index('idx_waiting_queue_position', 'waiting_queue', ['position'])
    op.create_index('idx_waiting_queue_clinic_doctor_status', 'waiting_queue', ['clinic_id', 'doctor_id', 'status'])
    
    # Audit logs indexes
    op.create_index('idx_audit_logs_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_clinic', 'audit_logs', ['clinic_id'])
    op.create_index('idx_audit_logs_entity', 'audit_logs', ['entity'])
    op.create_index('idx_audit_logs_created', 'audit_logs', ['created_at'])
    
    # User sessions indexes
    op.create_index('idx_user_sessions_user', 'user_sessions', ['user_id'])
    op.create_index('idx_user_sessions_jwt_id', 'user_sessions', ['jwt_id'])
    op.create_index('idx_user_sessions_expires', 'user_sessions', ['expires_at'])
    
    # 2FA codes indexes
    op.create_index('idx_login_2fa_codes_user', 'login_2fa_codes', ['user_id'])
    op.create_index('idx_login_2fa_codes_valid_until', 'login_2fa_codes', ['valid_until'])
    op.create_index('idx_login_2fa_codes_used', 'login_2fa_codes', ['used'])
    
    # Sync events indexes
    op.create_index('idx_client_sync_events_clinic', 'client_sync_events', ['clinic_id'])
    op.create_index('idx_client_sync_events_client_id', 'client_sync_events', ['client_event_id'])
    op.create_index('idx_client_sync_events_type', 'client_sync_events', ['event_type'])
    op.create_index('idx_client_sync_events_processed', 'client_sync_events', ['processed'])
    op.create_index('idx_client_sync_events_idempotency', 'client_sync_events', ['idempotency_key'])
    
    # Edit locks indexes
    op.create_index('idx_edit_locks_entity', 'edit_locks', ['entity_type', 'entity_id'])
    op.create_index('idx_edit_locks_locked_by', 'edit_locks', ['locked_by'])
    op.create_index('idx_edit_locks_active', 'edit_locks', ['active'])
    op.create_index('idx_edit_locks_expires', 'edit_locks', ['lock_expires_at'])
    
    # ========================================
    # UNIQUE CONSTRAINTS FOR IDEMPOTENCY
    # ========================================
    
    # Sync events idempotency
    op.create_unique_index('ux_client_sync_events_clinic_client_id', 'client_sync_events', ['clinic_id', 'client_event_id'])
    op.create_unique_index('ux_client_sync_events_clinic_idempotency', 'client_sync_events', ['clinic_id', 'idempotency_key'], 
                          postgresql_where=sa.text("idempotency_key IS NOT NULL"))
    
    # TISS jobs uniqueness (trava ética)
    op.create_unique_index('ux_tiss_jobs_clinic_invoice_procedure', 'tiss_jobs', ['clinic_id', 'invoice_id', 'procedure_code'])
    
    # Edit locks uniqueness (one lock per entity)
    op.create_unique_index('ux_edit_locks_entity_active', 'edit_locks', ['entity_type', 'entity_id'], 
                          postgresql_where=sa.text("active = true"))
    
    # Prescriptions QR token uniqueness
    op.create_unique_index('ux_prescriptions_qr_token', 'prescriptions', ['qr_token'], 
                          postgresql_where=sa.text("qr_token IS NOT NULL"))
    
    # Telemed room token uniqueness
    op.create_unique_index('ux_telemed_sessions_room_token', 'telemed_sessions', ['room_token'])
    
    # User sessions JWT ID uniqueness
    op.create_unique_index('ux_user_sessions_jwt_id', 'user_sessions', ['jwt_id'])
    
    # Medical records daily uniqueness
    op.create_unique_index('ux_medical_records_patient_doctor_date', 'medical_records', 
                          ['patient_id', 'doctor_id', sa.text("created_at::DATE")])
    
    # ========================================
    # CHECK CONSTRAINTS
    # ========================================
    
    # User role constraints
    op.create_check_constraint('ck_users_role', 'users', 
                              "role IN ('admin','doctor','reception','finance','patient')")
    
    # AI recordings status constraints
    op.create_check_constraint('ck_ai_recordings_status', 'ai_recordings', 
                              "status IN ('recording','uploaded','processing','done','failed')")
    
    # AI summaries status constraints
    op.create_check_constraint('ck_ai_summaries_status', 'ai_summaries', 
                              "status IN ('pending','done','failed')")
    
    # AI settings provider constraints
    op.create_check_constraint('ck_ai_settings_provider', 'ai_settings', 
                              "provider IN ('openai','vertex','custom')")
    
    # Prescriptions type constraints
    op.create_check_constraint('ck_prescriptions_type', 'prescriptions', 
                              "type IN ('simple','antimicrobial','C1')")
    
    # Prescriptions status constraints
    op.create_check_constraint('ck_prescriptions_status', 'prescriptions', 
                              "status IN ('draft','signed','cancelled')")
    
    # Prescriptions audit event constraints
    op.create_check_constraint('ck_prescriptions_audit_event', 'prescriptions_audit', 
                              "event IN ('create','sign','verify','view')")
    
    # TISS providers environment constraints
    op.create_check_constraint('ck_tiss_providers_environment', 'tiss_providers', 
                              "environment IN ('homolog','production')")
    
    # TISS jobs status constraints
    op.create_check_constraint('ck_tiss_jobs_status', 'tiss_jobs', 
                              "status IN ('pending','processing','sent','accepted','rejected','error')")
    
    # Health providers environment constraints
    op.create_check_constraint('ck_health_providers_environment', 'health_providers', 
                              "environment IN ('homolog','production')")
    
    # Health providers connection status constraints
    op.create_check_constraint('ck_health_providers_connection_status', 'health_providers', 
                              "last_connection_status IN ('ok','failed')")
    
    # Telemed sessions status constraints
    op.create_check_constraint('ck_telemed_sessions_status', 'telemed_sessions', 
                              "status IN ('scheduled','active','ended','cancelled')")
    
    # Waiting queue status constraints
    op.create_check_constraint('ck_waiting_queue_status', 'waiting_queue', 
                              "status IN ('waiting','called','done','cancelled')")
    
    # Medical records status constraints
    op.create_check_constraint('ck_medical_records_status', 'medical_records', 
                              "status IN ('draft','final','locked')")
    
    # ========================================
    # TRIGGERS FOR AUTO-UPDATING TIMESTAMPS
    # ========================================
    
    # Add updated_at triggers to all tables that need them
    tables_with_updated_at = [
        'ai_settings', 'tiss_providers', 'tiss_jobs', 'health_providers'
    ]
    
    for table in tables_with_updated_at:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """)
    
    # ========================================
    # SAMPLE DATA FOR TESTING
    # ========================================
    
    # Insert sample roles
    op.execute("""
        INSERT INTO roles (id, name, description, permissions, is_active, created_at, updated_at) VALUES
            (gen_random_uuid(), 'superadmin', 'Super Administrator', '["*"]', true, now(), now()),
            (gen_random_uuid(), 'admin', 'Clinic Administrator', '["users.*", "patients.*", "appointments.*", "medical_records.*"]', true, now(), now()),
            (gen_random_uuid(), 'doctor', 'Medical Doctor', '["patients.read", "patients.update", "medical_records.*", "prescriptions.*"]', true, now(), now()),
            (gen_random_uuid(), 'reception', 'Reception Staff', '["patients.*", "appointments.*", "waiting_queue.*"]', true, now(), now()),
            (gen_random_uuid(), 'finance', 'Finance Staff', '["invoices.*", "tiss.*", "health_plan.*"]', true, now(), now())
        ON CONFLICT (name) DO NOTHING;
    """)

def downgrade():
    """Downgrade function - remove all new tables and columns."""
    
    # Drop triggers
    tables_with_updated_at = [
        'ai_settings', 'tiss_providers', 'tiss_jobs', 'health_providers'
    ]
    
    for table in tables_with_updated_at:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
    
    # Drop check constraints
    check_constraints = [
        'ck_users_role', 'ck_ai_recordings_status', 'ck_ai_summaries_status', 'ck_ai_settings_provider',
        'ck_prescriptions_type', 'ck_prescriptions_status', 'ck_prescriptions_audit_event',
        'ck_tiss_providers_environment', 'ck_tiss_jobs_status', 'ck_health_providers_environment',
        'ck_health_providers_connection_status', 'ck_telemed_sessions_status', 'ck_waiting_queue_status',
        'ck_medical_records_status'
    ]
    
    for constraint in check_constraints:
        op.execute(f"DROP CONSTRAINT IF EXISTS {constraint};")
    
    # Drop unique indexes
    unique_indexes = [
        'ux_client_sync_events_clinic_client_id', 'ux_client_sync_events_clinic_idempotency',
        'ux_tiss_jobs_clinic_invoice_procedure', 'ux_edit_locks_entity_active',
        'ux_prescriptions_qr_token', 'ux_telemed_sessions_room_token',
        'ux_user_sessions_jwt_id', 'ux_medical_records_patient_doctor_date'
    ]
    
    for index in unique_indexes:
        op.execute(f"DROP INDEX IF EXISTS {index};")
    
    # Drop tables in reverse order
    tables_to_drop = [
        'edit_locks', 'client_sync_events', 'login_2fa_codes', 'user_sessions', 'audit_logs',
        'waiting_queue', 'telemed_logs', 'telemed_sessions', 'health_providers',
        'tiss_logs', 'tiss_jobs', 'tiss_providers', 'prescriptions_audit', 'prescriptions',
        'ai_settings', 'ai_summaries', 'ai_recordings', 'record_attachments', 'user_roles'
    ]
    
    for table in tables_to_drop:
        op.drop_table(table)
    
    # Remove columns from existing tables
    columns_to_remove = [
        ('medical_records', 'consultation_id'), ('medical_records', 'anamnese'),
        ('medical_records', 'physical_exam'), ('medical_records', 'evolution'),
        ('medical_records', 'conduct'), ('medical_records', 'diagnosis'),
        ('medical_records', 'attachments_count'), ('medical_records', 'locked'),
        ('medical_records', 'locked_by'), ('medical_records', 'lock_expires_at'),
        ('medical_records', 'status'), ('patients', 'medical_history'),
        ('users', 'twofa_enabled'), ('users', 'twofa_secret'), ('users', 'last_login_at'),
        ('users', 'crm_number'), ('users', 'signature_cert_ref'), ('users', 'is_active'),
        ('roles', 'permissions')
    ]
    
    for table, column in columns_to_remove:
        op.drop_column(table, column)
    
    # Drop foreign key constraints
    op.drop_constraint('fk_medical_records_consultation', 'medical_records', type_='foreignkey')
    op.drop_constraint('fk_medical_records_locked_by', 'medical_records', type_='foreignkey')
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
