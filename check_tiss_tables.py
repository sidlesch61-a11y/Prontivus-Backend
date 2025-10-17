import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_tables():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('postgresql+asyncpg://'):
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    conn = await asyncpg.connect(database_url)
    try:
        # Check insurance_providers table structure
        result = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'insurance_providers' ORDER BY ordinal_position")
        
        print('Insurance providers table structure:')
        for row in result:
            print(f'  {row["column_name"]}: {row["data_type"]}')
            
        # Check exam_database table structure
        result = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'exam_database' ORDER BY ordinal_position")
        
        print('\nExam database table structure:')
        for row in result:
            print(f'  {row["column_name"]}: {row["data_type"]}')
            
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tables())
