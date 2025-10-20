#!/usr/bin/env python3
"""
Debug admin authentication issue.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def debug_admin_auth():
    """Debug admin authentication."""
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
        
        # Check admin user details
        user = await conn.fetchrow(
            """
            SELECT id, email, role, is_active, clinic_id, created_at, updated_at
            FROM users 
            WHERE email = $1
            """,
            'admin@clinica.com.br'
        )
        
        if user:
            print(f'👤 Admin user details:')
            print(f'   ID: {user["id"]}')
            print(f'   Email: {user["email"]}')
            print(f'   Role: "{user["role"]}" (type: {type(user["role"])})')
            print(f'   Is Active: {user["is_active"]}')
            print(f'   Clinic ID: {user["clinic_id"]}')
            print(f'   Created: {user["created_at"]}')
            print(f'   Updated: {user["updated_at"]}')
            
            # Check if role is exactly 'admin'
            print(f'\n🔍 Role comparison tests:')
            print(f'   user["role"] == "admin": {user["role"] == "admin"}')
            print(f'   user["role"] == "admin": {repr(user["role"]) == repr("admin")}')
            print(f'   len(user["role"]): {len(user["role"])}')
            print(f'   repr(user["role"]): {repr(user["role"])}')
            
            # Check for any whitespace or hidden characters
            role_bytes = user["role"].encode('utf-8')
            print(f'   role bytes: {role_bytes}')
            
        else:
            print('❌ Admin user not found')
            
        # Check all users and their roles
        print('\n📋 All users and their roles:')
        all_users = await conn.fetch(
            """
            SELECT email, role, is_active, 
                   length(role) as role_length,
                   encode(role::bytea, 'hex') as role_hex
            FROM users 
            ORDER BY email
            """
        )
        
        for u in all_users:
            status = "✅" if u['is_active'] else "❌"
            print(f'  {status} {u["email"]}: role="{u["role"]}" (len={u["role_length"]}, hex={u["role_hex"]})')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(debug_admin_auth())
