#!/usr/bin/env python3
"""
Check tiss_jobs table structure.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_tiss_jobs_table():
    """Check tiss_jobs table structure."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('❌ DATABASE_URL not found in environment variables.')
        return

    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check if tiss_jobs table exists
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tiss_jobs')"
        )
        print(f'ℹ️ tiss_jobs table exists: {table_exists}')
        
        if table_exists:
            # Check structure of tiss_jobs table
            columns = await conn.fetch(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'tiss_jobs' ORDER BY ordinal_position"
            )
            
            print('📊 tiss_jobs table structure:')
            for col in columns:
                print(f'  - {col["column_name"]}: {col["data_type"]}')
        else:
            print('❌ tiss_jobs table does not exist!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tiss_jobs_table())
