-- Add price column to appointments table
-- This fixes the CSV export error for appointments

-- Add price column to main appointments table
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS price NUMERIC(10,2);

-- Add price column to all existing partitions
ALTER TABLE appointments_2024 ADD COLUMN IF NOT EXISTS price NUMERIC(10,2);
ALTER TABLE appointments_2025 ADD COLUMN IF NOT EXISTS price NUMERIC(10,2);
ALTER TABLE appointments_2026 ADD COLUMN IF NOT EXISTS price NUMERIC(10,2);

-- Add index for price column for better query performance
CREATE INDEX IF NOT EXISTS idx_appointments_price ON appointments(price);

-- Update existing appointments with default price based on consultation type
-- This is a placeholder - in production, you might want to calculate based on insurance or other factors
UPDATE appointments SET price = 150.00 WHERE price IS NULL;

-- Add comment to document the column
COMMENT ON COLUMN appointments.price IS 'Consultation price in local currency';
