"""Fix clinic status column - convert from ENUM to VARCHAR

Revision ID: 0015
Revises: 0014
Create Date: 2025-10-10 19:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    """Convert clinics.status from ENUM to VARCHAR and make nullable."""
    # Step 1: Alter the column to use VARCHAR instead of ENUM
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status TYPE VARCHAR USING status::text
    """)
    
    # Step 2: Make the column nullable
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status DROP NOT NULL
    """)
    
    # Step 3: Set default value
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status SET DEFAULT 'active'
    """)
    
    # Step 4: Update any NULL values to 'active'
    op.execute("""
        UPDATE clinics 
        SET status = 'active' 
        WHERE status IS NULL
    """)
    
    # Step 5: Try to drop the ENUM type if it exists
    try:
        op.execute("DROP TYPE IF EXISTS clinicstatus CASCADE")
    except Exception:
        pass  # Ignore if it doesn't exist


def downgrade():
    """Revert changes."""
    # Create the ENUM type
    op.execute("""
        CREATE TYPE clinicstatus AS ENUM ('active', 'inactive', 'suspended')
    """)
    
    # Convert back to ENUM
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status TYPE clinicstatus USING status::clinicstatus
    """)
    
    # Make NOT NULL again
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status SET NOT NULL
    """)

