# Test Registration Endpoint

## Test Case 1: New Registration

```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/register \
-H "Content-Type: application/json" \
-d '{
  "clinic": {
    "name": "Clínica Teste",
    "cnpj_cpf": "12345678000100",
    "contact_email": "contato@clinicateste.com.br",
    "contact_phone": "11987654321"
  },
  "user": {
    "name": "Dr. João Silva",
    "email": "joao@clinicateste.com.br",
    "password": "SenhaSegura123!",
    "role": "admin"
  }
}'
```

## Test Case 2: Duplicate Email

```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/register \
-H "Content-Type: application/json" \
-d '{
  "clinic": {
    "name": "Clínica Teste 2",
    "cnpj_cpf": "98765432000100",
    "contact_email": "contato2@clinicateste.com.br",
    "contact_phone": "11987654321"
  },
  "user": {
    "name": "Dr. Maria Santos",
    "email": "joao@clinicateste.com.br",
    "password": "SenhaSegura123!",
    "role": "admin"
  }
}'
```

Expected: `{"detail": "E-mail já cadastrado no sistema."}`

## Test Case 3: Duplicate CNPJ

```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/register \
-H "Content-Type: application/json" \
-d '{
  "clinic": {
    "name": "Clínica Teste 3",
    "cnpj_cpf": "12345678000100",
    "contact_email": "contato3@clinicateste.com.br",
    "contact_phone": "11987654321"
  },
  "user": {
    "name": "Dr. Pedro Costa",
    "email": "pedro@clinicateste.com.br",
    "password": "SenhaSegura123!",
    "role": "admin"
  }
}'
```

Expected: `{"detail": "CNPJ/CPF já cadastrado no sistema."}`

## Expected Success Response

```json
{
  "status": "success",
  "clinic_id": "uuid-here",
  "user_id": "uuid-here",
  "message": "Clínica e usuário administrador cadastrados com sucesso."
}
```

## Check Backend Logs

After testing, check logs at:
https://dashboard.render.com/web/prontivus-backend

Look for:
```
========== REGISTRATION ATTEMPT ==========
Email: ...
Clinic Name: ...
CNPJ: ...
Role: ...
```

If error occurs:
```
========== CLINIC CREATION ERROR ==========
Error type: ...
Error message: ...
Error details: ...
Clinic data: ...
```

