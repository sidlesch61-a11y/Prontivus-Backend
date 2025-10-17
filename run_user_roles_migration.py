#!/usr/bin/env python3
"""
Run user roles and permissions migration script.
"""

import asyncio
import asyncpg
import os
from pathlib import Path

async def run_migration():
    """Run the user roles and permissions migration."""
    
    # Database connection parameters
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/prontivus")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to database")
        
        # Read the migration SQL file
        migration_file = Path(__file__).parent / "add_user_roles_permissions.sql"
        
        if not migration_file.exists():
            print("❌ Migration file not found:", migration_file)
            return
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("📄 Running migration SQL...")
        
        # Execute the migration
        await conn.execute(migration_sql)
        
        print("✅ Migration completed successfully!")
        
        # Verify the changes
        print("\n🔍 Verifying changes...")
        
        # Check if role column exists
        role_check = await conn.fetchval("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'role'
        """)
        
        if role_check:
            print("✅ 'role' column added successfully")
        else:
            print("❌ 'role' column not found")
        
        # Check if permissions column exists
        permissions_check = await conn.fetchval("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'permissions'
        """)
        
        if permissions_check:
            print("✅ 'permissions' column added successfully")
        else:
            print("❌ 'permissions' column not found")
        
        # Check if is_active column exists
        is_active_check = await conn.fetchval("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'is_active'
        """)
        
        if is_active_check:
            print("✅ 'is_active' column added successfully")
        else:
            print("❌ 'is_active' column not found")
        
        # Show current user roles
        users = await conn.fetch("""
            SELECT name, email, role, is_active 
            FROM users 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        print("\n👥 Current users and their roles:")
        for user in users:
            print(f"  - {user['name']} ({user['email']}) - Role: {user['role']} - Active: {user['is_active']}")
        
        await conn.close()
        print("\n🎉 Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_migration())
