"""Initial Prontivus database schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable required extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')
    op.execute('CREATE EXTENSION IF NOT EXISTS citext;')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist;')
    
    # Create utility functions
    op.execute('''
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$;
    ''')
    
    # Create clinics table
    op.create_table('clinics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('cnpj_cpf', sa.String(), nullable=True),
        sa.Column('domain', sa.String(), nullable=True),
        sa.Column('contact_email', postgresql.CITEXT(), nullable=False),
        sa.Column('contact_phone', sa.String(), nullable=True),
        sa.Column('logo_url', sa.String(), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('active', 'suspended', 'inactive', 'trial')", name='chk_clinics_status')
    )
    op.create_index('idx_clinics_name', 'clinics', ['name'], postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('idx_clinics_status', 'clinics', ['status'])
    op.create_index('idx_clinics_domain', 'clinics', ['domain'], postgresql_where=sa.text('domain IS NOT NULL'))
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', postgresql.CITEXT(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('twofa_secret', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("role IN ('superadmin', 'admin', 'doctor', 'secretary', 'patient')", name='chk_users_role')
    )
    op.create_index('ux_users_clinic_email', 'users', ['clinic_id', sa.text('lower(email)')], unique=True)
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_clinic', 'users', ['clinic_id'])
    op.create_index('idx_users_email', 'users', ['email'], postgresql_using='gin', postgresql_ops={'email': 'gin_trgm_ops'})
    op.create_index('idx_users_active', 'users', ['clinic_id', 'is_active'], postgresql_where=sa.text('is_active = TRUE'))
    
    # Create patients table
    op.create_table('patients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('birthdate', sa.Date(), nullable=True),
        sa.Column('gender', sa.String(), nullable=True),
        sa.Column('cpf', sa.String(), nullable=True),
        sa.Column('rg', sa.String(), nullable=True),
        sa.Column('address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', postgresql.CITEXT(), nullable=True),
        sa.Column('emergency_contact', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('insurance_number', sa.String(), nullable=True),
        sa.Column('insurance_provider', sa.String(), nullable=True),
        sa.Column('allergies', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('medical_conditions', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('medications', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("gender IN ('male', 'female', 'other', 'unknown')", name='chk_patients_gender')
    )
    op.create_index('ux_patients_clinic_cpf', 'patients', ['clinic_id', 'cpf'], unique=True, postgresql_where=sa.text('cpf IS NOT NULL AND archived = FALSE'))
    op.create_index('idx_patients_clinic_name', 'patients', ['clinic_id', sa.text('lower(name)')])
    op.create_index('idx_patients_email', 'patients', ['clinic_id', sa.text('lower(email)')], postgresql_where=sa.text('email IS NOT NULL'))
    op.create_index('idx_patients_phone', 'patients', ['clinic_id', 'phone'], postgresql_where=sa.text('phone IS NOT NULL'))
    op.create_index('idx_patients_archived', 'patients', ['clinic_id', 'archived'])
    op.create_index('idx_patients_name_trgm', 'patients', ['name'], postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('idx_patients_cpf_trgm', 'patients', ['cpf'], postgresql_using='gin', postgresql_ops={'cpf': 'gin_trgm_ops'}, postgresql_where=sa.text('cpf IS NOT NULL'))
    
    # Create appointments table (partitioned)
    op.execute('''
        CREATE TABLE appointments (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
          patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
          doctor_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
          start_time TIMESTAMPTZ NOT NULL,
          end_time TIMESTAMPTZ NOT NULL,
          duration_minutes INTEGER GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (end_time - start_time))/60) STORED,
          status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show')),
          telemed_link TEXT,
          source TEXT CHECK (source IN ('web', 'mobile', 'frontdesk', 'import', 'telemedicine')) DEFAULT 'web',
          notes TEXT,
          cancellation_reason TEXT,
          cancellation_notes TEXT,
          metadata JSONB DEFAULT '{}'::JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT chk_appointment_times CHECK (end_time > start_time)
        ) PARTITION BY RANGE (start_time);
    ''')
    
    # Create appointment partitions
    op.execute('CREATE TABLE appointments_2024 PARTITION OF appointments FOR VALUES FROM (\'2024-01-01\') TO (\'2025-01-01\');')
    op.execute('CREATE TABLE appointments_2025 PARTITION OF appointments FOR VALUES FROM (\'2025-01-01\') TO (\'2026-01-01\');')
    op.execute('CREATE TABLE appointments_2026 PARTITION OF appointments FOR VALUES FROM (\'2026-01-01\') TO (\'2027-01-01\');')
    
    # Create appointment indexes
    op.execute('CREATE INDEX idx_appointments_clinic_start ON appointments (clinic_id, start_time);')
    op.execute('CREATE INDEX idx_appointments_doctor_range ON appointments (doctor_id, start_time, end_time);')
    op.execute('CREATE INDEX idx_appointments_patient_date ON appointments (patient_id, start_time);')
    op.execute('CREATE INDEX idx_appointments_status ON appointments (clinic_id, status);')
    
    # Create medical records table
    op.create_table('medical_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_type', sa.String(), nullable=False),
        sa.Column('anamnesis', sa.Text(), nullable=True),
        sa.Column('physical_exam', sa.Text(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('icd_codes', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('treatment_plan', sa.Text(), nullable=True),
        sa.Column('follow_up_instructions', sa.Text(), nullable=True),
        sa.Column('vital_signs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("record_type IN ('encounter', 'evolution', 'note', 'prescription', 'procedure')", name='chk_medrec_type')
    )
    op.create_index('idx_medrec_patient', 'medical_records', ['clinic_id', 'patient_id', 'created_at'])
    op.create_index('idx_medrec_appointment', 'medical_records', ['appointment_id'])
    op.create_index('idx_medrec_doctor', 'medical_records', ['doctor_id', 'created_at'])
    op.create_index('idx_medrec_type', 'medical_records', ['clinic_id', 'record_type'])
    
    # Create prescriptions table
    op.create_table('prescriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('medication_name', sa.String(), nullable=False),
        sa.Column('dosage', sa.String(), nullable=True),
        sa.Column('frequency', sa.String(), nullable=True),
        sa.Column('duration', sa.String(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_prescriptions_record', 'prescriptions', ['record_id'])
    op.create_index('idx_prescriptions_medication', 'prescriptions', ['clinic_id', 'medication_name'])
    
    # Create files table
    op.create_table('files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column('storage_provider', sa.String(), nullable=True),
        sa.Column('file_hash', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('scan_status', sa.String(), nullable=True),
        sa.Column('scan_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("scan_status IN ('pending', 'clean', 'infected', 'error')", name='chk_files_scan_status')
    )
    op.create_index('idx_files_patient', 'files', ['clinic_id', 'patient_id'])
    op.create_index('idx_files_record', 'files', ['record_id'])
    op.create_index('idx_files_appointment', 'files', ['appointment_id'])
    op.create_index('idx_files_uploaded_by', 'files', ['uploaded_by'])
    op.create_index('idx_files_content_type', 'files', ['content_type'])
    
    # Create invoices table
    op.create_table('invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('invoice_number', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount >= 0', name='chk_invoices_amount'),
        sa.CheckConstraint("payment_method IN ('pix', 'card', 'boleto', 'paypal', 'cash', 'insurance')", name='chk_invoices_payment_method'),
        sa.CheckConstraint("status IN ('draft', 'pending', 'paid', 'cancelled', 'failed', 'refunded')", name='chk_invoices_status')
    )
    op.create_index('ux_invoices_clinic_number', 'invoices', ['clinic_id', 'invoice_number'], unique=True)
    op.create_index('idx_invoices_clinic_status', 'invoices', ['clinic_id', 'status'])
    op.create_index('idx_invoices_patient', 'invoices', ['patient_id'])
    op.create_index('idx_invoices_due_date', 'invoices', ['due_date'], postgresql_where=sa.text("status = 'pending'"))
    
    # Create audit logs table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_clinic', 'audit_logs', ['clinic_id', 'created_at'])
    op.create_index('idx_audit_user', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('idx_audit_entity', 'audit_logs', ['entity', 'entity_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action', 'created_at'])
    
    # Create webhook events table
    op.create_table('webhook_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('webhook_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('signature', sa.String(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ux_webhook_source_webhookid', 'webhook_events', ['source', 'webhook_id'], unique=True, postgresql_where=sa.text('webhook_id IS NOT NULL'))
    op.create_index('idx_webhook_source', 'webhook_events', ['source', 'created_at'])
    op.create_index('idx_webhook_processed', 'webhook_events', ['processed', 'created_at'])
    
    # Create client sync events table
    op.create_table('client_sync_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('server_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ux_client_sync_clinic_clientid', 'client_sync_events', ['clinic_id', 'client_event_id'], unique=True)
    op.create_index('idx_client_sync_clinic', 'client_sync_events', ['clinic_id', 'created_at'])
    op.create_index('idx_client_sync_processed', 'client_sync_events', ['processed', 'created_at'])
    
    # Create licenses table
    op.create_table('licenses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan', sa.String(), nullable=False),
        sa.Column('modules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('users_limit', sa.Integer(), nullable=True),
        sa.Column('units_limit', sa.Integer(), nullable=True),
        sa.Column('appointments_limit', sa.Integer(), nullable=True),
        sa.Column('storage_limit_gb', sa.Integer(), nullable=True),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('signature', sa.String(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('offline_grace_hours', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('end_at > start_at', name='chk_license_dates'),
        sa.CheckConstraint("status IN ('active', 'expired', 'suspended', 'trial')", name='chk_licenses_status')
    )
    op.create_index('idx_licenses_clinic', 'licenses', ['clinic_id'])
    op.create_index('idx_licenses_status', 'licenses', ['status'])
    op.create_index('idx_licenses_end_date', 'licenses', ['end_at'], postgresql_where=sa.text("status = 'active'"))
    
    # Create activations table
    op.create_table('activations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('license_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('instance_id', sa.String(), nullable=False),
        sa.Column('device_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('offline_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('active', 'revoked', 'grace', 'suspended')", name='chk_activations_status')
    )
    op.create_index('ux_activations_license_instance', 'activations', ['license_id', 'instance_id'], unique=True)
    op.create_index('idx_activations_license', 'activations', ['license_id'])
    op.create_index('idx_activations_status', 'activations', ['status'])
    
    # Create triggers for updated_at
    op.execute('CREATE TRIGGER trg_clinics_set_updated_at BEFORE UPDATE ON clinics FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_users_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_patients_set_updated_at BEFORE UPDATE ON patients FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_appointments_set_updated_at BEFORE UPDATE ON appointments FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_medrec_set_updated_at BEFORE UPDATE ON medical_records FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_prescriptions_set_updated_at BEFORE UPDATE ON prescriptions FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_files_set_updated_at BEFORE UPDATE ON files FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_invoices_set_updated_at BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION set_updated_at();')
    op.execute('CREATE TRIGGER trg_licenses_set_updated_at BEFORE UPDATE ON licenses FOR EACH ROW EXECUTE FUNCTION set_updated_at();')


def downgrade() -> None:
    # Drop triggers first
    op.execute('DROP TRIGGER IF EXISTS trg_licenses_set_updated_at ON licenses;')
    op.execute('DROP TRIGGER IF EXISTS trg_invoices_set_updated_at ON invoices;')
    op.execute('DROP TRIGGER IF EXISTS trg_files_set_updated_at ON files;')
    op.execute('DROP TRIGGER IF EXISTS trg_prescriptions_set_updated_at ON prescriptions;')
    op.execute('DROP TRIGGER IF EXISTS trg_medrec_set_updated_at ON medical_records;')
    op.execute('DROP TRIGGER IF EXISTS trg_appointments_set_updated_at ON appointments;')
    op.execute('DROP TRIGGER IF EXISTS trg_patients_set_updated_at ON patients;')
    op.execute('DROP TRIGGER IF EXISTS trg_users_set_updated_at ON users;')
    op.execute('DROP TRIGGER IF EXISTS trg_clinics_set_updated_at ON clinics;')
    
    # Drop tables in reverse order
    op.drop_table('activations')
    op.drop_table('licenses')
    op.drop_table('client_sync_events')
    op.drop_table('webhook_events')
    op.drop_table('audit_logs')
    op.drop_table('invoices')
    op.drop_table('files')
    op.drop_table('prescriptions')
    op.drop_table('medical_records')
    op.execute('DROP TABLE IF EXISTS appointments CASCADE;')  # Drop partitioned table
    op.drop_table('patients')
    op.drop_table('users')
    op.drop_table('clinics')
    
    # Drop functions
    op.execute('DROP FUNCTION IF EXISTS set_updated_at();')
    
    # Note: Extensions are not dropped as they might be used by other databases