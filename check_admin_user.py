#!/usr/bin/env python3
"""
Script to check and fix admin user role.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import get_db_session
from app.models import User

async def check_and_fix_admin():
    """Check admin user role and fix if needed."""
    async with get_db_session() as db:
        # Check current admin user
        result = await db.execute(
            select(User).where(User.email == "admin@clinica.com.br")
        )
        user = result.scalar_one_or_none()
        
        if user:
            print(f"Found user: {user.email}")
            print(f"Current role: '{user.role}'")
            print(f"User ID: {user.id}")
            print(f"Clinic ID: {user.clinic_id}")
            print(f"Is Active: {user.is_active}")
            
            # Check if role is 'admin'
            if user.role != 'admin':
                print(f"\nUpdating role from '{user.role}' to 'admin'...")
                
                # Update the role
                await db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(role='admin')
                )
                await db.commit()
                print("✅ Role updated to 'admin'")
            else:
                print("✅ User already has 'admin' role")
        else:
            print("❌ User admin@clinica.com.br not found")
            
        # List all users to see their roles
        print("\nAll users in the system:")
        all_users_result = await db.execute(select(User))
        all_users = all_users_result.scalars().all()
        
        for u in all_users:
            print(f"  - {u.email}: role='{u.role}', active={u.is_active}")

if __name__ == "__main__":
    asyncio.run(check_and_fix_admin())
