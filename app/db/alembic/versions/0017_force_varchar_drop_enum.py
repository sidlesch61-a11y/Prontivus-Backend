"""Force conversion of status column to VARCHAR and drop ENUM

Revision ID: 0017
Revises: 0016
Create Date: 2025-10-10 20:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    """Force convert status to VARCHAR, bypassing all ENUM issues."""
    
    # Use raw SQL to force the conversion
    op.execute("""
        -- Step 1: Drop any defaults first
        ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT IF EXISTS;
    """)
    
    op.execute("""
        -- Step 2: Convert column type using CASE to handle any existing values
        ALTER TABLE clinics 
        ALTER COLUMN status TYPE VARCHAR 
        USING CASE 
            WHEN status::text = 'active' THEN 'active'
            WHEN status::text = 'inactive' THEN 'inactive'
            WHEN status::text = 'suspended' THEN 'suspended'
            WHEN status::text = 'trial' THEN 'trial'
            ELSE 'active'
        END;
    """)
    
    op.execute("""
        -- Step 3: Set NOT NULL constraint
        ALTER TABLE clinics ALTER COLUMN status SET NOT NULL;
    """)
    
    op.execute("""
        -- Step 4: Add default
        ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active';
    """)
    
    op.execute("""
        -- Step 5: Update any NULL or empty values
        UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = '';
    """)
    
    op.execute("""
        -- Step 6: Drop the ENUM type completely
        DROP TYPE IF EXISTS clinicstatus CASCADE;
    """)
    
    print("✅ Successfully converted status column from ENUM to VARCHAR")


def downgrade():
    """Revert to ENUM type."""
    # Recreate the enum
    op.execute("""
        CREATE TYPE clinicstatus AS ENUM ('active', 'inactive', 'suspended', 'trial');
    """)
    
    # Convert back to ENUM
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status TYPE clinicstatus USING status::clinicstatus;
    """)

