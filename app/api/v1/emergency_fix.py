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


@router.post("/convert-all-enums-to-varchar")
async def convert_all_enums_to_varchar(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Convert ALL ENUM columns to VARCHAR
    
    Fixes all ENUM type mismatches between database and SQLAlchemy models.
    This is a comprehensive fix for: clinicstatus, appointmentstatus, userrole.
    """
    try:
        results = []
        
        # 1. Fix clinics.status (clinicstatus → VARCHAR)
        try:
            await db.execute(text("ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT"))
            await db.execute(text("ALTER TABLE clinics ALTER COLUMN status TYPE VARCHAR USING status::text"))
            await db.execute(text("ALTER TABLE clinics ALTER COLUMN status SET NOT NULL"))
            await db.execute(text("ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active'"))
            await db.commit()
            results.append("✅ clinics.status → VARCHAR")
        except Exception as e:
            results.append(f"⚠️ clinics.status: {str(e)[:50]}")
        
        # 2. Fix appointments.status (appointmentstatus → VARCHAR)
        try:
            await db.execute(text("ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT"))
            await db.execute(text("ALTER TABLE appointments ALTER COLUMN status TYPE VARCHAR USING status::text"))
            await db.execute(text("ALTER TABLE appointments ALTER COLUMN status SET NOT NULL"))
            await db.execute(text("ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'"))
            await db.commit()
            results.append("✅ appointments.status → VARCHAR")
        except Exception as e:
            results.append(f"⚠️ appointments.status: {str(e)[:50]}")
        
        # 3. Fix users.role (userrole → VARCHAR)
        try:
            await db.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR USING role::text"))
            await db.execute(text("ALTER TABLE users ALTER COLUMN role SET NOT NULL"))
            await db.commit()
            results.append("✅ users.role → VARCHAR")
        except Exception as e:
            results.append(f"⚠️ users.role: {str(e)[:50]}")
        
        # 4. Drop ENUM types
        try:
            await db.execute(text("DROP TYPE IF EXISTS clinicstatus CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS appointmentstatus CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
            await db.commit()
            results.append("✅ Dropped all ENUM types")
        except Exception as e:
            results.append(f"⚠️ Drop ENUMs: {str(e)[:50]}")
        
        return {
            "success": True,
            "message": "✅ Converted all ENUMs to VARCHAR",
            "details": results,
            "next_steps": [
                "1. Remove all cast() calls from backend code (optional optimization)",
                "2. Test all features without ENUM errors",
                "3. This fix is permanent"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to convert ENUMs",
            "manual_fix": "Execute SQL manually or run individual ENUM fixes"
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


@router.post("/fix-appointment-source-column")
async def fix_appointment_source_column(db: AsyncSession = Depends(get_db_session)):
    """
    EMERGENCY: Fix appointments.source column NOT NULL constraint
    
    Makes the column nullable OR adds a default value of 'manual'.
    """
    try:
        # Option 1: Make it nullable
        await db.execute(text("""
            ALTER TABLE appointments 
            ALTER COLUMN source DROP NOT NULL
        """))
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ appointments.source is now nullable",
            "next_steps": [
                "1. Try creating an appointment again",
                "2. If working, this fix is permanent",
                "3. Consider adding 'source' field to the model with a default value"
            ]
        }
    
    except Exception as e:
        await db.rollback()
        
        # If column doesn't exist, try to add it
        try:
            await db.execute(text("""
                ALTER TABLE appointments 
                ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'manual'
            """))
            await db.commit()
            
            return {
                "success": True,
                "message": "✅ Added source column with default 'manual'",
                "next_steps": [
                    "1. Try creating an appointment again",
                    "2. If working, this fix is permanent"
                ]
            }
        except Exception as e2:
            await db.rollback()
            return {
                "success": False,
                "error": f"First attempt: {str(e)}, Second attempt: {str(e2)}",
                "message": "❌ Failed to fix appointments.source",
                "manual_fix": "ALTER TABLE appointments ALTER COLUMN source DROP NOT NULL;"
            }


@router.post("/delete-all-data-except-users")
async def delete_all_data_except_users(db: AsyncSession = Depends(get_db_session)):
    """
    ⚠️ DANGEROUS: Delete ALL data from database EXCEPT users and clinics
    
    This will DELETE:
    - All appointments
    - All medical records
    - All prescriptions
    - All patients
    - All files
    - All invoices
    - All audit logs
    - All sync events
    - All waiting queue entries
    - All ethical locks
    
    This will PRESERVE:
    - All users
    - All clinics
    
    USE WITH EXTREME CAUTION - THIS CANNOT BE UNDONE!
    """
    try:
        deleted_counts = {}
        
        # Delete in correct order to respect foreign key constraints
        tables_to_delete = [
            "files",
            "ethical_locks",
            "prescriptions",
            "medical_records",
            "appointments",
            "waiting_queue",
            "patients",
            "invoices",
            "sync_events",
            "audit_logs",
        ]
        
        for table in tables_to_delete:
            try:
                result = await db.execute(text(f"DELETE FROM {table}"))
                deleted_counts[table] = result.rowcount
                await db.commit()
            except Exception as e:
                # If table doesn't exist or has issues, continue
                deleted_counts[table] = f"Error: {str(e)[:50]}"
                await db.rollback()
        
        return {
            "success": True,
            "message": "✅ Database cleaned successfully (users and clinics preserved)",
            "deleted_counts": deleted_counts,
            "preserved": [
                "users",
                "clinics"
            ],
            "warning": "⚠️ This action cannot be undone!"
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to clean database"
        }


@router.post("/create-appointment-requests-table")
async def create_appointment_requests_table(db: AsyncSession = Depends(get_db_session)):
    """
    🆕 CREATE appointment_requests table (migration 0019)
    
    Creates the appointment_requests table for patient online booking system.
    
    Run this if migration fails or to create table manually.
    """
    try:
        from sqlalchemy import text
        
        # Create appointment_requests table
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS appointment_requests (
                id UUID PRIMARY KEY,
                clinic_id UUID NOT NULL,
                patient_id UUID NOT NULL,
                doctor_id UUID NULL,
                preferred_date VARCHAR NOT NULL,
                preferred_time VARCHAR NULL,
                reason TEXT NOT NULL,
                notes TEXT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                requested_at TIMESTAMP NOT NULL,
                reviewed_at TIMESTAMP NULL,
                reviewed_by UUID NULL,
                rejection_reason TEXT NULL,
                approved_appointment_id UUID NULL,
                approved_start_time TIMESTAMP NULL,
                approved_end_time TIMESTAMP NULL,
                CONSTRAINT fk_appointment_requests_clinic 
                    FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
                CONSTRAINT fk_appointment_requests_patient 
                    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
                CONSTRAINT fk_appointment_requests_doctor 
                    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL,
                CONSTRAINT fk_appointment_requests_reviewed_by 
                    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
                CONSTRAINT fk_appointment_requests_appointment 
                    FOREIGN KEY (approved_appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
            )
        """))
        await db.commit()
        
        # Create indexes
        await db.execute(text("CREATE INDEX IF NOT EXISTS idx_appointment_requests_clinic ON appointment_requests(clinic_id)"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS idx_appointment_requests_patient ON appointment_requests(patient_id)"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS idx_appointment_requests_status ON appointment_requests(status)"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS idx_appointment_requests_requested_at ON appointment_requests(requested_at)"))
        await db.commit()
        
        return {
            "success": True,
            "message": "✅ appointment_requests table created successfully",
            "details": {
                "table": "appointment_requests",
                "indexes": 4,
                "foreign_keys": 5
            }
        }
        
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to create appointment_requests table"
        }


@router.post("/delete-everything-except-admin")
async def delete_everything_except_admin(db: AsyncSession = Depends(get_db_session)):
    """
    🔥 NUCLEAR OPTION: Delete EVERYTHING except admin@clinica.com.br and their clinic
    
    This will DELETE:
    - ALL other users
    - ALL other clinics
    - ALL appointments
    - ALL medical records
    - ALL prescriptions
    - ALL patients
    - ALL files
    - ALL invoices
    - ALL audit logs
    - ALL sync events
    - ALL waiting queue entries
    - ALL ethical locks
    
    This will PRESERVE ONLY:
    - User: admin@clinica.com.br
    - Their associated clinic
    
    ⚠️⚠️⚠️ EXTREME DANGER - THIS CANNOT BE UNDONE! ⚠️⚠️⚠️
    """
    try:
        # Find the admin user
        from sqlalchemy import select
        result = await db.execute(
            text("SELECT id, clinic_id FROM users WHERE email = 'admin@clinica.com.br'")
        )
        admin_user = result.fetchone()
        
        if not admin_user:
            return {
                "success": False,
                "error": "Admin user not found",
                "message": "❌ Could not find admin@clinica.com.br"
            }
        
        admin_user_id = str(admin_user[0])
        admin_clinic_id = str(admin_user[1])
        
        deleted_counts = {}
        
        # Step 1: Delete all data from child tables (no conditions needed)
        child_tables = [
            "files",
            "ethical_locks",
            "prescriptions",
            "medical_records",
            "appointments",
            "waiting_queue",
            "patients",
            "invoices",
            "sync_events",
            "audit_logs",
        ]
        
        for table in child_tables:
            try:
                result = await db.execute(text(f"DELETE FROM {table}"))
                deleted_counts[table] = result.rowcount
                await db.commit()
            except Exception as e:
                deleted_counts[table] = f"Error: {str(e)[:50]}"
                await db.rollback()
        
        # Step 2: Delete all users EXCEPT admin@clinica.com.br
        try:
            result = await db.execute(
                text(f"DELETE FROM users WHERE email != 'admin@clinica.com.br'")
            )
            deleted_counts["users (other)"] = result.rowcount
            await db.commit()
        except Exception as e:
            deleted_counts["users (other)"] = f"Error: {str(e)[:50]}"
            await db.rollback()
        
        # Step 3: Delete all clinics EXCEPT the admin's clinic
        try:
            result = await db.execute(
                text(f"DELETE FROM clinics WHERE id != :clinic_id"),
                {"clinic_id": admin_clinic_id}
            )
            deleted_counts["clinics (other)"] = result.rowcount
            await db.commit()
        except Exception as e:
            deleted_counts["clinics (other)"] = f"Error: {str(e)[:50]}"
            await db.rollback()
        
        return {
            "success": True,
            "message": "🔥 NUCLEAR CLEANUP COMPLETE - Only admin@clinica.com.br remains",
            "deleted_counts": deleted_counts,
            "preserved": {
                "user": "admin@clinica.com.br",
                "user_id": admin_user_id,
                "clinic_id": admin_clinic_id
            },
            "warning": "⚠️⚠️⚠️ ALL OTHER DATA HAS BEEN PERMANENTLY DELETED! ⚠️⚠️⚠️"
        }
    
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "❌ Failed to complete nuclear cleanup"
        }

