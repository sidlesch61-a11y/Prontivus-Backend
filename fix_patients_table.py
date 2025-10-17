#!/usr/bin/env python3
"""
Fix patients table structure to match SQLModel.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_patients_table():
    """Fix patients table structure."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('❌ DATABASE_URL not found in environment variables.')
        return

    if database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)
        
        print('🔄 Fixing patients table structure...')
        
        # Add missing columns
        columns_to_add = [
            "city VARCHAR(255)"
        ]
        
        for column_def in columns_to_add:
            column_name = column_def.split()[0]
            
            # Check if column exists
            column_exists = await conn.fetchval(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'patients' AND column_name = '{column_name}')"
            )
            
            if not column_exists:
                try:
                    await conn.execute(f"ALTER TABLE patients ADD COLUMN {column_def};")
                    print(f'✅ Added column: {column_name}')
                except Exception as e:
                    print(f'⚠️ Error adding {column_name}: {e}')
            else:
                print(f'ℹ️ Column {column_name} already exists')
        
        print('🎉 patients table structure fixed successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_patients_table())
