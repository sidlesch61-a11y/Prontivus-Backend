"""Add appointment_requests table

Revision ID: 0019_appointment_requests
Revises: 0018_make_prescription_record_id_nullable
Create Date: 2025-10-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0019_appointment_requests'
down_revision = '0018_make_prescription_record_id_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create appointment_requests table for patient online booking system."""
    op.create_table('appointment_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('preferred_date', sa.String(), nullable=False),
        sa.Column('preferred_time', sa.String(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('approved_appointment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_start_time', sa.DateTime(), nullable=True),
        sa.Column('approved_end_time', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better query performance
    op.create_index('idx_appointment_requests_clinic', 'appointment_requests', ['clinic_id'])
    op.create_index('idx_appointment_requests_patient', 'appointment_requests', ['patient_id'])
    op.create_index('idx_appointment_requests_status', 'appointment_requests', ['status'])
    op.create_index('idx_appointment_requests_requested_at', 'appointment_requests', ['requested_at'])


def downgrade() -> None:
    """Drop appointment_requests table."""
    op.drop_index('idx_appointment_requests_requested_at', table_name='appointment_requests')
    op.drop_index('idx_appointment_requests_status', table_name='appointment_requests')
    op.drop_index('idx_appointment_requests_patient', table_name='appointment_requests')
    op.drop_index('idx_appointment_requests_clinic', table_name='appointment_requests')
    op.drop_table('appointment_requests')

