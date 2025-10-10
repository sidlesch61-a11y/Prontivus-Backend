-- ========================================
-- EMERGENCY FIX: Convert clinicstatus ENUM to VARCHAR
-- Execute this DIRECTLY in PostgreSQL (Render Dashboard > Connect)
-- ========================================

BEGIN;

-- Step 1: Check current ENUM values
SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'clinicstatus');

-- Step 2: Drop the constraint if it exists
ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT;

-- Step 3: Convert column from ENUM to VARCHAR
ALTER TABLE clinics ALTER COLUMN status TYPE VARCHAR USING status::text;

-- Step 4: Add DEFAULT back
ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active';

-- Step 5: Update any NULL values
UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = '';

-- Step 6: Drop the ENUM type
DROP TYPE IF EXISTS clinicstatus CASCADE;

-- Step 7: Verify
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'clinics' AND column_name = 'status';

COMMIT;

-- ========================================
-- After running this, the registration should work!
-- ========================================

