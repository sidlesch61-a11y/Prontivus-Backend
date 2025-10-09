"""
Comprehensive database schema update for CliniCore/Prontivus with all new features.
"""

# Core Updates - Clinics, Users, and Roles
def upgrade_core_tables():
    """Update core tables with new features."""
    
    # Update users table
    op.add_column('users', sa.Column('twofa_enabled', sa.Boolean(), nullable=False, default=False))
    op.add_column('users', sa.Column('twofa_secret', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('crm_number', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('signature_cert_ref', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, default=True))
    
    # Update roles table for RBAC
    op.add_column('roles', sa.Column('permissions', postgresql.JSONB(), nullable=True))
    
    # Create user_roles junction table
    op.create_table('user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'role_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='CASCADE')
    )

# Advanced EMR Features
def create_emr_tables():
    """Create advanced EMR tables."""
    
    # AI-assisted consultation recordings
    op.create_table('consultation_recordings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recording_path', sa.Text(), nullable=False),
        sa.Column('transcript_text', sa.Text(), nullable=True),
        sa.Column('ai_summary', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Medical record attachments
    op.create_table('medical_record_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('medical_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['medical_record_id'], ['medical_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='CASCADE')
    )

# Digital Prescription System
def create_prescription_tables():
    """Create digital prescription tables."""
    
    op.create_table('digital_prescriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prescription_data', postgresql.JSONB(), nullable=False),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('signature_data', postgresql.JSONB(), nullable=True),
        sa.Column('qr_token', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='draft'),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )

# TISS Multi-Convênio Integration
def create_tiss_tables():
    """Create TISS integration tables."""
    
    op.create_table('tiss_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('api_endpoint', sa.Text(), nullable=False),
        sa.Column('credentials', postgresql.JSONB(), nullable=False),  # Encrypted
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_test_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_test_result', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    op.create_table('tiss_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('procedure_code', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['provider_id'], ['tiss_providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE')
    )

# Telemedicine Platform
def create_telemedicine_tables():
    """Create telemedicine tables."""
    
    op.create_table('telemedicine_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_token', sa.String(), nullable=False),
        sa.Column('room_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='scheduled'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recording_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('recording_path', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )

# Waiting Queue System
def create_waiting_queue_tables():
    """Create waiting queue tables."""
    
    op.create_table('waiting_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='waiting'),
        sa.Column('priority', sa.String(), nullable=False, default='normal'),
        sa.Column('estimated_wait_time', sa.Integer(), nullable=True),
        sa.Column('called_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consultation_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consultation_ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ondelete='CASCADE')
    )

# Ethical Locks (Trava Ética)
def create_ethical_locks_tables():
    """Create ethical locks tables."""
    
    op.create_table('ethical_locks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locked_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['locked_by'], ['users.id'], ondelete='CASCADE')
    )

# Audit and Security Tables
def create_audit_tables():
    """Create audit and security tables."""
    
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('old_values', postgresql.JSONB(), nullable=True),
        sa.Column('new_values', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    op.create_table('twofa_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('secret_encrypted', sa.Text(), nullable=False),
        sa.Column('backup_codes', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='disabled'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

# Offline Sync System
def create_sync_tables():
    """Create offline sync tables."""
    
    op.create_table('client_sync_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_event_id', sa.String(), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('server_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )

# Health Plan API Integration
def create_health_plan_tables():
    """Create health plan integration tables."""
    
    op.create_table('health_plan_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('api_endpoint', sa.Text(), nullable=False),
        sa.Column('oauth_config', postgresql.JSONB(), nullable=False),
        sa.Column('connection_status', sa.String(), nullable=False, default='disconnected'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )

# Indexes and Constraints
def create_indexes():
    """Create performance indexes."""
    
    # Users indexes
    op.create_index('idx_users_twofa_enabled', 'users', ['twofa_enabled'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    op.create_index('idx_users_crm_number', 'users', ['crm_number'])
    
    # EMR indexes
    op.create_index('idx_recordings_consultation', 'consultation_recordings', ['consultation_id'])
    op.create_index('idx_recordings_status', 'consultation_recordings', ['status'])
    op.create_index('idx_attachments_record', 'medical_record_attachments', ['medical_record_id'])
    
    # Prescription indexes
    op.create_index('idx_prescriptions_patient', 'digital_prescriptions', ['patient_id'])
    op.create_index('idx_prescriptions_status', 'digital_prescriptions', ['status'])
    op.create_index('idx_prescriptions_qr_token', 'digital_prescriptions', ['qr_token'])
    
    # TISS indexes
    op.create_index('idx_tiss_providers_clinic', 'tiss_providers', ['clinic_id'])
    op.create_index('idx_tiss_jobs_provider', 'tiss_jobs', ['provider_id'])
    op.create_index('idx_tiss_jobs_status', 'tiss_jobs', ['status'])
    
    # Telemedicine indexes
    op.create_index('idx_telemed_appointment', 'telemedicine_sessions', ['appointment_id'])
    op.create_index('idx_telemed_status', 'telemedicine_sessions', ['status'])
    op.create_index('idx_telemed_token', 'telemedicine_sessions', ['session_token'])
    
    # Waiting queue indexes
    op.create_index('idx_queue_clinic', 'waiting_queue', ['clinic_id'])
    op.create_index('idx_queue_position', 'waiting_queue', ['position'])
    op.create_index('idx_queue_status', 'waiting_queue', ['status'])
    
    # Ethical locks indexes
    op.create_index('idx_locks_resource', 'ethical_locks', ['resource_type', 'resource_id'])
    op.create_index('idx_locks_user', 'ethical_locks', ['locked_by'])
    op.create_index('idx_locks_status', 'ethical_locks', ['status'])
    
    # Audit indexes
    op.create_index('idx_audit_clinic', 'audit_logs', ['clinic_id'])
    op.create_index('idx_audit_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type'])
    op.create_index('idx_audit_created', 'audit_logs', ['created_at'])
    
    # Sync indexes
    op.create_index('idx_sync_clinic', 'client_sync_events', ['clinic_id'])
    op.create_index('idx_sync_client_id', 'client_sync_events', ['client_event_id'])
    op.create_index('idx_sync_idempotency', 'client_sync_events', ['idempotency_key'])
    op.create_index('idx_sync_status', 'client_sync_events', ['status'])

# Unique constraints for idempotency
def create_unique_constraints():
    """Create unique constraints for idempotency."""
    
    # Sync events idempotency
    op.create_index('ux_sync_clinic_client_id', 'client_sync_events', 
                   ['clinic_id', 'client_event_id'], unique=True)
    op.create_index('ux_sync_clinic_idempotency', 'client_sync_events', 
                   ['clinic_id', 'idempotency_key'], unique=True, 
                   postgresql_where=sa.text("idempotency_key IS NOT NULL"))
    
    # TISS jobs uniqueness
    op.create_index('ux_tiss_clinic_invoice_procedure', 'tiss_jobs', 
                   ['clinic_id', 'invoice_id', 'procedure_code'], unique=True)
    
    # Ethical locks uniqueness
    op.create_index('ux_locks_resource_active', 'ethical_locks', 
                   ['resource_type', 'resource_id'], unique=True,
                   postgresql_where=sa.text("status = 'active'"))

# Check constraints
def create_check_constraints():
    """Create check constraints for data integrity."""
    
    # User role constraints
    op.create_check_constraint('ck_users_role', 'users', 
                              "role IN ('admin','doctor','reception','finance','patient')")
    
    # Recording status constraints
    op.create_check_constraint('ck_recordings_status', 'consultation_recordings', 
                              "status IN ('pending','processing','completed','failed')")
    
    # Prescription status constraints
    op.create_check_constraint('ck_prescriptions_status', 'digital_prescriptions', 
                              "status IN ('draft','signed','verified','expired')")
    
    # TISS status constraints
    op.create_check_constraint('ck_tiss_jobs_status', 'tiss_jobs', 
                              "status IN ('pending','processing','completed','failed','retrying')")
    
    # Telemedicine status constraints
    op.create_check_constraint('ck_telemed_status', 'telemedicine_sessions', 
                              "status IN ('scheduled','active','ended','cancelled')")
    
    # Queue status constraints
    op.create_check_constraint('ck_queue_status', 'waiting_queue', 
                              "status IN ('waiting','called','in_consultation','completed','cancelled')")
    
    # Lock status constraints
    op.create_check_constraint('ck_locks_status', 'ethical_locks', 
                              "status IN ('active','expired','released','force_unlocked')")
    
    # 2FA status constraints
    op.create_check_constraint('ck_twofa_status', 'twofa_secrets', 
                              "status IN ('disabled','pending_setup','enabled','suspended')")

# Main upgrade function
def upgrade():
    """Main upgrade function."""
    upgrade_core_tables()
    create_emr_tables()
    create_prescription_tables()
    create_tiss_tables()
    create_telemedicine_tables()
    create_waiting_queue_tables()
    create_ethical_locks_tables()
    create_audit_tables()
    create_sync_tables()
    create_health_plan_tables()
    create_indexes()
    create_unique_constraints()
    create_check_constraints()

def downgrade():
    """Downgrade function."""
    # Drop all new tables and columns in reverse order
    pass
