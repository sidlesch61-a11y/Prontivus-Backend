"""Make prescription record_id nullable

Revision ID: 0018
Revises: 0017
Create Date: 2025-10-11 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    """Make prescriptions.record_id nullable."""
    op.execute("""
        ALTER TABLE prescriptions 
        ALTER COLUMN record_id DROP NOT NULL
    """)


def downgrade():
    """Revert prescriptions.record_id to NOT NULL."""
    # First update any NULL values
    op.execute("""
        UPDATE prescriptions 
        SET record_id = '00000000-0000-0000-0000-000000000000' 
        WHERE record_id IS NULL
    """)
    
    op.execute("""
        ALTER TABLE prescriptions 
        ALTER COLUMN record_id SET NOT NULL
    """)

