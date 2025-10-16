#!/usr/bin/env python3
"""
Fix exam_requests table foreign key constraint issue.
Remove the foreign key constraint on tiss_guide_id since tiss_guides table doesn't exist.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_exam_requests_foreign_key():
    """Remove foreign key constraint from exam_requests.tiss_guide_id"""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert postgresql+asyncpg:// to postgresql:// for asyncpg
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        # Connect to database
        print("🔌 Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        # Check if exam_requests table exists
        print("🔍 Checking if exam_requests table exists...")
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'exam_requests'
            );
        """)
        
        if not table_exists:
            print("❌ exam_requests table doesn't exist")
            await conn.close()
            return
        
        # Check current foreign key constraints
        print("🔍 Checking current foreign key constraints...")
        constraints = await conn.fetch("""
            SELECT 
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'exam_requests'
                AND kcu.column_name = 'tiss_guide_id';
        """)
        
        if constraints:
            print(f"🔍 Found {len(constraints)} foreign key constraint(s) on tiss_guide_id:")
            for constraint in constraints:
                print(f"   - {constraint['constraint_name']}: {constraint['table_name']}.{constraint['column_name']} -> {constraint['foreign_table_name']}.{constraint['foreign_column_name']}")
            
            # Drop the foreign key constraints
            for constraint in constraints:
                print(f"🗑️  Dropping constraint: {constraint['constraint_name']}")
                await conn.execute(f"ALTER TABLE exam_requests DROP CONSTRAINT {constraint['constraint_name']};")
            
            print("✅ Foreign key constraints removed successfully")
        else:
            print("ℹ️  No foreign key constraints found on tiss_guide_id")
        
        # Verify the fix
        print("🔍 Verifying the fix...")
        remaining_constraints = await conn.fetch("""
            SELECT 
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'exam_requests'
                AND kcu.column_name = 'tiss_guide_id';
        """)
        
        if not remaining_constraints:
            print("✅ Verification successful - no foreign key constraints on tiss_guide_id remain")
        else:
            print(f"⚠️  Warning: {len(remaining_constraints)} foreign key constraints still exist on tiss_guide_id")
        
        await conn.close()
        print("🎉 Database fix completed successfully!")
        
    except Exception as e:
        print(f"❌ Error fixing database: {str(e)}")
        if 'conn' in locals():
            await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_exam_requests_foreign_key())
