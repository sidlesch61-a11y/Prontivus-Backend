import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def update_tables():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    conn = await asyncpg.connect(database_url)
    try:
        # Drop and recreate insurance_providers
        await conn.execute('DROP TABLE IF EXISTS insurance_providers')
        await conn.execute('''
            CREATE TABLE insurance_providers (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                clinic_id UUID NOT NULL,
                name VARCHAR(255) NOT NULL,
                code VARCHAR(50) NOT NULL,
                cnpj VARCHAR(18),
                contact_email VARCHAR(255),
                contact_phone VARCHAR(20),
                address TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            )
        ''')
        print('✅ insurance_providers recreated with clinic_id')
        
        # Add missing columns to tiss_providers
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS cnpj VARCHAR(18)')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS endpoint_url TEXT')
        await conn.execute("ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS environment VARCHAR(20) DEFAULT 'production'")
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS username VARCHAR(255)')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS password_encrypted TEXT')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS certificate_path TEXT')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS timeout_seconds INTEGER DEFAULT 30')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS retry_delay_seconds INTEGER DEFAULT 5')
        await conn.execute("ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active'")
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS last_test_result TEXT')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS last_tested_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS last_successful_request TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS config_meta JSONB')
        await conn.execute('ALTER TABLE tiss_providers ADD COLUMN IF NOT EXISTS notes TEXT')
        print('✅ tiss_providers columns added')
        
        # Add missing columns to tiss_jobs
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS invoice_id UUID')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS procedure_code VARCHAR(50)')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS payload JSONB')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS response_data JSONB')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS max_attempts INTEGER DEFAULT 3')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS last_error TEXT')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS ethical_lock_type VARCHAR(100)')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS ethical_lock_reason TEXT')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS manual_review_required BOOLEAN DEFAULT FALSE')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS job_meta JSONB')
        await conn.execute('ALTER TABLE tiss_jobs ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 0')
        print('✅ tiss_jobs columns added')
        
        # Add missing columns to tiss_guides
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS provider_id UUID')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS procedure_code VARCHAR(50)')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS procedure_name VARCHAR(255)')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS unit_value DECIMAL(10,2)')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS total_value DECIMAL(10,2)')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS authorization_number VARCHAR(100)')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS xml_content TEXT')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS pdf_path TEXT')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMP WITHOUT TIME ZONE')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS rejection_reason TEXT')
        await conn.execute('ALTER TABLE tiss_guides ADD COLUMN IF NOT EXISTS notes TEXT')
        print('✅ tiss_guides columns added')
        
        # Add missing columns to exam_database
        await conn.execute('ALTER TABLE exam_database ADD COLUMN IF NOT EXISTS description TEXT')
        await conn.execute('ALTER TABLE exam_database ADD COLUMN IF NOT EXISTS preparation_instructions TEXT')
        await conn.execute('ALTER TABLE exam_database ADD COLUMN IF NOT EXISTS fasting_required BOOLEAN DEFAULT FALSE')
        await conn.execute('ALTER TABLE exam_database ADD COLUMN IF NOT EXISTS fasting_hours INTEGER')
        print('✅ exam_database columns added')
        
        print('✅ All tables updated successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(update_tables())
