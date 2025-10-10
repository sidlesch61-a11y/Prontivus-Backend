"""Add default value for clinic status

Revision ID: 0014
Revises: 0013
Create Date: 2025-10-10 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    """Add default value for clinics.status column."""
    # Set default value for status column
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status SET DEFAULT 'active'
    """)
    
    # Update any NULL status values to 'active'
    op.execute("""
        UPDATE clinics 
        SET status = 'active' 
        WHERE status IS NULL
    """)


def downgrade():
    """Remove default value from clinics.status column."""
    op.execute("""
        ALTER TABLE clinics 
        ALTER COLUMN status DROP DEFAULT
    """)

