"""
EMERGENCY FIX ENDPOINT - Execute database migrations manually
DELETE THIS FILE AFTER THE FIX IS APPLIED
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db_session

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.post("/fix-clinic-status-enum")
async def fix_clinic_status_enum(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Convert clinics.status from ENUM to VARCHAR
    
    This endpoint should be called ONCE to fix the database schema issue.
    After successful execution, this endpoint should be removed.
    """
    try:
        # Step 1: Drop default
        await db.execute(text("""
            ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT
        """))
        await db.commit()
        
        # Step 2: Convert to VARCHAR
        await db.execute(text("""
            ALTER TABLE clinics 
            ALTER COLUMN status TYPE VARCHAR 
            USING CASE 
                WHEN status::text = 'active' THEN 'active'
                WHEN status::text = 'inactive' THEN 'inactive'
                WHEN status::text = 'suspended' THEN 'suspended'
                WHEN status::text = 'trial' THEN 'trial'
                ELSE 'active'
            END
        """))
        await db.commit()
        
        # Step 3: Set NOT NULL
        await db.execute(text("""
            ALTER TABLE clinics ALTER COLUMN status SET NOT NULL
        """))
        await db.commit()
        
        # Step 4: Set DEFAULT
        await db.execute(text("""
            ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active'
        """))
        await db.commit()
        
        # Step 5: Update NULLs
        await db.execute(text("""
            UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = ''
        """))
        await db.commit()
        
        # Step 6: Drop ENUM type
        await db.execute(text("""
            DROP TYPE IF EXISTS clinicstatus CASCADE
        """))
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ Successfully converted status column from ENUM to VARCHAR",
            "next_steps": [
                "1. Test registration at /register",
                "2. If working, delete this endpoint file",
                "3. Deploy without emergency_fix.py"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to convert status column",
            "manual_fix": "You may need to execute SQL manually in PostgreSQL"
        }

