#!/usr/bin/env python3
"""
Check what appointments tables exist in the database.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_appointments_tables():
    """Check what appointments tables exist."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('❌ DATABASE_URL not found in environment variables.')
        return

    # Replace 'postgresql+asyncpg://' with 'postgresql://' for asyncpg.connect
    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check what tables exist with 'appointments' in the name
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%appointments%' ORDER BY table_name"
        )
        
        print('📋 Appointments-related tables found:')
        for table in tables:
            print(f'  - {table["table_name"]}')
        
        # Check if main appointments table has price column
        price_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'appointments' AND column_name = 'price')"
        )
        print(f'\n💰 Price column in appointments table: {price_exists}')
        
        # Check structure of main appointments table
        columns = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'appointments' ORDER BY ordinal_position"
        )
        
        print('\n📊 Appointments table structure:')
        for col in columns:
            print(f'  - {col["column_name"]}: {col["data_type"]}')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(check_appointments_tables())
