#!/usr/bin/env python3
"""
Fix tiss_providers table structure to match SQLModel.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_tiss_providers_table():
    """Fix tiss_providers table structure."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('❌ DATABASE_URL not found in environment variables.')
        return

    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        print('🔄 Fixing tiss_providers table structure...')
        
        # Add missing columns
        columns_to_add = [
            "cnpj VARCHAR(18)",
            "endpoint_url TEXT",
            "environment VARCHAR(20) DEFAULT 'production'",
            "username VARCHAR(255)",
            "password_encrypted TEXT",
            "certificate_path TEXT",
            "timeout_seconds INTEGER DEFAULT 30",
            "max_retries INTEGER DEFAULT 3",
            "retry_delay_seconds INTEGER DEFAULT 60",
            "last_test_result JSONB",
            "last_tested_at TIMESTAMP WITHOUT TIME ZONE",
            "last_successful_request TIMESTAMP WITHOUT TIME ZONE",
            "config_meta JSONB DEFAULT '{}'",
            "notes TEXT"
        ]
        
        for column_def in columns_to_add:
            column_name = column_def.split()[0]
            
            # Check if column exists
            column_exists = await conn.fetchval(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'tiss_providers' AND column_name = '{column_name}')"
            )
            
            if not column_exists:
                try:
                    await conn.execute(f"ALTER TABLE tiss_providers ADD COLUMN {column_def};")
                    print(f'✅ Added column: {column_name}')
                except Exception as e:
                    print(f'⚠️ Error adding {column_name}: {e}')
            else:
                print(f'ℹ️ Column {column_name} already exists')
        
        # Add indexes
        indexes_to_add = [
            "CREATE INDEX IF NOT EXISTS idx_tiss_providers_cnpj ON tiss_providers(cnpj)",
            "CREATE INDEX IF NOT EXISTS idx_tiss_providers_environment ON tiss_providers(environment)",
            "CREATE INDEX IF NOT EXISTS idx_tiss_providers_status ON tiss_providers(status)"
        ]
        
        for index_sql in indexes_to_add:
            try:
                await conn.execute(index_sql)
                print(f'✅ Added index: {index_sql.split()[-1]}')
            except Exception as e:
                print(f'⚠️ Error adding index: {e}')
        
        print('🎉 tiss_providers table structure fixed successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_tiss_providers_table())
