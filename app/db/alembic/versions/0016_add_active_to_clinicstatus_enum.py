"""Add 'active' value to clinicstatus enum if missing

Revision ID: 0016
Revises: 0015
Create Date: 2025-10-10 19:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    """Add missing values to clinicstatus enum, or convert to VARCHAR."""
    
    # Try to add values to the enum
    try:
        # Check if the enum exists
        op.execute("""
            DO $$
            BEGIN
                -- Try to add 'active' if it doesn't exist
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'active' 
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'clinicstatus')
                ) THEN
                    ALTER TYPE clinicstatus ADD VALUE 'active';
                END IF;
                
                -- Try to add 'trial' if it doesn't exist
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'trial' 
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'clinicstatus')
                ) THEN
                    ALTER TYPE clinicstatus ADD VALUE 'trial';
                END IF;
            EXCEPTION
                WHEN OTHERS THEN
                    -- If enum operations fail, convert to VARCHAR
                    RAISE NOTICE 'ENUM operations failed, converting to VARCHAR';
                    
                    -- Drop default
                    ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT;
                    
                    -- Convert to VARCHAR
                    ALTER TABLE clinics ALTER COLUMN status TYPE VARCHAR USING status::text;
                    
                    -- Set default
                    ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active';
                    
                    -- Update NULLs
                    UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = '';
                    
                    -- Drop ENUM type
                    DROP TYPE IF EXISTS clinicstatus CASCADE;
            END $$;
        """)
    except Exception as e:
        print(f"Migration warning: {e}")
        # Fallback: Just convert to VARCHAR
        op.execute("""
            ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT;
            ALTER TABLE clinics ALTER COLUMN status TYPE VARCHAR USING status::text;
            ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active';
            UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = '';
            DROP TYPE IF EXISTS clinicstatus CASCADE;
        """)


def downgrade():
    """Revert changes."""
    # Recreate the enum
    op.execute("""
        CREATE TYPE clinicstatus AS ENUM ('active', 'inactive', 'suspended', 'trial');
    """)
    
    # Convert back to ENUM
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status TYPE clinicstatus USING status::clinicstatus;
    """)

