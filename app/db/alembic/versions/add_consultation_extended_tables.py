"""add consultation extended tables

Revision ID: consultation_extended_001
Revises: 
Create Date: 2025-10-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'consultation_extended_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create vitals table
    op.create_table(
        'vitals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('recorded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('blood_pressure', sa.String, nullable=True),
        sa.Column('heart_rate', sa.Integer, nullable=True),
        sa.Column('temperature', sa.Float, nullable=True),
        sa.Column('weight', sa.Float, nullable=True),
        sa.Column('height', sa.Float, nullable=True),
        sa.Column('respiratory_rate', sa.Integer, nullable=True),
        sa.Column('oxygen_saturation', sa.Integer, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('recorded_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create attachments table
    op.create_table(
        'attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('file_name', sa.String, nullable=False),
        sa.Column('file_type', sa.String, nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('file_url', sa.String, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String, nullable=True),
        sa.Column('uploaded_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create queue_status table
    op.create_table(
        'queue_status',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('appointments.id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('status', sa.String, nullable=False, server_default='waiting'),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('called_at', sa.DateTime, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create consultation_notes table
    op.create_table(
        'consultation_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False, unique=True),
        sa.Column('anamnese', sa.Text, nullable=True),
        sa.Column('physical_exam', sa.Text, nullable=True),
        sa.Column('evolution', sa.Text, nullable=True),
        sa.Column('diagnosis', sa.Text, nullable=True),
        sa.Column('treatment_plan', sa.Text, nullable=True),
        sa.Column('allergies', sa.String, nullable=True),
        sa.Column('chronic_conditions', sa.String, nullable=True),
        sa.Column('auto_saved_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create prescription_items table
    op.create_table(
        'prescription_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('prescription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prescriptions.id'), nullable=False),
        sa.Column('medication_name', sa.String, nullable=False),
        sa.Column('dosage', sa.String, nullable=False),
        sa.Column('frequency', sa.String, nullable=False),
        sa.Column('duration', sa.String, nullable=False),
        sa.Column('route', sa.String, nullable=False, server_default='oral'),
        sa.Column('instructions', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create medical_certificates table
    op.create_table(
        'medical_certificates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('certificate_type', sa.String, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('days_off', sa.Integer, nullable=True),
        sa.Column('cid10_code', sa.String, nullable=True),
        sa.Column('pdf_url', sa.String, nullable=True),
        sa.Column('icp_signature_hash', sa.String, nullable=True),
        sa.Column('issued_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create exam_requests table
    op.create_table(
        'exam_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('tiss_guide_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tiss_guides.id'), nullable=True),
        sa.Column('exam_type', sa.String, nullable=False),
        sa.Column('exam_name', sa.String, nullable=False),
        sa.Column('clinical_indication', sa.Text, nullable=False),
        sa.Column('urgency', sa.String, nullable=False, server_default='routine'),
        sa.Column('pdf_url', sa.String, nullable=True),
        sa.Column('status', sa.String, nullable=False, server_default='pending'),
        sa.Column('requested_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create referrals table
    op.create_table(
        'referrals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('specialty', sa.String, nullable=False),
        sa.Column('reason', sa.Text, nullable=False),
        sa.Column('urgency', sa.String, nullable=False, server_default='routine'),
        sa.Column('referred_to_doctor', sa.String, nullable=True),
        sa.Column('referred_to_clinic', sa.String, nullable=True),
        sa.Column('pdf_url', sa.String, nullable=True),
        sa.Column('status', sa.String, nullable=False, server_default='pending'),
        sa.Column('referred_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create voice_notes table
    op.create_table(
        'voice_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultations.id'), nullable=False),
        sa.Column('recorded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('audio_url', sa.String, nullable=False),
        sa.Column('duration_seconds', sa.Integer, nullable=False),
        sa.Column('transcription', sa.Text, nullable=True),
        sa.Column('note_type', sa.String, nullable=False, server_default='anamnese'),
        sa.Column('transcribed_at', sa.DateTime, nullable=True),
        sa.Column('recorded_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create indexes for better query performance
    op.create_index('idx_vitals_consultation', 'vitals', ['consultation_id'])
    op.create_index('idx_attachments_consultation', 'attachments', ['consultation_id'])
    op.create_index('idx_queue_status_doctor', 'queue_status', ['doctor_id', 'status'])
    op.create_index('idx_queue_status_appointment', 'queue_status', ['appointment_id'])
    op.create_index('idx_consultation_notes_consultation', 'consultation_notes', ['consultation_id'])
    op.create_index('idx_prescription_items_prescription', 'prescription_items', ['prescription_id'])
    op.create_index('idx_exam_requests_consultation', 'exam_requests', ['consultation_id'])
    op.create_index('idx_referrals_consultation', 'referrals', ['consultation_id'])
    op.create_index('idx_voice_notes_consultation', 'voice_notes', ['consultation_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_voice_notes_consultation')
    op.drop_index('idx_referrals_consultation')
    op.drop_index('idx_exam_requests_consultation')
    op.drop_index('idx_prescription_items_prescription')
    op.drop_index('idx_consultation_notes_consultation')
    op.drop_index('idx_queue_status_appointment')
    op.drop_index('idx_queue_status_doctor')
    op.drop_index('idx_attachments_consultation')
    op.drop_index('idx_vitals_consultation')
    
    # Drop tables
    op.drop_table('voice_notes')
    op.drop_table('referrals')
    op.drop_table('exam_requests')
    op.drop_table('medical_certificates')
    op.drop_table('prescription_items')
    op.drop_table('consultation_notes')
    op.drop_table('queue_status')
    op.drop_table('attachments')
    op.drop_table('vitals')

