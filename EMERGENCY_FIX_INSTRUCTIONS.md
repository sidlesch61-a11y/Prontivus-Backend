# 🚨 EMERGENCY FIX - USE THIS NOW!

## Problema
As migrations Alembic NÃO estão rodando no Render, então o banco ainda tem ENUM `clinicstatus` e o registro falha.

## Solução Imediata (2 minutos)

Criamos um **endpoint de API** que executa o SQL manualmente!

### Passo a Passo:

#### **1. Aguarde o Deploy Completar (~3 minutos)**
O commit `7afd863` está deployando agora. Aguarde até ver:
```
==> Your service is live 🎉
```

#### **2. Execute o Endpoint de Fix**
Abra seu navegador ou Postman e faça um **POST** para:

```
https://prontivus-backend-wnw2.onrender.com/api/v1/emergency/fix-clinic-status-enum
```

**Via cURL:**
```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/emergency/fix-clinic-status-enum
```

**Via Navegador:**
Abra esta URL em uma nova aba:
```
https://prontivus-backend-wnw2.onrender.com/docs
```
1. Procure por "Emergency" → `/emergency/fix-clinic-status-enum`
2. Clique em "Try it out"
3. Clique em "Execute"

#### **3. Resposta Esperada:**
```json
{
  "success": true,
  "message": "✅ Successfully converted status column from ENUM to VARCHAR",
  "next_steps": [
    "1. Test registration at /register",
    "2. If working, delete this endpoint file",
    "3. Deploy without emergency_fix.py"
  ]
}
```

#### **4. Teste o Registro!**
Vá para: https://prontivus-frontend-ten.vercel.app/register

Deve funcionar perfeitamente agora!

---

## Opção Alternativa: SQL Manual

Se o endpoint também falhar, execute este SQL diretamente no PostgreSQL:

### Via Render Dashboard:
1. https://dashboard.render.com/
2. `prontivus-db` → Connect → External Connection
3. Copie a connection string
4. Use `psql` ou DBeaver para conectar
5. Execute:

```sql
ALTER TABLE clinics ALTER COLUMN status DROP DEFAULT;
ALTER TABLE clinics ALTER COLUMN status TYPE VARCHAR USING status::text;
ALTER TABLE clinics ALTER COLUMN status SET DEFAULT 'active';
UPDATE clinics SET status = 'active' WHERE status IS NULL OR status = '';
DROP TYPE IF EXISTS clinicstatus CASCADE;
```

---

## Por Que Isso É Necessário?

As migrations Alembic não estão rodando automaticamente no Render. Possíveis causas:
1. O comando no `render.yaml` não está funcionando
2. O Alembic não encontra o `alembic.ini`
3. As migrations estão em cache

Este endpoint **força a execução manual** do SQL necessário.

---

## Após o Fix Funcionar

1. ✅ Confirme que o registro funciona
2. 🗑️ Delete o arquivo `app/api/v1/emergency_fix.py`
3. 🗑️ Remova a linha do `app/main.py`: 
   ```python
   app.include_router(emergency_fix.router, ...)
   ```
4. 📤 Commit e push novamente

---

## Timing

- **Agora**: Commit `7afd863` deployando
- **+3 min**: Endpoint `/emergency/fix-clinic-status-enum` disponível
- **+3.5 min**: Execute o endpoint (POST)
- **+4 min**: Teste o registro → DEVE FUNCIONAR! ✅

