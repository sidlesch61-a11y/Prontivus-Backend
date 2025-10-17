-- Add roles and permissions columns to users table
-- This script adds role-based access control to the users table

-- Add role column
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'medico';

-- Add permissions column (JSONB for flexible permissions)
ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB DEFAULT '{}';

-- Add is_active column for user status
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Add last_login column for tracking
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITHOUT TIME ZONE;

-- Add created_by column for audit trail
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);

-- Add updated_by column for audit trail
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES users(id);

-- Create index for role-based queries
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Update existing users to have appropriate roles
-- This is a basic assignment - in production, you'd want to review each user
UPDATE users SET role = 'administrador' WHERE email LIKE '%admin%' OR email LIKE '%administrator%';
UPDATE users SET role = 'medico' WHERE role IS NULL AND crm IS NOT NULL;
UPDATE users SET role = 'secretaria' WHERE role IS NULL AND crm IS NULL;

-- Add some sample permissions for different roles
UPDATE users SET permissions = '{
  "can_view_patients": true,
  "can_edit_patients": true,
  "can_view_appointments": true,
  "can_edit_appointments": true,
  "can_view_consultations": true,
  "can_edit_consultations": true,
  "can_view_reports": true,
  "can_manage_users": false,
  "can_manage_settings": false
}'::jsonb WHERE role = 'medico';

UPDATE users SET permissions = '{
  "can_view_patients": true,
  "can_edit_patients": true,
  "can_view_appointments": true,
  "can_edit_appointments": true,
  "can_view_consultations": false,
  "can_edit_consultations": false,
  "can_view_reports": true,
  "can_manage_users": false,
  "can_manage_settings": false
}'::jsonb WHERE role = 'secretaria';

UPDATE users SET permissions = '{
  "can_view_patients": true,
  "can_edit_patients": true,
  "can_view_appointments": true,
  "can_edit_appointments": true,
  "can_view_consultations": true,
  "can_edit_consultations": true,
  "can_view_reports": true,
  "can_manage_users": true,
  "can_manage_settings": true
}'::jsonb WHERE role = 'administrador';

-- Add comment to document the changes
COMMENT ON COLUMN users.role IS 'User role: administrador, medico, secretaria, financeiro';
COMMENT ON COLUMN users.permissions IS 'JSON object containing user permissions';
COMMENT ON COLUMN users.is_active IS 'Whether the user account is active';
COMMENT ON COLUMN users.last_login IS 'Timestamp of last user login';
COMMENT ON COLUMN users.created_by IS 'User who created this user account';
COMMENT ON COLUMN users.updated_by IS 'User who last updated this user account';
