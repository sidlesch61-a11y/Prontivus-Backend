"""Add offline sync events and idempotency system

Revision ID: 0009_sync_events_system
Revises: 0008_security_system
Create Date: 2024-01-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0009_sync_events_system'
down_revision = '0008_security_system'
branch_labels = None
depends_on = None


def upgrade():
    """Create offline sync events and idempotency system tables."""
    
    # Create client_sync_events table
    op.create_table('client_sync_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_event_id', sa.String(), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('client_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False),
        sa.Column('server_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('processing_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('processing_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # Create indexes for client_sync_events
    op.create_index('idx_client_sync_events_clinic_id', 'client_sync_events', ['clinic_id'])
    op.create_index('idx_client_sync_events_client_event_id', 'client_sync_events', ['client_event_id'])
    op.create_index('idx_client_sync_events_idempotency_key', 'client_sync_events', ['idempotency_key'])
    op.create_index('idx_client_sync_events_event_type', 'client_sync_events', ['event_type'])
    op.create_index('idx_client_sync_events_status', 'client_sync_events', ['status'])
    op.create_index('idx_client_sync_events_processed', 'client_sync_events', ['processed'])
    op.create_index('idx_client_sync_events_server_entity_id', 'client_sync_events', ['server_entity_id'])
    op.create_index('idx_client_sync_events_created_at', 'client_sync_events', ['created_at'])
    op.create_index('idx_client_sync_events_processed_at', 'client_sync_events', ['processed_at'])
    
    # Create unique constraint for idempotency
    op.create_index('ux_client_sync_events_clinic_client_id', 'client_sync_events', ['clinic_id', 'client_event_id'], unique=True)
    op.create_index('ux_client_sync_events_clinic_idempotency', 'client_sync_events', ['clinic_id', 'idempotency_key'], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"))
    
    # Create sync_batches table
    op.create_table('sync_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_id', sa.String(), nullable=False),
        sa.Column('client_batch_id', sa.String(), nullable=True),
        sa.Column('total_events', sa.Integer(), nullable=False),
        sa.Column('processed_events', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_events', sa.Integer(), nullable=False, default=0),
        sa.Column('skipped_events', sa.Integer(), nullable=False, default=0),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('has_errors', sa.Boolean(), nullable=False, default=False),
        sa.Column('error_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # Create indexes for sync_batches
    op.create_index('idx_sync_batches_clinic_id', 'sync_batches', ['clinic_id'])
    op.create_index('idx_sync_batches_batch_id', 'sync_batches', ['batch_id'])
    op.create_index('idx_sync_batches_client_batch_id', 'sync_batches', ['client_batch_id'])
    op.create_index('idx_sync_batches_status', 'sync_batches', ['status'])
    op.create_index('idx_sync_batches_has_errors', 'sync_batches', ['has_errors'])
    op.create_index('idx_sync_batches_created_at', 'sync_batches', ['created_at'])
    op.create_index('idx_sync_batches_processing_started_at', 'sync_batches', ['processing_started_at'])
    op.create_index('idx_sync_batches_processing_completed_at', 'sync_batches', ['processing_completed_at'])
    
    # Create unique constraint for batch_id
    op.create_index('ux_sync_batches_clinic_batch_id', 'sync_batches', ['clinic_id', 'batch_id'], unique=True)
    
    # Create sync_conflicts table
    op.create_table('sync_conflicts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sync_event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conflict_type', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('server_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('conflict_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sync_event_id'], ['client_sync_events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes for sync_conflicts
    op.create_index('idx_sync_conflicts_clinic_id', 'sync_conflicts', ['clinic_id'])
    op.create_index('idx_sync_conflicts_sync_event_id', 'sync_conflicts', ['sync_event_id'])
    op.create_index('idx_sync_conflicts_conflict_type', 'sync_conflicts', ['conflict_type'])
    op.create_index('idx_sync_conflicts_entity_type', 'sync_conflicts', ['entity_type'])
    op.create_index('idx_sync_conflicts_entity_id', 'sync_conflicts', ['entity_id'])
    op.create_index('idx_sync_conflicts_status', 'sync_conflicts', ['status'])
    op.create_index('idx_sync_conflicts_resolved_by', 'sync_conflicts', ['resolved_by'])
    op.create_index('idx_sync_conflicts_resolved_at', 'sync_conflicts', ['resolved_at'])
    op.create_index('idx_sync_conflicts_created_at', 'sync_conflicts', ['created_at'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_client_sync_events_event_type',
        'client_sync_events',
        "event_type IN ('create_patient', 'update_patient', 'delete_patient', 'create_appointment', 'update_appointment', 'delete_appointment', 'create_medical_record', 'update_medical_record', 'delete_medical_record', 'create_prescription', 'update_prescription', 'delete_prescription', 'create_invoice', 'update_invoice', 'delete_invoice', 'create_file', 'update_file', 'delete_file')"
    )
    
    op.create_check_constraint(
        'ck_client_sync_events_status',
        'client_sync_events',
        "status IN ('pending', 'processing', 'processed', 'failed', 'retrying', 'skipped')"
    )
    
    op.create_check_constraint(
        'ck_sync_batches_status',
        'sync_batches',
        "status IN ('pending', 'processing', 'processed', 'failed', 'retrying', 'skipped')"
    )
    
    op.create_check_constraint(
        'ck_sync_conflicts_status',
        'sync_conflicts',
        "status IN ('pending', 'resolved', 'ignored')"
    )
    
    op.create_check_constraint(
        'ck_sync_conflicts_resolution',
        'sync_conflicts',
        "resolution IN ('client_wins', 'server_wins', 'manual')"
    )
    
    # Add updated_at triggers
    op.execute("""
        CREATE TRIGGER trg_client_sync_events_set_updated_at
        BEFORE UPDATE ON client_sync_events
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_sync_batches_set_updated_at
        BEFORE UPDATE ON sync_batches
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_sync_conflicts_set_updated_at
        BEFORE UPDATE ON sync_conflicts
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    # Create function for automatic conflict detection
    op.execute("""
        CREATE OR REPLACE FUNCTION detect_sync_conflict()
        RETURNS TRIGGER AS $$
        BEGIN
            -- This function would be called to detect conflicts
            -- Implementation depends on specific business rules
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for conflict detection
    op.execute("""
        CREATE TRIGGER trg_client_sync_events_detect_conflict
        AFTER INSERT OR UPDATE ON client_sync_events
        FOR EACH ROW
        EXECUTE FUNCTION detect_sync_conflict();
    """)


def downgrade():
    """Drop offline sync events and idempotency system tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_client_sync_events_detect_conflict ON client_sync_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_conflicts_set_updated_at ON sync_conflicts;")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_batches_set_updated_at ON sync_batches;")
    op.execute("DROP TRIGGER IF EXISTS trg_client_sync_events_set_updated_at ON client_sync_events;")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS detect_sync_conflict();")
    
    # Drop check constraints
    op.drop_constraint('ck_sync_conflicts_resolution', 'sync_conflicts', type_='check')
    op.drop_constraint('ck_sync_conflicts_status', 'sync_conflicts', type_='check')
    op.drop_constraint('ck_sync_batches_status', 'sync_batches', type_='check')
    op.drop_constraint('ck_client_sync_events_status', 'client_sync_events', type_='check')
    op.drop_constraint('ck_client_sync_events_event_type', 'client_sync_events', type_='check')
    
    # Drop tables
    op.drop_table('sync_conflicts')
    op.drop_table('sync_batches')
    op.drop_table('client_sync_events')
