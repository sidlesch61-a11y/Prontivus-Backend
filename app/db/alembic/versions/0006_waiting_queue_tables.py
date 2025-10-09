"""Add waiting queue tables

Revision ID: 0006_waiting_queue_tables
Revises: 0005_telemedicine_tables
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0006_waiting_queue_tables'
down_revision = '0005_telemedicine_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create waiting queue tables."""
    
    # Create waiting_queue table
    op.create_table('waiting_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='waiting'),
        sa.Column('priority', sa.String(), nullable=False, default='normal'),
        sa.Column('enqueued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('called_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consultation_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consultation_ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_wait_time_minutes', sa.Integer(), nullable=True),
        sa.Column('estimated_call_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('queue_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes for waiting_queue
    op.create_index('idx_waiting_queue_clinic_id', 'waiting_queue', ['clinic_id'])
    op.create_index('idx_waiting_queue_appointment_id', 'waiting_queue', ['appointment_id'])
    op.create_index('idx_waiting_queue_patient_id', 'waiting_queue', ['patient_id'])
    op.create_index('idx_waiting_queue_doctor_id', 'waiting_queue', ['doctor_id'])
    op.create_index('idx_waiting_queue_status', 'waiting_queue', ['status'])
    op.create_index('idx_waiting_queue_priority', 'waiting_queue', ['priority'])
    op.create_index('idx_waiting_queue_position', 'waiting_queue', ['position'])
    op.create_index('idx_waiting_queue_enqueued_at', 'waiting_queue', ['enqueued_at'])
    op.create_index('idx_waiting_queue_created_at', 'waiting_queue', ['created_at'])
    
    # Create composite indexes for common queries
    op.create_index('idx_waiting_queue_clinic_doctor_status', 'waiting_queue', ['clinic_id', 'doctor_id', 'status'])
    op.create_index('idx_waiting_queue_clinic_doctor_position', 'waiting_queue', ['clinic_id', 'doctor_id', 'position'])
    
    # Create waiting_queue_logs table
    op.create_table('waiting_queue_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('queue_id', postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(['queue_id'], ['waiting_queue.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes for waiting_queue_logs
    op.create_index('idx_waiting_queue_logs_queue_id', 'waiting_queue_logs', ['queue_id'])
    op.create_index('idx_waiting_queue_logs_clinic_id', 'waiting_queue_logs', ['clinic_id'])
    op.create_index('idx_waiting_queue_logs_event', 'waiting_queue_logs', ['event'])
    op.create_index('idx_waiting_queue_logs_user_id', 'waiting_queue_logs', ['user_id'])
    op.create_index('idx_waiting_queue_logs_created_at', 'waiting_queue_logs', ['created_at'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_waiting_queue_status',
        'waiting_queue',
        "status IN ('waiting', 'called', 'in_consultation', 'completed', 'cancelled', 'no_show')"
    )
    
    op.create_check_constraint(
        'ck_waiting_queue_priority',
        'waiting_queue',
        "priority IN ('normal', 'urgent', 'emergency', 'vip')"
    )
    
    op.create_check_constraint(
        'ck_waiting_queue_position',
        'waiting_queue',
        'position > 0'
    )
    
    op.create_check_constraint(
        'ck_waiting_queue_logs_event',
        'waiting_queue_logs',
        "event IN ('enqueued', 'dequeued', 'called', 'consultation_started', 'consultation_ended', 'consultation_finalized', 'position_changed', 'priority_changed', 'notes_updated')"
    )
    
    op.create_check_constraint(
        'ck_waiting_queue_logs_user_role',
        'waiting_queue_logs',
        "user_role IN ('doctor', 'receptionist', 'admin', 'system')"
    )
    
    # Add updated_at trigger for waiting_queue
    op.execute("""
        CREATE TRIGGER trg_waiting_queue_set_updated_at
        BEFORE UPDATE ON waiting_queue
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    # Add function to automatically update positions when entries are removed
    op.execute("""
        CREATE OR REPLACE FUNCTION update_queue_positions()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Update positions for remaining entries in the same clinic and doctor
            UPDATE waiting_queue 
            SET position = position - 1, updated_at = now()
            WHERE clinic_id = OLD.clinic_id 
              AND doctor_id = OLD.doctor_id 
              AND position > OLD.position
              AND status IN ('waiting', 'called', 'in_consultation');
            
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add trigger to automatically update positions
    op.execute("""
        CREATE TRIGGER trg_waiting_queue_update_positions
        AFTER DELETE ON waiting_queue
        FOR EACH ROW
        EXECUTE FUNCTION update_queue_positions();
    """)
    
    # Add function to prevent duplicate queue entries
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_duplicate_queue_entries()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Check if patient is already in active queue
            IF EXISTS (
                SELECT 1 FROM waiting_queue 
                WHERE clinic_id = NEW.clinic_id 
                  AND patient_id = NEW.patient_id 
                  AND status IN ('waiting', 'called', 'in_consultation')
            ) THEN
                RAISE EXCEPTION 'Patient is already in the waiting queue';
            END IF;
            
            -- Check if appointment is already in queue
            IF EXISTS (
                SELECT 1 FROM waiting_queue 
                WHERE clinic_id = NEW.clinic_id 
                  AND appointment_id = NEW.appointment_id 
                  AND status IN ('waiting', 'called', 'in_consultation')
            ) THEN
                RAISE EXCEPTION 'Appointment is already in the waiting queue';
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add trigger to prevent duplicate entries
    op.execute("""
        CREATE TRIGGER trg_waiting_queue_prevent_duplicates
        BEFORE INSERT ON waiting_queue
        FOR EACH ROW
        EXECUTE FUNCTION prevent_duplicate_queue_entries();
    """)


def downgrade():
    """Drop waiting queue tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_waiting_queue_prevent_duplicates ON waiting_queue;")
    op.execute("DROP TRIGGER IF EXISTS trg_waiting_queue_update_positions ON waiting_queue;")
    op.execute("DROP TRIGGER IF EXISTS trg_waiting_queue_set_updated_at ON waiting_queue;")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS prevent_duplicate_queue_entries();")
    op.execute("DROP FUNCTION IF EXISTS update_queue_positions();")
    
    # Drop check constraints
    op.drop_constraint('ck_waiting_queue_logs_user_role', 'waiting_queue_logs', type_='check')
    op.drop_constraint('ck_waiting_queue_logs_event', 'waiting_queue_logs', type_='check')
    op.drop_constraint('ck_waiting_queue_position', 'waiting_queue', type_='check')
    op.drop_constraint('ck_waiting_queue_priority', 'waiting_queue', type_='check')
    op.drop_constraint('ck_waiting_queue_status', 'waiting_queue', type_='check')
    
    # Drop tables
    op.drop_table('waiting_queue_logs')
    op.drop_table('waiting_queue')
