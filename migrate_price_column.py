#!/usr/bin/env python3
"""
Migration script to add price column to appointments table.
This fixes the CSV export error for appointments.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def add_price_column():
    """Add price column to appointments table and partitions."""
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
        
        # Check if price column already exists
        price_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'appointments' AND column_name = 'price')"
        )
        print(f'ℹ️ Price column exists: {price_exists}')
        
        if not price_exists:
            print('🔄 Adding price column to appointments table...')
            
            # Add price column to main appointments table
            await conn.execute('ALTER TABLE appointments ADD COLUMN price NUMERIC(10,2);')
            print('✅ Added price column to main appointments table')
            
            # Add price column to all existing partitions
            await conn.execute('ALTER TABLE appointments_2024 ADD COLUMN price NUMERIC(10,2);')
            print('✅ Added price column to appointments_2024 partition')
            
            await conn.execute('ALTER TABLE appointments_2025 ADD COLUMN price NUMERIC(10,2);')
            print('✅ Added price column to appointments_2025 partition')
            
            await conn.execute('ALTER TABLE appointments_2026 ADD COLUMN price NUMERIC(10,2);')
            print('✅ Added price column to appointments_2026 partition')
            
            # Add index for price column
            await conn.execute('CREATE INDEX idx_appointments_price ON appointments(price);')
            print('✅ Added index for price column')
            
            # Update existing appointments with default price
            await conn.execute('UPDATE appointments SET price = 150.00 WHERE price IS NULL;')
            print('✅ Updated existing appointments with default price')
            
            print('🎉 Price column migration completed successfully!')
        else:
            print('ℹ️ Price column already exists, no migration needed.')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(add_price_column())
