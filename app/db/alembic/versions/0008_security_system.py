"""Add 2FA, RBAC, and comprehensive audit system

Revision ID: 0008_security_system
Revises: 0007_ethical_locks_tables
Create Date: 2024-01-15 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0008_security_system'
down_revision = '0007_ethical_locks_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create 2FA, RBAC, and audit system tables."""
    
    # Add 2FA columns to users table
    op.add_column('users', sa.Column('twofa_enabled', sa.Boolean(), nullable=False, default=False))
    op.add_column('users', sa.Column('twofa_secret', sa.String(), nullable=True))
    
    # Create twofa_secrets table
    op.create_table('twofa_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('secret_encrypted', sa.String(), nullable=False),
        sa.Column('backup_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='disabled'),
        sa.Column('setup_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('issuer', sa.String(), nullable=False, default='Prontivus'),
        sa.Column('algorithm', sa.String(), nullable=False, default='SHA1'),
        sa.Column('digits', sa.Integer(), nullable=False, default=6),
        sa.Column('period', sa.Integer(), nullable=False, default=30),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create indexes for twofa_secrets
    op.create_index('idx_twofa_secrets_user_id', 'twofa_secrets', ['user_id'])
    op.create_index('idx_twofa_secrets_clinic_id', 'twofa_secrets', ['clinic_id'])
    op.create_index('idx_twofa_secrets_status', 'twofa_secrets', ['status'])
    op.create_index('idx_twofa_secrets_locked_until', 'twofa_secrets', ['locked_until'])
    
    # Create roles table
    op.create_table('roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, default=False),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('permissions_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('role_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE')
    )
    
    # Create indexes for roles
    op.create_index('idx_roles_clinic_id', 'roles', ['clinic_id'])
    op.create_index('idx_roles_name', 'roles', ['name'])
    op.create_index('idx_roles_is_system_role', 'roles', ['is_system_role'])
    op.create_index('idx_roles_is_active', 'roles', ['is_active'])
    
    # Create unique constraint for role names per clinic
    op.create_index('ux_roles_clinic_name', 'roles', ['clinic_id', 'name'], unique=True)
    
    # Create user_roles table
    op.create_table('user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assignment_reason', sa.String(), nullable=True),
        sa.Column('assignment_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes for user_roles
    op.create_index('idx_user_roles_user_id', 'user_roles', ['user_id'])
    op.create_index('idx_user_roles_role_id', 'user_roles', ['role_id'])
    op.create_index('idx_user_roles_clinic_id', 'user_roles', ['clinic_id'])
    op.create_index('idx_user_roles_assigned_by', 'user_roles', ['assigned_by'])
    op.create_index('idx_user_roles_is_active', 'user_roles', ['is_active'])
    op.create_index('idx_user_roles_expires_at', 'user_roles', ['expires_at'])
    
    # Create permissions table
    op.create_table('permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=True),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create indexes for permissions
    op.create_index('idx_permissions_name', 'permissions', ['name'])
    op.create_index('idx_permissions_category', 'permissions', ['category'])
    op.create_index('idx_permissions_resource_type', 'permissions', ['resource_type'])
    op.create_index('idx_permissions_action', 'permissions', ['action'])
    op.create_index('idx_permissions_is_active', 'permissions', ['is_active'])
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('user_role', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('severity', sa.String(), nullable=False, default='medium'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes for audit_logs
    op.create_index('idx_audit_logs_clinic_id', 'audit_logs', ['clinic_id'])
    op.create_index('idx_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_logs_resource_type', 'audit_logs', ['resource_type'])
    op.create_index('idx_audit_logs_resource_id', 'audit_logs', ['resource_id'])
    op.create_index('idx_audit_logs_endpoint', 'audit_logs', ['endpoint'])
    op.create_index('idx_audit_logs_method', 'audit_logs', ['method'])
    op.create_index('idx_audit_logs_severity', 'audit_logs', ['severity'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('idx_audit_logs_is_sensitive', 'audit_logs', ['is_sensitive'])
    
    # Create composite indexes for audit_logs
    op.create_index('idx_audit_logs_clinic_action', 'audit_logs', ['clinic_id', 'action'])
    op.create_index('idx_audit_logs_clinic_created', 'audit_logs', ['clinic_id', 'created_at'])
    op.create_index('idx_audit_logs_user_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('idx_audit_logs_resource_action', 'audit_logs', ['resource_type', 'action'])
    
    # Add check constraints
    op.create_check_constraint(
        'ck_twofa_secrets_status',
        'twofa_secrets',
        "status IN ('disabled', 'pending_setup', 'enabled', 'suspended')"
    )
    
    op.create_check_constraint(
        'ck_audit_logs_action',
        'audit_logs',
        "action IN ('create', 'read', 'update', 'delete', 'login', 'logout', '2fa_setup', '2fa_verify', '2fa_disable', 'permission_grant', 'permission_revoke', 'force_unlock', 'export_data', 'import_data')"
    )
    
    op.create_check_constraint(
        'ck_audit_logs_severity',
        'audit_logs',
        "severity IN ('low', 'medium', 'high', 'critical')"
    )
    
    op.create_check_constraint(
        'ck_permissions_category',
        'permissions',
        "category IN ('user_management', 'patient_management', 'appointment_management', 'medical_records', 'prescriptions', 'invoices', 'reports', 'system_admin', 'audit_logs', 'licenses', 'integrations')"
    )
    
    # Add updated_at triggers
    op.execute("""
        CREATE TRIGGER trg_twofa_secrets_set_updated_at
        BEFORE UPDATE ON twofa_secrets
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_roles_set_updated_at
        BEFORE UPDATE ON roles
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_user_roles_set_updated_at
        BEFORE UPDATE ON user_roles
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    op.execute("""
        CREATE TRIGGER trg_permissions_set_updated_at
        BEFORE UPDATE ON permissions
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    """)
    
    # Insert default permissions
    default_permissions = [
        # User Management
        ("users.create", "user_management", "Create users"),
        ("users.read", "user_management", "Read user information"),
        ("users.update", "user_management", "Update user information"),
        ("users.delete", "user_management", "Delete users"),
        
        # Patient Management
        ("patients.create", "patient_management", "Create patients"),
        ("patients.read", "patient_management", "Read patient information"),
        ("patients.update", "patient_management", "Update patient information"),
        ("patients.delete", "patient_management", "Delete patients"),
        
        # Medical Records
        ("medical_records.create", "medical_records", "Create medical records"),
        ("medical_records.read", "medical_records", "Read medical records"),
        ("medical_records.update", "medical_records", "Update medical records"),
        ("medical_records.delete", "medical_records", "Delete medical records"),
        
        # System Administration
        ("system.admin", "system_admin", "System administration"),
        ("audit_logs.read", "audit_logs", "Read audit logs"),
        ("licenses.manage", "licenses", "Manage licenses"),
    ]
    
    for name, category, description in default_permissions:
        op.execute(f"""
            INSERT INTO permissions (id, name, category, description, is_active, created_at, updated_at)
            VALUES (gen_random_uuid(), '{name}', '{category}', '{description}', true, now(), now());
        """)


def downgrade():
    """Drop 2FA, RBAC, and audit system tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_permissions_set_updated_at ON permissions;")
    op.execute("DROP TRIGGER IF EXISTS trg_user_roles_set_updated_at ON user_roles;")
    op.execute("DROP TRIGGER IF EXISTS trg_roles_set_updated_at ON roles;")
    op.execute("DROP TRIGGER IF EXISTS trg_twofa_secrets_set_updated_at ON twofa_secrets;")
    
    # Drop check constraints
    op.drop_constraint('ck_permissions_category', 'permissions', type_='check')
    op.drop_constraint('ck_audit_logs_severity', 'audit_logs', type_='check')
    op.drop_constraint('ck_audit_logs_action', 'audit_logs', type_='check')
    op.drop_constraint('ck_twofa_secrets_status', 'twofa_secrets', type_='check')
    
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('permissions')
    op.drop_table('user_roles')
    op.drop_table('roles')
    op.drop_table('twofa_secrets')
    
    # Remove columns from users table
    op.drop_column('users', 'twofa_secret')
    op.drop_column('users', 'twofa_enabled')
