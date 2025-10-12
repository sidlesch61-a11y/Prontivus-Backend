"""Add 2FA tables and enhanced security

Revision ID: 0020_add_2fa_tables
Revises: 0019_appointment_requests
Create Date: 2025-10-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0020_add_2fa_tables'
down_revision = '0019_appointment_requests'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 2FA and security tables."""
    
    # Create two_fa_secrets table
    op.create_table('two_fa_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('secret_encrypted', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('backup_codes_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('enabled_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create indexes for 2FA table
    op.create_index('idx_two_fa_user', 'two_fa_secrets', ['user_id'])
    op.create_index('idx_two_fa_status', 'two_fa_secrets', ['status'])
    
    # Add 2FA fields to users table
    op.add_column('users', sa.Column('two_fa_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('two_fa_verified_at', sa.DateTime(), nullable=True))
    
    # Create security_settings table for clinic-wide security policies
    op.create_table('security_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinic_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('require_2fa_for_roles', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('session_timeout_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('max_login_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('lockout_duration_minutes', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('password_min_length', sa.Integer(), nullable=False, server_default='8'),
        sa.Column('password_require_special', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clinic_id')
    )
    
    # Create login_attempts table for tracking failed logins
    op.create_table('login_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for login_attempts
    op.create_index('idx_login_attempts_user', 'login_attempts', ['user_id'])
    op.create_index('idx_login_attempts_email', 'login_attempts', ['email'])
    op.create_index('idx_login_attempts_attempted_at', 'login_attempts', ['attempted_at'])
    
    # Insert default security settings for existing clinics
    op.execute("""
        INSERT INTO security_settings (
            id, clinic_id, require_2fa_for_roles, session_timeout_minutes,
            max_login_attempts, lockout_duration_minutes, password_min_length,
            password_require_special, updated_at
        )
        SELECT 
            gen_random_uuid(),
            id,
            ARRAY['admin', 'doctor', 'superadmin'],
            60,
            5,
            15,
            8,
            true,
            NOW()
        FROM clinics
        WHERE NOT EXISTS (
            SELECT 1 FROM security_settings WHERE security_settings.clinic_id = clinics.id
        )
    """)


def downgrade() -> None:
    """Remove 2FA and security tables."""
    op.drop_table('login_attempts')
    op.drop_table('security_settings')
    op.drop_column('users', 'two_fa_verified_at')
    op.drop_column('users', 'two_fa_enabled')
    op.drop_index('idx_two_fa_status', table_name='two_fa_secrets')
    op.drop_index('idx_two_fa_user', table_name='two_fa_secrets')
    op.drop_table('two_fa_secrets')

