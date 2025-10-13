"""create consultations table

Revision ID: 0021
Revises: 0020
Create Date: 2025-10-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON, TIMESTAMP


# revision identifiers, used by Alembic.
revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create consultations table for medical consultations."""
    op.create_table(
        'consultations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('appointment_id', UUID(as_uuid=True), sa.ForeignKey('appointments.id'), nullable=False),
        sa.Column('doctor_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        
        # Anamnese fields
        sa.Column('chief_complaint', sa.Text, nullable=False),
        sa.Column('history_present_illness', sa.Text, nullable=True),
        sa.Column('past_medical_history', sa.Text, nullable=True),
        sa.Column('family_history', sa.Text, nullable=True),
        sa.Column('social_history', sa.Text, nullable=True),
        sa.Column('medications_in_use', sa.Text, nullable=True),
        sa.Column('allergies', sa.String(255), nullable=True),
        
        # Physical examination and diagnosis
        sa.Column('physical_examination', sa.Text, nullable=True),
        sa.Column('vital_signs', JSON, nullable=True, server_default='{}'),
        sa.Column('diagnosis', sa.Text, nullable=False),
        sa.Column('diagnosis_code', sa.String(10), nullable=True),  # CID-10 code
        sa.Column('treatment_plan', sa.Text, nullable=True),
        sa.Column('follow_up', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        
        # Lock mechanism
        sa.Column('is_locked', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('locked_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('locked_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        
        # Timestamps
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes
    op.create_index('idx_consultations_clinic_id', 'consultations', ['clinic_id'])
    op.create_index('idx_consultations_patient_id', 'consultations', ['patient_id'])
    op.create_index('idx_consultations_appointment_id', 'consultations', ['appointment_id'])
    op.create_index('idx_consultations_doctor_id', 'consultations', ['doctor_id'])
    op.create_index('idx_consultations_created_at', 'consultations', ['created_at'])


def downgrade() -> None:
    """Drop consultations table."""
    op.drop_index('idx_consultations_created_at', table_name='consultations')
    op.drop_index('idx_consultations_doctor_id', table_name='consultations')
    op.drop_index('idx_consultations_appointment_id', table_name='consultations')
    op.drop_index('idx_consultations_patient_id', table_name='consultations')
    op.drop_index('idx_consultations_clinic_id', table_name='consultations')
    op.drop_table('consultations')

