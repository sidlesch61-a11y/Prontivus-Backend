"""
Execute this script LOCALLY to fix the database ENUM issue.
This connects directly to your Render PostgreSQL database.

Usage:
    python fix_db_now.py
"""

import asyncio
import os
import sys

try:
    import asyncpg
except ImportError:
    print("❌ asyncpg not installed!")
    print("Run: pip install asyncpg")
    sys.exit(1)


async def fix_database():
    """Connect to Render PostgreSQL and fix the ENUM issue."""
    
    # Get DATABASE_URL from environment or use Render's
    db_url = os.getenv(
        "DATABASE_URL",
        # REPLACE THIS with your actual Render PostgreSQL connection string:
        "postgresql://prontivus:YOUR_PASSWORD@YOUR_HOST.oregon-postgres.render.com/prontivus"
    )
    
    if "YOUR_PASSWORD" in db_url or "YOUR_HOST" in db_url:
        print("⚠️  WARNING: You need to set your DATABASE_URL!")
        print()
        print("Get it from:")
        print("1. https://dashboard.render.com/")
        print("2. Go to 'prontivus-db'")
        print("3. Click 'Connect' → 'External Connection'")
        print("4. Copy the connection string")
        print()
        db_url = input("Paste your DATABASE_URL here: ").strip()
    
    print("🔌 Connecting to database...")
    
    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Connected!")
        
        # Step 1: Drop default
        print("\n📝 Step 1: Dropping default...")
        await conn.execute("ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT")
        print("✅ Done")
        
        # Step 2: Convert to VARCHAR
        print("\n📝 Step 2: Converting ENUM → VARCHAR...")
        await conn.execute("""
            ALTER TABLE clinics 
            ALTER COLUMN status TYPE VARCHAR 
            USING CASE 
                WHEN status::text = 'active' THEN 'active'
                WHEN status::text = 'inactive' THEN 'inactive'
                WHEN status::text = 'suspended' THEN 'suspended'
                WHEN status::text = 'trial' THEN 'trial'
                ELSE 'active'
            END
        """)
        print("✅ Done")
        
        # Step 3: Set NOT NULL
        print("\n📝 Step 3: Setting NOT NULL...")
        await conn.execute("ALTER TABLE clinics ALTER COLUMN status SET NOT NULL")
        print("✅ Done")
        
        # Step 4: Set DEFAULT
        print("\n📝 Step 4: Setting DEFAULT 'active'...")
        await conn.execute("ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active'")
        print("✅ Done")
        
        # Step 5: Update NULLs
        print("\n📝 Step 5: Updating NULL values...")
        result = await conn.execute("UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = ''")
        print(f"✅ Done (affected: {result})")
        
        # Step 6: Drop ENUM type
        print("\n📝 Step 6: Dropping ENUM type...")
        await conn.execute("DROP TYPE IF EXISTS clinicstatus CASCADE")
        print("✅ Done")
        
        await conn.close()
        
        print("\n" + "="*50)
        print("🎉 SUCCESS! Database fixed!")
        print("="*50)
        print("\nNow test registration at:")
        print("https://prontivus-frontend-ten.vercel.app/register")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTry executing manually via Render Dashboard:")
        print("https://dashboard.render.com/")
        return False
    
    return True


if __name__ == "__main__":
    print("="*50)
    print("🚨 EMERGENCY DATABASE FIX")
    print("="*50)
    print()
    
    result = asyncio.run(fix_database())
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)

