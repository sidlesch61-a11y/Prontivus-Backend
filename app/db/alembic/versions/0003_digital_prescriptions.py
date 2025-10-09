"""Add digital prescriptions table

Revision ID: 0003_digital_prescriptions
Revises: 0002_ai_consultation_tables
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003_digital_prescriptions'
down_revision = '0002_ai_consultation_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add digital prescriptions table with PAdES signature support."""
    
    # Create prescriptions table
    op.create_table('prescriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('prescription_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('rx_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('signed_pdf_path', sa.String(), nullable=True),
        sa.Column('signature_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('qr_token', sa.String(), nullable=True),
        sa.Column('signer_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('certificate_id', sa.String(), nullable=True),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['signer_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_prescriptions_clinic', 'prescriptions', ['clinic_id'])
    op.create_index('idx_prescriptions_patient', 'prescriptions', ['patient_id'])
    op.create_index('idx_prescriptions_doctor', 'prescriptions', ['doctor_id'])
    op.create_index('idx_prescriptions_status', 'prescriptions', ['status'])
    op.create_index('idx_prescriptions_type', 'prescriptions', ['prescription_type'])
    op.create_index('idx_prescriptions_qr_token', 'prescriptions', ['qr_token'], unique=True)
    op.create_index('idx_prescriptions_created_at', 'prescriptions', ['created_at'])
    op.create_index('idx_prescriptions_expires_at', 'prescriptions', ['expires_at'])
    
    # Create unique constraint for QR token
    op.create_unique_constraint('uq_prescriptions_qr_token', 'prescriptions', ['qr_token'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_prescriptions_type',
        'prescriptions',
        "prescription_type IN ('simple', 'antimicrobial', 'C1')"
    )
    
    op.create_check_constraint(
        'ck_prescriptions_status',
        'prescriptions',
        "status IN ('draft', 'signed', 'verified', 'expired', 'revoked')"
    )
    
    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER trg_prescriptions_set_updated_at
        BEFORE UPDATE ON prescriptions
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade():
    """Remove digital prescriptions table."""
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_prescriptions_set_updated_at ON prescriptions;")
    
    # Drop constraints
    op.drop_constraint('ck_prescriptions_status', 'prescriptions', type_='check')
    op.drop_constraint('ck_prescriptions_type', 'prescriptions', type_='check')
    
    # Drop unique constraint
    op.drop_constraint('uq_prescriptions_qr_token', 'prescriptions', type_='unique')
    
    # Drop indexes
    op.drop_index('idx_prescriptions_expires_at', table_name='prescriptions')
    op.drop_index('idx_prescriptions_created_at', table_name='prescriptions')
    op.drop_index('idx_prescriptions_qr_token', table_name='prescriptions')
    op.drop_index('idx_prescriptions_type', table_name='prescriptions')
    op.drop_index('idx_prescriptions_status', table_name='prescriptions')
    op.drop_index('idx_prescriptions_doctor', table_name='prescriptions')
    op.drop_index('idx_prescriptions_patient', table_name='prescriptions')
    op.drop_index('idx_prescriptions_clinic', table_name='prescriptions')
    
    # Drop table
    op.drop_table('prescriptions')
