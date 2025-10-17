import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_table_structure():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    conn = await asyncpg.connect(database_url)
    try:
        # Check consultations table structure
        result = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'consultations' 
            ORDER BY ordinal_position
        """)
        
        print('Consultations table structure:')
        for row in result:
            print(f'  {row["column_name"]}: {row["data_type"]}')
            
        # Check if consultations table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'consultations'
            )
        """)
        print(f'\nConsultations table exists: {table_exists}')
            
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_table_structure())
