"""Add ethical locks and collision detection tables

Revision ID: 0007_ethical_locks_tables
Revises: 0006_waiting_queue_tables
Create Date: 2024-01-15 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0007_ethical_locks_tables'
down_revision = '0006_waiting_queue_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create ethical locks and collision detection tables."""
    
    # Create ethical_locks table
    op.create_table('ethical_locks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lock_type', sa.String(), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lock_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='active'),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lock_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('force_unlocked_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('force_unlocked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('force_unlock_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['locked_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['force_unlocked_by'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes for ethical_locks
    op.create_index('idx_ethical_locks_clinic_id', 'ethical_locks', ['clinic_id'])
    op.create_index('idx_ethical_locks_resource', 'ethical_locks', ['resource_id', 'resource_type'])
    op.create_index('idx_ethical_locks_locked_by', 'ethical_locks', ['locked_by'])
    op.create_index('idx_ethical_locks_status', 'ethical_locks', ['status'])
    op.create_index('idx_ethical_locks_lock_type', 'ethical_locks', ['lock_type'])
    op.create_index('idx_ethical_locks_expires_at', 'ethical_locks', ['lock_expires_at'])
    op.create_index('idx_ethical_locks_created_at', 'ethical_locks', ['created_at'])
    
    # Create composite indexes for common queries
    op.create_index('idx_ethical_locks_clinic_status', 'ethical_locks', ['clinic_id', 'status'])
    op.create_index('idx_ethical_locks_resource_status', 'ethical_locks', ['resource_id', 'resource_type', 'status'])
    op.create_index('idx_ethical_locks_active_expires', 'ethical_locks', ['status', 'lock_expires_at'])
    
    # Create collision_detections table
    op.create_table('collision_detections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('collision_type', sa.String(), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('conflicting_resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('conflicting_resource_type', sa.String(), nullable=True),
        sa.Column('detection_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('severity', sa.String(), nullable=False, default='medium'),
        sa.Column('status', sa.String(), nullable=False, default='detected'),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.String(), nullable=True),
        sa.Column('requires_manual_review', sa.Boolean(), nullable=False, default=False),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes for collision_detections
    op.create_index('idx_collision_detections_clinic_id', 'collision_detections', ['clinic_id'])
    op.create_index('idx_collision_detections_collision_type', 'collision_detections', ['collision_type'])
    op.create_index('idx_collision_detections_resource', 'collision_detections', ['resource_id', 'resource_type'])
    op.create_index('idx_collision_detections_status', 'collision_detections', ['status'])
    op.create_index('idx_collision_detections_severity', 'collision_detections', ['severity'])
    op.create_index('idx_collision_detections_manual_review', 'collision_detections', ['requires_manual_review'])
    op.create_index('idx_collision_detections_created_at', 'collision_detections', ['created_at'])
    
    # Create composite indexes for collision_detections
    op.create_index('idx_collision_detections_clinic_status', 'collision_detections', ['clinic_id', 'status'])
    op.create_index('idx_collision_detections_type_status', 'collision_detections', ['collision_type', 'status'])
    op.create_index('idx_collision_detections_review_status', 'collision_detections', ['requires_manual_review', 'status'])
    
    # Create lock_audit_logs table
    op.create_table('lock_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lock_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('operation', sa.String(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_role', sa.String(), nullable=False),
        sa.Column('operation_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lock_id'], ['ethical_locks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes for lock_audit_logs
    op.create_index('idx_lock_audit_logs_clinic_id', 'lock_audit_logs', ['clinic_id'])
    op.create_index('idx_lock_audit_logs_lock_id', 'lock_audit_logs', ['lock_id'])
    op.create_index('idx_lock_audit_logs_operation', 'lock_audit_logs', ['operation'])
    op.create_index('idx_lock_audit_logs_user_id', 'lock_audit_logs', ['user_id'])
    op.create_index('idx_lock_audit_logs_success', 'lock_audit_logs', ['success'])
    op.create_index('idx_lock_audit_logs_created_at', 'lock_audit_logs', ['created_at'])
    
    # Create composite indexes for lock_audit_logs
    op.create_index('idx_lock_audit_logs_clinic_operation', 'lock_audit_logs', ['clinic_id', 'operation'])
    op.create_index('idx_lock_audit_logs_lock_operation', 'lock_audit_logs', ['lock_id', 'operation'])
    op.create_index('idx_lock_audit_logs_user_operation', 'lock_audit_logs', ['user_id', 'operation'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_ethical_locks_lock_type',
        'ethical_locks',
        "lock_type IN ('medical_record_edit', 'sadt_submission', 'tuss_submission', 'cid_diagnosis', 'prescription_edit', 'appointment_edit')"
    )
    
    op.create_check_constraint(
        'ck_ethical_locks_status',
        'ethical_locks',
        "status IN ('active', 'expired', 'released', 'force_unlocked')"
    )
    
    op.create_check_constraint(
        'ck_collision_detections_collision_type',
        'collision_detections',
        "collision_type IN ('duplicate_submission', 'cid_conflict', 'exam_conflict', 'medication_conflict', 'schedule_conflict')"
    )
    
    op.create_check_constraint(
        'ck_collision_detections_severity',
        'collision_detections',
        "severity IN ('low', 'medium', 'high', 'critical')"
    )
    
    op.create_check_constraint(
        'ck_collision_detections_status',
        'collision_detections',
        "status IN ('detected', 'reviewed', 'resolved', 'ignored')"
    )
    
    op.create_check_constraint(
        'ck_lock_audit_logs_operation',
        'lock_audit_logs',
        "operation IN ('acquire', 'release', 'heartbeat', 'extend', 'force_unlock', 'acquire_conflict', 'duplicate_submission_detected')"
    )
    
    op.create_check_constraint(
        'ck_lock_audit_logs_user_role',
        'lock_audit_logs',
        "user_role IN ('doctor', 'receptionist', 'admin', 'system')"
    )
    
    # Add updated_at trigger for ethical_locks
    op.execute("""
        CREATE TRIGGER trg_ethical_locks_set_updated_at
        BEFORE UPDATE ON ethical_locks
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    # Add updated_at trigger for collision_detections
    op.execute("""
        CREATE TRIGGER trg_collision_detections_set_updated_at
        BEFORE UPDATE ON collision_detections
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    # Add function to automatically expire locks
    op.execute("""
        CREATE OR REPLACE FUNCTION expire_ethical_locks()
        RETURNS INTEGER AS $$
        DECLARE
            expired_count INTEGER;
        BEGIN
            UPDATE ethical_locks 
            SET status = 'expired', updated_at = now()
            WHERE status = 'active' 
              AND lock_expires_at <= now();
            
            GET DIAGNOSTICS expired_count = ROW_COUNT;
            RETURN expired_count;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add function to prevent duplicate active locks
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_duplicate_active_locks()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Check if there's already an active lock for the same resource
            IF EXISTS (
                SELECT 1 FROM ethical_locks 
                WHERE clinic_id = NEW.clinic_id 
                  AND resource_id = NEW.resource_id 
                  AND resource_type = NEW.resource_type 
                  AND status = 'active' 
                  AND lock_expires_at > now()
                  AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid)
            ) THEN
                RAISE EXCEPTION 'Active lock already exists for this resource';
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add trigger to prevent duplicate active locks
    op.execute("""
        CREATE TRIGGER trg_ethical_locks_prevent_duplicates
        BEFORE INSERT OR UPDATE ON ethical_locks
        FOR EACH ROW
        EXECUTE FUNCTION prevent_duplicate_active_locks();
    """)
    
    # Add function to clean up expired locks
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_expired_locks()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Clean up expired locks when new locks are created
            PERFORM expire_ethical_locks();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Add trigger to clean up expired locks
    op.execute("""
        CREATE TRIGGER trg_ethical_locks_cleanup_expired
        AFTER INSERT ON ethical_locks
        FOR EACH ROW
        EXECUTE FUNCTION cleanup_expired_locks();
    """)
    
    # Add unique constraint for active locks per resource
    op.create_index(
        'ux_ethical_locks_active_resource',
        'ethical_locks',
        ['clinic_id', 'resource_id', 'resource_type'],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND lock_expires_at > now()")
    )


def downgrade():
    """Drop ethical locks and collision detection tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_ethical_locks_cleanup_expired ON ethical_locks;")
    op.execute("DROP TRIGGER IF EXISTS trg_ethical_locks_prevent_duplicates ON ethical_locks;")
    op.execute("DROP TRIGGER IF EXISTS trg_collision_detections_set_updated_at ON collision_detections;")
    op.execute("DROP TRIGGER IF EXISTS trg_ethical_locks_set_updated_at ON ethical_locks;")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_locks();")
    op.execute("DROP FUNCTION IF EXISTS prevent_duplicate_active_locks();")
    op.execute("DROP FUNCTION IF EXISTS expire_ethical_locks();")
    
    # Drop check constraints
    op.drop_constraint('ck_lock_audit_logs_user_role', 'lock_audit_logs', type_='check')
    op.drop_constraint('ck_lock_audit_logs_operation', 'lock_audit_logs', type_='check')
    op.drop_constraint('ck_collision_detections_status', 'collision_detections', type_='check')
    op.drop_constraint('ck_collision_detections_severity', 'collision_detections', type_='check')
    op.drop_constraint('ck_collision_detections_collision_type', 'collision_detections', type_='check')
    op.drop_constraint('ck_ethical_locks_status', 'ethical_locks', type_='check')
    op.drop_constraint('ck_ethical_locks_lock_type', 'ethical_locks', type_='check')
    
    # Drop tables
    op.drop_table('lock_audit_logs')
    op.drop_table('collision_detections')
    op.drop_table('ethical_locks')
