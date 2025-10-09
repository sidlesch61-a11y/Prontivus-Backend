"""
Database migration for AI consultation recording and summarization tables.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '0002_ai_consultation_tables'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None

def upgrade():
    """Create AI consultation tables."""
    
    # Create recordings table
    op.create_table(
        'recordings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('started_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consent_given', sa.Boolean(), nullable=False, default=False),
        sa.Column('consent_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('storage_path', sa.String(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'uploaded', 'processing', 'completed', 'failed', name='recordingstatus'), nullable=False, default='pending'),
        sa.Column('record_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['consultation_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['started_by'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes for recordings
    op.create_index('idx_recordings_consultation', 'recordings', ['consultation_id'])
    op.create_index('idx_recordings_started_by', 'recordings', ['started_by'])
    op.create_index('idx_recordings_status', 'recordings', ['status'])
    op.create_index('idx_recordings_created_at', 'recordings', ['created_at'])
    
    # Create ai_summaries table
    op.create_table(
        'ai_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recording_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stt_provider', sa.Enum('openai', 'google', 'azure', 'aws', name='sttprovider'), nullable=False, default='openai'),
        sa.Column('llm_provider', sa.Enum('openai', 'vertex', 'anthropic', name='llmprovider'), nullable=False, default='openai'),
        sa.Column('transcript_text', sa.Text(), nullable=True),
        sa.Column('summary_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='aisummarystatus'), nullable=False, default='pending'),
        sa.Column('processing_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('stt_cost', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('llm_cost', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='CASCADE')
    )
    
    # Create indexes for ai_summaries
    op.create_index('idx_ai_summaries_recording', 'ai_summaries', ['recording_id'])
    op.create_index('idx_ai_summaries_status', 'ai_summaries', ['status'])
    op.create_index('idx_ai_summaries_created_at', 'ai_summaries', ['created_at'])
    op.create_index('idx_ai_summaries_cost', 'ai_summaries', ['total_cost'])
    
    # Create updated_at trigger for recordings
    op.execute("""
        CREATE OR REPLACE FUNCTION update_recordings_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trg_recordings_updated_at
        BEFORE UPDATE ON recordings
        FOR EACH ROW EXECUTE FUNCTION update_recordings_updated_at();
    """)
    
    # Create updated_at trigger for ai_summaries
    op.execute("""
        CREATE OR REPLACE FUNCTION update_ai_summaries_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trg_ai_summaries_updated_at
        BEFORE UPDATE ON ai_summaries
        FOR EACH ROW EXECUTE FUNCTION update_ai_summaries_updated_at();
    """)

def downgrade():
    """Drop AI consultation tables."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS trg_ai_summaries_updated_at ON ai_summaries;")
    op.execute("DROP TRIGGER IF EXISTS trg_recordings_updated_at ON recordings;")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_ai_summaries_updated_at();")
    op.execute("DROP FUNCTION IF EXISTS update_recordings_updated_at();")
    
    # Drop tables
    op.drop_table('ai_summaries')
    op.drop_table('recordings')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS aisummarystatus;")
    op.execute("DROP TYPE IF EXISTS recordingstatus;")
    op.execute("DROP TYPE IF EXISTS llmprovider;")
    op.execute("DROP TYPE IF EXISTS sttprovider;")
