"""Add exam database and insurance pricing tables

Revision ID: 0022
Revises: 0021_create_consultations_table
Create Date: 2024-10-17 05:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0022'
down_revision = '0021_create_consultations_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create exam_categories table
    op.create_table('exam_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.VARCHAR(), nullable=False),
        sa.Column('description', sa.VARCHAR(), nullable=True),
        sa.Column('color', sa.VARCHAR(), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exam_categories_name'), 'exam_categories', ['name'], unique=False)
    
    # Create standard_exams table
    op.create_table('standard_exams',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.VARCHAR(), nullable=False),
        sa.Column('tuss_code', sa.VARCHAR(), nullable=False),
        sa.Column('category', sa.VARCHAR(), nullable=False),
        sa.Column('description', sa.VARCHAR(), nullable=True),
        sa.Column('preparation_instructions', sa.VARCHAR(), nullable=True),
        sa.Column('normal_values', sa.VARCHAR(), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_standard_exams_name'), 'standard_exams', ['name'], unique=False)
    op.create_index(op.f('ix_standard_exams_tuss_code'), 'standard_exams', ['tuss_code'], unique=False)
    
    # Create insurance_providers table
    op.create_table('insurance_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.VARCHAR(), nullable=False),
        sa.Column('code', sa.VARCHAR(), nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_insurance_providers_name'), 'insurance_providers', ['name'], unique=True)
    op.create_index(op.f('ix_insurance_providers_code'), 'insurance_providers', ['code'], unique=True)
    
    # Create service_pricing table
    op.create_table('service_pricing',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('insurance_provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_type', sa.VARCHAR(), nullable=False),
        sa.Column('service_name', sa.VARCHAR(), nullable=False),
        sa.Column('base_price', sa.Float(), nullable=False),
        sa.Column('insurance_price', sa.Float(), nullable=False),
        sa.Column('discount_percentage', sa.Float(), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['insurance_provider_id'], ['insurance_providers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create pricing_rules table
    op.create_table('pricing_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('insurance_provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_type', sa.VARCHAR(), nullable=False),
        sa.Column('rule_value', sa.Float(), nullable=False),
        sa.Column('min_amount', sa.Float(), nullable=True),
        sa.Column('max_amount', sa.Float(), nullable=True),
        sa.Column('service_type', sa.VARCHAR(), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['insurance_provider_id'], ['insurance_providers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('pricing_rules')
    op.drop_table('service_pricing')
    op.drop_table('insurance_providers')
    op.drop_index(op.f('ix_standard_exams_tuss_code'), table_name='standard_exams')
    op.drop_index(op.f('ix_standard_exams_name'), table_name='standard_exams')
    op.drop_table('standard_exams')
    op.drop_index(op.f('ix_exam_categories_name'), table_name='exam_categories')
    op.drop_table('exam_categories')
