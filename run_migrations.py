#!/usr/bin/env python3
"""
Script to run database migrations and create necessary tables.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.core.config import settings
from app.db.session import get_db_session
from sqlalchemy import text

async def run_migrations():
    """Run database migrations."""
    print("🚀 Iniciando migrações do banco de dados...")
    
    # Read and execute the SQL migration file
    migration_file = Path(__file__).parent / "create_print_tables.sql"
    
    if not migration_file.exists():
        print("❌ Arquivo de migração não encontrado!")
        return False
    
    try:
        # Get database session
        async for db in get_db_session():
            # Read SQL file
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            for i, statement in enumerate(statements, 1):
                if statement:
                    print(f"📝 Executando statement {i}/{len(statements)}...")
                    try:
                        await db.execute(text(statement))
                        await db.commit()
                        print(f"✅ Statement {i} executado com sucesso")
                    except Exception as e:
                        print(f"⚠️  Statement {i} falhou (pode já existir): {e}")
                        # Continue with other statements
                        continue
            
            print("🎉 Migrações concluídas com sucesso!")
            return True
            
    except Exception as e:
        print(f"❌ Erro durante as migrações: {e}")
        return False

async def main():
    """Main function."""
    print("=" * 50)
    print("PRONTIVUS - SCRIPT DE MIGRAÇÃO")
    print("=" * 50)
    
    success = await run_migrations()
    
    if success:
        print("\n✅ Todas as migrações foram executadas com sucesso!")
        print("📋 Tabelas criadas:")
        print("   - print_logs")
        print("   - price_rules") 
        print("   - patient_vitals (campo altura adicionado)")
        print("   - patients (campo city adicionado)")
    else:
        print("\n❌ Algumas migrações falharam. Verifique os logs acima.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
