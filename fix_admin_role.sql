-- Fix admin user role
UPDATE users 
SET role = 'admin' 
WHERE email = 'admin@clinica.com.br';

-- Check the result
SELECT id, email, role, is_active, clinic_id 
FROM users 
WHERE email = 'admin@clinica.com.br';
