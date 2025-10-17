#!/usr/bin/env python3
"""
Update user schema with roles and permissions.
This script uses the existing FastAPI database connection.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.db.session import get_db_session
from sqlmodel import text

async def update_user_schema():
    """Update the users table with roles and permissions columns."""
    
    print("🔄 Starting user schema update...")
    
    try:
        # Get database session
        async for db in get_db_session():
            print("✅ Connected to database")
            
            # Check if role column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'role'
            """))
            role_exists = result.fetchone() is not None
            
            if not role_exists:
                print("📝 Adding 'role' column...")
                await db.execute(text("""
                    ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'Médico'
                """))
                print("✅ 'role' column added")
            else:
                print("ℹ️ 'role' column already exists")
            
            # Check if permissions column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'permissions'
            """))
            permissions_exists = result.fetchone() is not None
            
            if not permissions_exists:
                print("📝 Adding 'permissions' column...")
                await db.execute(text("""
                    ALTER TABLE users ADD COLUMN permissions JSONB DEFAULT '{}'::jsonb
                """))
                print("✅ 'permissions' column added")
            else:
                print("ℹ️ 'permissions' column already exists")
            
            # Check if is_active column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'is_active'
            """))
            is_active_exists = result.fetchone() is not None
            
            if not is_active_exists:
                print("📝 Adding 'is_active' column...")
                await db.execute(text("""
                    ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE
                """))
                print("✅ 'is_active' column added")
            else:
                print("ℹ️ 'is_active' column already exists")
            
            # Check if created_by column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'created_by'
            """))
            created_by_exists = result.fetchone() is not None
            
            if not created_by_exists:
                print("📝 Adding 'created_by' column...")
                await db.execute(text("""
                    ALTER TABLE users ADD COLUMN created_by UUID REFERENCES users(id)
                """))
                print("✅ 'created_by' column added")
            else:
                print("ℹ️ 'created_by' column already exists")
            
            # Check if updated_by column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'updated_by'
            """))
            updated_by_exists = result.fetchone() is not None
            
            if not updated_by_exists:
                print("📝 Adding 'updated_by' column...")
                await db.execute(text("""
                    ALTER TABLE users ADD COLUMN updated_by UUID REFERENCES users(id)
                """))
                print("✅ 'updated_by' column added")
            else:
                print("ℹ️ 'updated_by' column already exists")
            
            # Check if last_login column exists
            result = await db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'last_login'
            """))
            last_login_exists = result.fetchone() is not None
            
            if not last_login_exists:
                print("📝 Adding 'last_login' column...")
                await db.execute(text("""
                    ALTER TABLE users ADD COLUMN last_login TIMESTAMP WITHOUT TIME ZONE
                """))
                print("✅ 'last_login' column added")
            else:
                print("ℹ️ 'last_login' column already exists")
            
            # Commit all changes
            await db.commit()
            print("✅ All changes committed to database")
            
            # Verify the changes
            print("\n🔍 Verifying changes...")
            
            # Get current users and their roles
            result = await db.execute(text("""
                SELECT name, email, role, is_active 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 5
            """))
            users = result.fetchall()
            
            print("\n👥 Current users and their roles:")
            for user in users:
                print(f"  - {user[0]} ({user[1]}) - Role: {user[2]} - Active: {user[3]}")
            
            print("\n🎉 User schema update completed successfully!")
            break
            
    except Exception as e:
        print(f"❌ Schema update failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(update_user_schema())
