#!/usr/bin/env python3
"""
Fix tiss_jobs table structure to match SQLModel.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_tiss_jobs_table():
    """Fix tiss_jobs table structure."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('❌ DATABASE_URL not found in environment variables.')
        return

    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        print('🔄 Fixing tiss_jobs table structure...')
        
        # Add missing columns
        columns_to_add = [
            "invoice_id UUID",
            "procedure_code VARCHAR(50)",
            "payload JSONB DEFAULT '{}'",
            "response_data JSONB",
            "attempts INTEGER DEFAULT 0",
            "max_attempts INTEGER DEFAULT 3",
            "scheduled_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()",
            "processed_at TIMESTAMP WITHOUT TIME ZONE",
            "completed_at TIMESTAMP WITHOUT TIME ZONE",
            "last_error TEXT",
            "last_error_at TIMESTAMP WITHOUT TIME ZONE",
            "next_retry_at TIMESTAMP WITHOUT TIME ZONE",
            "ethical_lock_type VARCHAR(50)",
            "ethical_lock_reason TEXT",
            "manual_review_required BOOLEAN DEFAULT FALSE",
            "job_meta JSONB",
            "priority INTEGER DEFAULT 0"
        ]
        
        for column_def in columns_to_add:
            column_name = column_def.split()[0]
            
            # Check if column exists
            column_exists = await conn.fetchval(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'tiss_jobs' AND column_name = '{column_name}')"
            )
            
            if not column_exists:
                try:
                    await conn.execute(f"ALTER TABLE tiss_jobs ADD COLUMN {column_def};")
                    print(f'✅ Added column: {column_name}')
                except Exception as e:
                    print(f'⚠️ Error adding {column_name}: {e}')
            else:
                print(f'ℹ️ Column {column_name} already exists')
        
        # Add indexes
        indexes_to_add = [
            "CREATE INDEX IF NOT EXISTS idx_tiss_jobs_invoice_id ON tiss_jobs(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_tiss_jobs_status ON tiss_jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_tiss_jobs_scheduled_at ON tiss_jobs(scheduled_at)",
            "CREATE INDEX IF NOT EXISTS idx_tiss_jobs_priority ON tiss_jobs(priority)"
        ]
        
        for index_sql in indexes_to_add:
            try:
                await conn.execute(index_sql)
                print(f'✅ Added index: {index_sql.split()[-1]}')
            except Exception as e:
                print(f'⚠️ Error adding index: {e}')
        
        print('🎉 tiss_jobs table structure fixed successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_tiss_jobs_table())
