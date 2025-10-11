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


@router.post("/fix-prescription-record-id")
async def fix_prescription_record_id(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Make prescriptions.record_id NULLABLE
    
    This corresponds to migration 0018 which failed to apply.
    Call this endpoint ONCE to fix the schema.
    """
    try:
        # Make record_id nullable
        await db.execute(text("ALTER TABLE prescriptions ALTER COLUMN record_id DROP NOT NULL"))
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ Successfully made prescriptions.record_id NULLABLE",
            "next_steps": [
                "1. Test prescription creation at /app/prescriptions",
                "2. If working, this fix is permanent",
                "3. You can delete this endpoint after testing"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to fix prescriptions.record_id",
            "manual_fix": "Execute in PostgreSQL: ALTER TABLE prescriptions ALTER COLUMN record_id DROP NOT NULL"
        }


@router.post("/fix-appointment-status-enum")
async def fix_appointment_status_enum(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Convert appointments.status from ENUM to VARCHAR
    
    The database has 'appointmentstatus' ENUM but SQLAlchemy model uses str.
    This causes operator errors when comparing status values.
    Call this endpoint ONCE to fix the schema.
    """
    try:
        # Step 1: Drop default
        await db.execute(text("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT"))
        await db.commit()
        
        # Step 2: Convert to VARCHAR
        await db.execute(text("""
            ALTER TABLE appointments 
            ALTER COLUMN status TYPE VARCHAR 
            USING status::text
        """))
        await db.commit()
        
        # Step 3: Set NOT NULL
        await db.execute(text("ALTER TABLE appointments ALTER COLUMN status SET NOT NULL"))
        await db.commit()
        
        # Step 4: Set DEFAULT
        await db.execute(text("ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'"))
        await db.commit()
        
        # Step 5: Drop ENUM type
        await db.execute(text("DROP TYPE IF EXISTS appointmentstatus CASCADE"))
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ Successfully converted appointments.status from ENUM to VARCHAR",
            "next_steps": [
                "1. Test appointment creation at /app/appointments",
                "2. If working, this fix is permanent",
                "3. You can delete this endpoint after testing"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to fix appointments.status",
            "manual_fix": "Execute SQL manually to convert ENUM to VARCHAR"
        }


@router.post("/fix-medical-record-appointment-id")
async def fix_medical_record_appointment_id(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Make medical_records.appointment_id NULLABLE
    
    The application allows creating medical records without appointments,
    but the database requires appointment_id to be NOT NULL.
    Call this endpoint ONCE to fix the schema.
    """
    try:
        # Make appointment_id nullable
        await db.execute(text("ALTER TABLE medical_records ALTER COLUMN appointment_id DROP NOT NULL"))
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ Successfully made medical_records.appointment_id NULLABLE",
            "next_steps": [
                "1. Test medical record creation at /app/medical-records",
                "2. If working, this fix is permanent",
                "3. You can delete this endpoint after testing"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to fix medical_records.appointment_id",
            "manual_fix": "Execute in PostgreSQL: ALTER TABLE medical_records ALTER COLUMN appointment_id DROP NOT NULL"
        }


@router.post("/create-ethical-locks-table")
async def create_ethical_locks_table(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Create ethical_locks table if it doesn't exist
    
    The medical record lock feature requires this table.
    This table may be missing if migrations didn't run.
    """
    try:
        # Create ENUM types first
        await db.execute(text("""
            DO $$ BEGIN
                CREATE TYPE locktype AS ENUM (
                    'record_edit', 'record_view', 'record_delete', 
                    'appointment_edit', 'appointment_cancel', 
                    'patient_edit', 'patient_merge', 
                    'prescription_edit', 'file_edit',
                    'record_finalization'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        await db.execute(text("""
            DO $$ BEGIN
                CREATE TYPE lockstatus AS ENUM (
                    'active', 'expired', 'released', 'force_released'
                );
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        await db.commit()
        
        # Create the table
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS ethical_locks (
                id UUID PRIMARY KEY,
                clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
                lock_type locktype NOT NULL,
                resource_id UUID NOT NULL,
                resource_type VARCHAR NOT NULL,
                locked_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                locked_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                lock_expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                status lockstatus NOT NULL DEFAULT 'active',
                heartbeat_at TIMESTAMP WITHOUT TIME ZONE,
                released_at TIMESTAMP WITHOUT TIME ZONE,
                lock_meta JSONB,
                reason VARCHAR,
                force_unlocked_by UUID REFERENCES users(id) ON DELETE SET NULL,
                force_unlocked_at TIMESTAMP WITHOUT TIME ZONE,
                force_unlock_reason VARCHAR,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
        """))
        
        # Create indexes
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ethical_locks_clinic ON ethical_locks(clinic_id);
        """))
        
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ethical_locks_resource ON ethical_locks(resource_id, resource_type);
        """))
        
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ethical_locks_status ON ethical_locks(status);
        """))
        
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ Successfully created ethical_locks table",
            "next_steps": [
                "1. Test locking a medical record",
                "2. If working, this fix is permanent",
                "3. You can delete this endpoint after testing"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to create ethical_locks table",
            "manual_fix": "Check if table already exists or execute SQL manually"
        }

