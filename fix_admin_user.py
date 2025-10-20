#!/usr/bin/env python3
"""
Fix admin user role in the database.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_admin_user():
    """Fix admin user role."""
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
        print('✅ Connected to database')
        
        # Check current admin user
        user = await conn.fetchrow(
            "SELECT id, email, role, is_active, clinic_id FROM users WHERE email = $1",
            'admin@clinica.com.br'
        )
        
        if user:
            print(f'👤 Found user: {user["email"]}')
            print(f'   Current role: "{user["role"]}"')
            print(f'   Is active: {user["is_active"]}')
            print(f'   Clinic ID: {user["clinic_id"]}')
            
            if user['role'] != 'admin':
                print(f'🔧 Updating role from "{user["role"]}" to "admin"...')
                
                # Update the role
                result = await conn.execute(
                    "UPDATE users SET role = $1 WHERE email = $2",
                    'admin', 'admin@clinica.com.br'
                )
                
                print(f'✅ Updated {result.split()[-1]} user(s)')
                
                # Verify the update
                updated_user = await conn.fetchrow(
                    "SELECT id, email, role, is_active, clinic_id FROM users WHERE email = $1",
                    'admin@clinica.com.br'
                )
                
                print(f'✅ Verified - New role: "{updated_user["role"]}"')
            else:
                print('✅ User already has "admin" role')
        else:
            print('❌ User admin@clinica.com.br not found')
            
        # List all users to see their roles
        print('\n📋 All users in the system:')
        all_users = await conn.fetch(
            "SELECT email, role, is_active FROM users ORDER BY email"
        )
        
        for u in all_users:
            status = "✅" if u['is_active'] else "❌"
            print(f'  {status} {u["email"]}: role="{u["role"]}"')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_admin_user())
