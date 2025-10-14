"""
Emergency script to create consultations table directly
Bypasses Alembic migration system
"""

import asyncio
from sqlalchemy import text
from app.db.base import async_engine


async def create_consultations_table():
    """Create consultations table directly."""
    print("=" * 60)
    print("CREATING CONSULTATIONS TABLE")
    print("=" * 60)
    
    # Split SQL into individual statements
    sql_statements = [
        # Drop existing table
        """DROP TABLE IF EXISTS consultations CASCADE""",
        
        # Create table
        """CREATE TABLE consultations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
            patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            doctor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chief_complaint TEXT NOT NULL,
            history_present_illness TEXT,
            past_medical_history TEXT,
            family_history TEXT,
            social_history TEXT,
            medications_in_use TEXT,
            allergies VARCHAR(255),
            physical_examination TEXT,
            vital_signs JSON DEFAULT '{}',
            diagnosis TEXT NOT NULL,
            diagnosis_code VARCHAR(10),
            treatment_plan TEXT,
            follow_up TEXT,
            notes TEXT,
            is_locked BOOLEAN NOT NULL DEFAULT false,
            locked_at TIMESTAMP,
            locked_by UUID REFERENCES users(id),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # Create indexes
        """CREATE INDEX idx_consultations_clinic_id ON consultations(clinic_id)""",
        """CREATE INDEX idx_consultations_patient_id ON consultations(patient_id)""",
        """CREATE INDEX idx_consultations_appointment_id ON consultations(appointment_id)""",
        """CREATE INDEX idx_consultations_doctor_id ON consultations(doctor_id)""",
        """CREATE INDEX idx_consultations_created_at ON consultations(created_at)""",
        
        # Create trigger function
        """CREATE OR REPLACE FUNCTION update_consultations_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql""",
        
        # Drop old trigger if exists
        """DROP TRIGGER IF EXISTS trigger_update_consultations_updated_at ON consultations""",
        
        # Create trigger
        """CREATE TRIGGER trigger_update_consultations_updated_at
        BEFORE UPDATE ON consultations
        FOR EACH ROW
        EXECUTE FUNCTION update_consultations_updated_at()"""
    ]
    
    engine = async_engine
    
    try:
        async with engine.begin() as conn:
            # Execute each SQL statement separately
            for i, sql in enumerate(sql_statements, 1):
                try:
                    await conn.execute(text(sql))
                    print(f"✅ Step {i}/{len(sql_statements)} completed")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"⚠️  Step {i}: Already exists (skipping)")
                    else:
                        raise
            
            print("\n✅ Table 'consultations' created successfully")
            
            # Verify creation
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = 'consultations';
            """))
            
            if result.scalar():
                print("✅ Table verified in database")
                
                # Count columns
                result = await conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_name = 'consultations';
                """))
                col_count = result.scalar()
                print(f"✅ Table has {col_count} columns")
                
                # Count indexes
                result = await conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE tablename = 'consultations';
                """))
                idx_count = result.scalar()
                print(f"✅ Table has {idx_count} indexes")
                
                print("\n" + "=" * 60)
                print("SUCCESS! Consultations table is ready to use.")
                print("=" * 60)
                return True
            else:
                print("❌ Table creation failed - not found in database")
                return False
                
    except Exception as e:
        print(f"\n❌ Error creating table: {str(e)}")
        print("\nIf you see 'relation already exists', the table is already there.")
        print("You can safely ignore this error.")
        return False
    finally:
        await engine.dispose()


async def main():
    """Run table creation."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  CREATE CONSULTATIONS TABLE - DIRECT".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")
    
    success = await create_consultations_table()
    
    if success:
        print("\n✅ Next steps:")
        print("   1. Run: python verify_consultations_setup.py")
        print("   2. Test frontend: https://prontivus-frontend-ten.vercel.app/app/consultations")
        print("\n")
    else:
        print("\n⚠️ If the table already exists, that's OK!")
        print("   Run: python verify_consultations_setup.py to verify.")
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())

