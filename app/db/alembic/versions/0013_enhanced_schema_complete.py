"""Enhanced schema with all required tables, indexes, and constraints

Revision ID: 0013_enhanced_schema_complete
Revises: 0012_cid10_codes
Create Date: 2025-10-09 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '0013_enhanced_schema_complete'
down_revision = '0012_cid10_codes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create health_plan_integrations table
    op.create_table(
        'health_plan_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('provider_code', sa.String(), nullable=False),
        
        # OAuth2 configuration
        sa.Column('base_url', sa.String(), nullable=False),
        sa.Column('client_id', sa.String(), nullable=False),
        sa.Column('client_secret_encrypted', sa.Text(), nullable=False),
        sa.Column('scope', sa.String(), nullable=True),
        
        # Token management
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('token_last_refreshed', sa.DateTime(timezone=True), nullable=True),
        
        # Connection status
        sa.Column('status', sa.String(), nullable=False, server_default='inactive'),
        sa.Column('last_status_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_successful_call', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        
        # Configuration
        sa.Column('config_meta', postgresql.JSONB, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        # Soft delete
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )
    
    # Create digital_prescriptions table
    op.create_table(
        'digital_prescriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('emr_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('medical_records.id', ondelete='SET NULL'), nullable=True),
        
        # Prescription details
        sa.Column('prescription_type', sa.String(), nullable=False, server_default='simple'),
        sa.Column('medications', postgresql.JSONB, nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Digital signature
        sa.Column('pdf_url', sa.String(), nullable=True),
        sa.Column('pdf_path', sa.String(), nullable=True),
        sa.Column('signed_hash', sa.String(64), nullable=True, index=True),
        sa.Column('signature_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('signature_certificate_id', sa.String(), nullable=True),
        
        # QR Code
        sa.Column('qr_code_url', sa.String(), nullable=True),
        sa.Column('qr_code_data', sa.String(), nullable=True),
        sa.Column('verification_code', sa.String(32), nullable=True, unique=True, index=True),
        
        # Compliance
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('compliance_flags', postgresql.JSONB, nullable=True),
        
        # Audit
        sa.Column('viewed_by', postgresql.JSONB, nullable=True),
        sa.Column('viewed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        
        # Soft delete
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )
    
    # Create ai_logs table
    op.create_table(
        'ai_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        
        # AI request details
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('request_type', sa.String(), nullable=False),
        
        # Usage tracking
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        
        # Cost tracking
        sa.Column('cost', sa.Numeric(10, 4), nullable=True, server_default='0.0'),
        sa.Column('cost_currency', sa.String(3), nullable=False, server_default='USD'),
        
        # Request/Response
        sa.Column('request_payload', postgresql.JSONB, nullable=True),
        sa.Column('response_payload', postgresql.JSONB, nullable=True),
        
        # Performance
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Context
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recording_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create reports_cache table
    op.create_table(
        'reports_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinics.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Report identification
        sa.Column('report_type', sa.String(), nullable=False, index=True),
        sa.Column('report_key', sa.String(), nullable=False),
        
        # Report data
        sa.Column('data_json', postgresql.JSONB, nullable=False),
        
        # Parameters
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filters', postgresql.JSONB, nullable=True),
        
        # Cache management
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        
        # Metadata
        sa.Column('generation_duration_seconds', sa.Float(), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Add composite unique constraint for report cache
    op.create_index(
        'idx_reports_cache_unique',
        'reports_cache',
        ['clinic_id', 'report_type', 'report_key'],
        unique=True
    )
    
    # Add additional indexes to existing tables for performance
    
    # Appointments indexes
    op.create_index('idx_appointments_clinic_date', 'appointments', ['clinic_id', 'start_time'])
    op.create_index('idx_appointments_doctor_date', 'appointments', ['doctor_id', 'start_time'])
    op.create_index('idx_appointments_patient_date', 'appointments', ['patient_id', 'start_time'])
    op.create_index('idx_appointments_status', 'appointments', ['status'])
    
    # Medical records indexes
    op.create_index('idx_medical_records_clinic_created', 'medical_records', ['clinic_id', 'created_at'])
    op.create_index('idx_medical_records_doctor_created', 'medical_records', ['doctor_id', 'created_at'])
    op.create_index('idx_medical_records_patient_created', 'medical_records', ['patient_id', 'created_at'])
    
    # Invoices indexes
    op.create_index('idx_invoices_clinic_status', 'invoices', ['clinic_id', 'status'])
    op.create_index('idx_invoices_due_date', 'invoices', ['due_date'])
    op.create_index('idx_invoices_patient_status', 'invoices', ['patient_id', 'status'])
    
    # Audit logs indexes
    op.create_index('idx_audit_logs_clinic_action', 'audit_logs', ['clinic_id', 'action'])
    op.create_index('idx_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('idx_audit_logs_entity', 'audit_logs', ['entity', 'entity_id'])
    
    # Patients indexes
    op.create_index('idx_patients_cpf', 'patients', ['cpf'])
    op.create_index('idx_patients_email', 'patients', ['email'])
    
    # Users indexes
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_clinic_role', 'users', ['clinic_id', 'role'])


def downgrade() -> None:
    # Remove additional indexes
    op.drop_index('idx_users_clinic_role', 'users')
    op.drop_index('idx_users_email', 'users')
    op.drop_index('idx_patients_email', 'patients')
    op.drop_index('idx_patients_cpf', 'patients')
    op.drop_index('idx_audit_logs_entity', 'audit_logs')
    op.drop_index('idx_audit_logs_user_created', 'audit_logs')
    op.drop_index('idx_audit_logs_clinic_action', 'audit_logs')
    op.drop_index('idx_invoices_patient_status', 'invoices')
    op.drop_index('idx_invoices_due_date', 'invoices')
    op.drop_index('idx_invoices_clinic_status', 'invoices')
    op.drop_index('idx_medical_records_patient_created', 'medical_records')
    op.drop_index('idx_medical_records_doctor_created', 'medical_records')
    op.drop_index('idx_medical_records_clinic_created', 'medical_records')
    op.drop_index('idx_appointments_status', 'appointments')
    op.drop_index('idx_appointments_patient_date', 'appointments')
    op.drop_index('idx_appointments_doctor_date', 'appointments')
    op.drop_index('idx_appointments_clinic_date', 'appointments')
    
    # Drop new tables
    op.drop_index('idx_reports_cache_unique', 'reports_cache')
    op.drop_table('reports_cache')
    op.drop_table('ai_logs')
    op.drop_table('digital_prescriptions')
    op.drop_table('health_plan_integrations')

