# 📋 Prescrição Digital - Workflow Completo

## ✅ Funcionalidades Implementadas

### 1. **Criação de Prescrição** ✅
**Endpoint:** `POST /api/v1/prescriptions/`

**Payload:**
```json
{
  "patient_id": "uuid",
  "prescription_type": "simple",  // ou "antimicrobial", "C1"
  "medications": [
    {
      "medication_name": "Paracetamol 500mg",
      "dosage": "1 comprimido",
      "frequency": "De 6 em 6 horas",
      "duration": "7 dias"
    }
  ],
  "notes": "Tomar após as refeições",
  "record_id": "uuid" // opcional
}
```

**Resultado:**
- ✅ Prescrição criada no banco
- ✅ Status: `DRAFT`
- ✅ Múltiplos medicamentos suportados

---

### 2. **Geração de PDF com Marca da Clínica** ✅
**Endpoint:** `POST /api/v1/prescriptions/{prescription_id}/generate-pdf`

**Funcionalidades:**
- ✅ PDF gerado com `prescription_pdf.py`
- ✅ Branding da clínica (logo, nome, contato)
- ✅ Informações do paciente
- ✅ Tabela de medicamentos profissional
- ✅ Seção de assinatura do médico

**Arquivos:**
- `backend/app/services/prescription_pdf.py` - Gerador ReportLab
- `backend/app/services/pdf_generator.py` - Gerador WeasyPrint

---

### 3. **Assinatura Digital ICP-Brasil A1** ✅
**Endpoint:** `POST /api/v1/prescriptions/{prescription_id}/sign`

**Payload:**
```json
{
  "certificate_id": "id_do_certificado",
  "pin": "senha_do_certificado",
  "signer_user_id": "uuid"
}
```

**Funcionalidades:**
- ✅ Assinatura PAdES (PDF Advanced Electronic Signature)
- ✅ Certificado ICP-Brasil A1 compatível
- ✅ Hash SHA-256 do documento
- ✅ Timestamp de assinatura
- ✅ Metadados de verificação

**Arquivos:**
- `backend/app/services/digital_signature.py` - Serviço principal
- `backend/app/services/digital_signature_prescription.py` - Especializado para prescrições

**Resultado:**
- ✅ Status: `DRAFT` → `SIGNED`
- ✅ `signed_at`: timestamp
- ✅ `signature_hash`: hash da assinatura
- ✅ `pdf_url`: URL do PDF assinado

---

### 4. **QR Code para Verificação** ✅
**Gerado automaticamente ao assinar**

**Funcionalidades:**
- ✅ QR Code embutido no PDF
- ✅ Código de verificação único
- ✅ URL de verificação pública

**Arquivo:**
- `backend/app/services/qr_generator.py`

**Exemplo de URL:**
```
https://prontivus.com/verify/prescription/{id}?code={verification_code}
```

---

### 5. **Verificação Pública** ✅
**Endpoint:** `GET /api/v1/prescriptions/verify/{prescription_id}`

**Funcionalidades:**
- ✅ Qualquer pessoa pode verificar autenticidade
- ✅ Valida assinatura digital
- ✅ Mostra dados da prescrição (sem informações sensíveis)
- ✅ Confirma validade (não expirada, não revogada)

**Arquivo:**
- `backend/app/api/v1/prescription_verification.py`

---

### 6. **Download de PDF** ✅
**Endpoint:** `GET /api/v1/prescriptions/{prescription_id}/pdf`

**Funcionalidades:**
- ✅ Download do PDF assinado
- ✅ Autenticação requerida
- ✅ Audit log de acesso

---

## 🔄 Workflow Completo

```
1. Frontend → POST /prescriptions
   └─→ Prescrição criada (DRAFT)

2. Frontend → POST /prescriptions/{id}/generate-pdf
   ├─→ PDF gerado com branding
   ├─→ Assinatura digital aplicada
   ├─→ QR Code embutido
   └─→ Status: SIGNED

3. Backend → Upload PDF para S3/MinIO
   └─→ pdf_url: https://storage.../prescription.pdf

4. Frontend → Notifica médico
   └─→ "Prescrição assinada com sucesso!"

5. Paciente pode:
   ├─→ Ver no portal
   ├─→ Receber por email
   ├─→ Receber por WhatsApp
   └─→ Verificar autenticidade via QR Code
```

---

## 📊 Status Atual

| Funcionalidade | Status | Arquivo |
|----------------|--------|---------|
| ✅ Criar Prescrição | Funcionando | `prescriptions_basic.py` |
| ✅ Gerar PDF | Implementado | `prescription_pdf.py` |
| ✅ Assinar ICP-Brasil | Implementado | `digital_signature.py` |
| ✅ QR Code | Implementado | `qr_generator.py` |
| ✅ Verificação Pública | Implementado | `prescription_verification.py` |
| ⚠️ Email/WhatsApp | TODO | Precisa configurar SMTP/API |
| ⚠️ Storage S3/MinIO | TODO | Precisa configurar credenciais |

---

## 🚀 Próximos Passos de Produção

### **Para Ativar Email:**
1. Configure SMTP no `render.yaml`:
   ```yaml
   - key: SMTP_HOST
     value: "smtp.gmail.com"
   - key: SMTP_PORT
     value: "587"
   - key: SMTP_USERNAME
     value: "seu-email@gmail.com"
   - key: SMTP_PASSWORD
     value: "sua-senha-de-app"
   ```

2. Prescrições serão enviadas automaticamente após assinatura

### **Para Ativar WhatsApp:**
1. Integre com Twilio/WhatsApp Business API
2. Configure `WHATSAPP_API_KEY` no ambiente
3. Endpoint já preparado para envio

### **Para Ativar Storage:**
1. Configure MinIO ou AWS S3:
   ```yaml
   - key: S3_ENDPOINT
     value: "https://s3.amazonaws.com"
   - key: S3_ACCESS_KEY
     value: "sua-chave"
   - key: S3_SECRET_KEY
     value: "seu-secret"
   - key: S3_BUCKET
     value: "prontivus-prescriptions"
   ```

2. PDFs assinados serão salvos automaticamente

---

## 🔐 Certificado ICP-Brasil A1

### **Instalação:**
1. Obtenha certificado A1 de Autoridade Certificadora
2. Converta para formato PEM:
   ```bash
   openssl pkcs12 -in certificado.pfx -out cert.pem -nokeys
   openssl pkcs12 -in certificado.pfx -out key.pem -nodes -nocerts
   ```

3. Configure no ambiente:
   ```yaml
   - key: ICP_CERT_PATH
     value: "/path/to/cert.pem"
   - key: ICP_KEY_PATH
     value: "/path/to/key.pem"
   ```

### **Validação:**
- ✅ Certificado válido (não expirado)
- ✅ Cadeia de confiança ICP-Brasil
- ✅ Assinatura PAdES compatível com validadores

---

## 📱 Entrega ao Paciente

### **Opções Disponíveis:**

#### **1. Portal do Paciente** ✅
- Acesso via login
- Histórico de prescrições
- Download de PDF

#### **2. Email** ⚠️ (Configurar SMTP)
Template pronto:
- Assunto: "Nova Prescrição Digital - [Clínica]"
- Anexo: PDF assinado
- Link de verificação
- QR Code inline

#### **3. WhatsApp** ⚠️ (Configurar API)
Template pronto:
- Mensagem: "Olá [Paciente], sua prescrição está pronta!"
- Anexo: PDF
- Link: verificação pública

#### **4. Impressão** ✅
- Gerar PDF → Imprimir
- QR Code visível para verificação física

---

## 🔍 Verificação de Autenticidade

### **URL Pública:**
```
https://prontivus.com/verify/prescription/{id}?code={verification_code}
```

### **Informações Exibidas:**
- ✅ Validade da assinatura digital
- ✅ Dados do médico (CRM)
- ✅ Data de emissão
- ✅ Medicamentos prescritos
- ✅ Status (válida, expirada, revogada)
- ❌ **NÃO** mostra dados sensíveis do paciente

---

## 🎯 Compliance Médico

### **Requisitos Atendidos:**
- ✅ CFM Resolução 1.821/2007 (Prontuário Eletrônico)
- ✅ ICP-Brasil para assinatura digital
- ✅ LGPD - dados criptografados
- ✅ Rastreabilidade completa (audit logs)
- ✅ Verificação de autenticidade
- ✅ Controle de acesso (RBAC)

### **Tipos de Prescrição:**
- ✅ **Simples**: Medicamentos comuns
- ✅ **Antimicrobianos**: Validação especial CFM
- ✅ **C1 (Controlados)**: Validação Portaria 344

---

## 📞 Suporte ao Usuário

Para dúvidas sobre prescrições digitais:
- 📧 suporte@prontivus.com
- 📱 WhatsApp: +55 11 98765-4321
- 📖 Documentação: https://docs.prontivus.com/prescriptions

---

**Sistema de prescrições digitais pronto para uso! Configure SMTP/Storage para ativar entrega automática.**

