# 🚨 INSTRUÇÕES DE FIX URGENTE

## Problema
O ENUM `clinicstatus` no PostgreSQL não tem os valores corretos, causando erro de registro.

## Solução Imediata (5 minutos)

### Opção A: Via Render Dashboard (RECOMENDADO)

1. **Acesse o Render Dashboard**: https://dashboard.render.com/
2. **Navegue até o Database**: `prontivus-db`
3. **Clique em "Connect"** → Escolha "External Connection"
4. **Copie a Connection String** (algo como `postgresql://user:pass@host/db`)
5. **Abra um cliente PostgreSQL** (DBeaver, pgAdmin, ou psql no terminal):
   ```bash
   psql "postgresql://user:pass@host/db"
   ```
6. **Execute o conteúdo de `FIX_ENUM_NOW.sql`**:
   ```sql
   -- Copie e cole todo o conteúdo do arquivo FIX_ENUM_NOW.sql
   ```

### Opção B: Via Shell do Render (Alternativa)

1. No Render Dashboard, vá para o **Backend Service** (`prontivus-backend`)
2. Clique em **"Shell"**
3. Execute:
   ```bash
   python -c "
   import asyncio
   from app.db.session import engine
   from sqlalchemy import text
   
   async def fix():
       async with engine.begin() as conn:
           await conn.execute(text(\"ALTER TABLE clinics ALTER COLUMN status TYPE VARCHAR USING status::text\"))
           await conn.execute(text(\"DROP TYPE IF EXISTS clinicstatus CASCADE\"))
           print('✅ Fixed!')
   
   asyncio.run(fix())
   "
   ```

### Opção C: Forçar Migration 0015 (Via Deploy)

O arquivo `0015_fix_clinic_status_type.py` já existe, mas não rodou. Para forçá-lo:

1. No Render Dashboard, vá para o **Backend Service**
2. Clique em **"Manual Deploy"** → **"Clear build cache & deploy"**
3. Aguarde 5 minutos e verifique os logs para:
   ```
   Running upgrade 0014 -> 0015, Fix clinic status column
   ```

## Verificação

Após qualquer método, teste o registro em:
https://prontivus-frontend-ten.vercel.app/register

Se funcionar, você verá:
✅ "Cadastro realizado com sucesso!"

## Causa Raiz

O banco tinha um ENUM `clinicstatus` que não incluía o valor "active", criado por alguma migration antiga ou criação manual da tabela.

