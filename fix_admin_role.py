#!/usr/bin/env python3
"""
Script to fix admin user role.
"""

import asyncio
import os
import sys
from sqlalchemy import text

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import get_db_session

async def fix_admin_role():
    """Fix admin user role."""
    async for db in get_db_session():
        try:
            # Update the admin user role
            result = await db.execute(
                text("UPDATE users SET role = 'admin' WHERE email = 'admin@clinica.com.br'")
            )
            await db.commit()
            
            print(f"Updated {result.rowcount} user(s)")
            
            # Check the result
            check_result = await db.execute(
                text("SELECT id, email, role, is_active, clinic_id FROM users WHERE email = 'admin@clinica.com.br'")
            )
            user = check_result.fetchone()
            
            if user:
                print(f"✅ Admin user found:")
                print(f"  ID: {user[0]}")
                print(f"  Email: {user[1]}")
                print(f"  Role: {user[2]}")
                print(f"  Active: {user[3]}")
                print(f"  Clinic ID: {user[4]}")
            else:
                print("❌ Admin user not found")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            await db.rollback()
        break

if __name__ == "__main__":
    asyncio.run(fix_admin_role())
