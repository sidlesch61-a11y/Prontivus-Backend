import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def insert_sample_data():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    conn = await asyncpg.connect(database_url)
    try:
        # Get clinic_id
        clinic_id = await conn.fetchval('SELECT id FROM clinics LIMIT 1')
        if not clinic_id:
            print('❌ No clinic found')
            return
            
        # Insert sample insurance providers
        await conn.execute('''
            INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
            SELECT gen_random_uuid(), $1, 'Particular', 'PARTICULAR', TRUE
            WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'PARTICULAR')
        ''', clinic_id)
        
        await conn.execute('''
            INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
            SELECT gen_random_uuid(), $1, 'Unimed', 'UNIMED', TRUE
            WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'UNIMED')
        ''', clinic_id)
        
        await conn.execute('''
            INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
            SELECT gen_random_uuid(), $1, 'Bradesco Saúde', 'BRADESCO', TRUE
            WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'BRADESCO')
        ''', clinic_id)
        
        print('✅ Insurance providers inserted')
        
        # Insert sample exams
        exams = [
            ('Hemograma Completo', '40301001', 'Hematologia'),
            ('Glicemia de Jejum', '40301002', 'Bioquímica'),
            ('Colesterol Total', '40301003', 'Bioquímica'),
            ('Triglicerídeos', '40301004', 'Bioquímica'),
            ('Creatinina', '40301005', 'Bioquímica'),
            ('Uréia', '40301006', 'Bioquímica'),
            ('TSH', '40301007', 'Hormônios'),
            ('T4 Livre', '40301008', 'Hormônios'),
            ('T3 Livre', '40301009', 'Hormônios'),
            ('Exame de Urina Completo', '40301010', 'Urologia')
        ]
        
        for name, tuss_code, category in exams:
            await conn.execute('''
                INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, is_active)
                SELECT gen_random_uuid(), $1, $2::VARCHAR(255), $3::VARCHAR(50), $4::VARCHAR(100), TRUE
                WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = $3)
            ''', clinic_id, name, tuss_code, category)
        
        print('✅ Sample exams inserted')
        print('✅ All sample data inserted successfully!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(insert_sample_data())
