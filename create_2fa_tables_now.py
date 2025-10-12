"""
Emergency script to create 2FA tables directly
Run this if alembic migration fails
"""

import asyncio
from sqlalchemy import text
from app.db.base import async_engine

async def create_tables():
    """Create all 2FA-related tables."""
    engine = async_engine
    
    async with engine.begin() as conn:
        print("🔧 Creating two_fa_secrets table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS two_fa_secrets (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL UNIQUE,
                secret_encrypted VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                backup_codes_encrypted TEXT,
                created_at TIMESTAMP NOT NULL,
                enabled_at TIMESTAMP,
                last_used_at TIMESTAMP,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TIMESTAMP,
                CONSTRAINT fk_two_fa_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """))
        print("✅ two_fa_secrets created")
        
        print("🔧 Creating security_settings table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS security_settings (
                id UUID PRIMARY KEY,
                clinic_id UUID NOT NULL UNIQUE,
                require_2fa_for_roles VARCHAR[] NOT NULL DEFAULT ARRAY['admin', 'doctor', 'superadmin'],
                session_timeout_minutes INTEGER NOT NULL DEFAULT 60,
                max_login_attempts INTEGER NOT NULL DEFAULT 5,
                lockout_duration_minutes INTEGER NOT NULL DEFAULT 15,
                password_min_length INTEGER NOT NULL DEFAULT 8,
                password_require_special BOOLEAN NOT NULL DEFAULT true,
                updated_at TIMESTAMP NOT NULL,
                updated_by UUID,
                CONSTRAINT fk_security_clinic FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE,
                CONSTRAINT fk_security_updated_by FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        print("✅ security_settings created")
        
        print("🔧 Creating login_attempts table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id UUID PRIMARY KEY,
                user_id UUID,
                email VARCHAR NOT NULL,
                ip_address VARCHAR,
                user_agent VARCHAR,
                success BOOLEAN NOT NULL,
                failure_reason VARCHAR,
                attempted_at TIMESTAMP NOT NULL,
                CONSTRAINT fk_login_attempts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """))
        print("✅ login_attempts created")
        
        print("🔧 Adding 2FA columns to users table...")
        try:
            await conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS two_fa_enabled BOOLEAN NOT NULL DEFAULT false
            """))
            await conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS two_fa_verified_at TIMESTAMP
            """))
            print("✅ users table updated")
        except Exception as e:
            print(f"⚠️  users columns might already exist: {e}")
        
        print("🔧 Creating indexes...")
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_two_fa_user ON two_fa_secrets(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_two_fa_status ON two_fa_secrets(status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_login_attempts_user ON login_attempts(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_login_attempts_attempted_at ON login_attempts(attempted_at)"))
        print("✅ indexes created")
        
        print("🔧 Creating default security settings for existing clinics...")
        await conn.execute(text("""
            INSERT INTO security_settings (
                id, clinic_id, require_2fa_for_roles, session_timeout_minutes,
                max_login_attempts, lockout_duration_minutes, password_min_length,
                password_require_special, updated_at
            )
            SELECT 
                gen_random_uuid(),
                id,
                ARRAY['admin', 'doctor', 'superadmin']::VARCHAR[],
                60,
                5,
                15,
                8,
                true,
                NOW()
            FROM clinics
            WHERE NOT EXISTS (
                SELECT 1 FROM security_settings WHERE security_settings.clinic_id = clinics.id
            )
        """))
        print("✅ default security settings created")
    
    print("")
    print("=" * 50)
    print("✅ ALL 2FA TABLES CREATED SUCCESSFULLY!")
    print("=" * 50)
    print("")
    print("Next steps:")
    print("1. Restart your backend server")
    print("2. Login to your admin account")
    print("3. Go to Settings → Security")
    print("4. Enable 2FA")
    print("")

if __name__ == "__main__":
    try:
        asyncio.run(create_tables())
        print("🎉 Deployment complete! Your security system is ready!")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("")
        print("If you see connection errors, make sure:")
        print("1. Your database is running")
        print("2. DATABASE_URL is set in .env")
        print("3. The database connection is working")

