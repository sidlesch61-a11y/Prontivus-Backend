#!/usr/bin/env python3
"""
Add status column to tiss_providers table.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def add_status_column():
    """Add status column to tiss_providers table."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('❌ DATABASE_URL not found in environment variables.')
        return

    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check if status column already exists
        status_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'tiss_providers' AND column_name = 'status')"
        )
        print(f'ℹ️ Status column exists: {status_exists}')
        
        if not status_exists:
            print('🔄 Adding status column to tiss_providers table...')
            
            # Add status column
            await conn.execute("ALTER TABLE tiss_providers ADD COLUMN status VARCHAR(50) DEFAULT 'active';")
            print('✅ Added status column to tiss_providers table')
            
            # Update existing records to have 'active' status
            await conn.execute("UPDATE tiss_providers SET status = 'active' WHERE status IS NULL;")
            print('✅ Updated existing records with default status')
            
            print('🎉 Status column migration completed successfully!')
        else:
            print('ℹ️ Status column already exists, no migration needed.')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(add_status_column())
