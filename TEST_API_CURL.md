# 🧪 Prontivus Backend API - cURL Testing Guide

## 🌐 Base URLs

**Production**: https://prontivus-backend-wnw2.onrender.com  
**Local**: http://localhost:8000

---

## 1️⃣ Health Check (No Auth Required)

### Test if backend is running
```bash
curl https://prontivus-backend-wnw2.onrender.com/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

---

### Test root endpoint
```bash
curl https://prontivus-backend-wnw2.onrender.com/
```

**Expected Response:**
```json
{
  "message": "Welcome to Prontivus API",
  "version": "1.0.0",
  "environment": "production"
}
```

---

## 2️⃣ Test CORS Headers

### Check CORS preflight (OPTIONS request)
```bash
curl -X OPTIONS https://prontivus-backend-wnw2.onrender.com/api/v1/auth/login \
  -H "Origin: https://prontivus-frontend-ten.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v 2>&1 | grep -i "access-control"
```

**Expected Headers:**
```
Access-Control-Allow-Origin: https://prontivus-frontend-ten.vercel.app
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
```

---

## 3️⃣ Authentication Endpoints

### Register New Clinic + Admin User
```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "clinic": {
      "name": "Test Clinic",
      "cnpj_cpf": "12345678901234",
      "contact_email": "clinic@example.com",
      "contact_phone": "+5511999999999"
    },
    "user": {
      "name": "Dr. Test",
      "email": "doctor@example.com",
      "password": "SecurePassword123!",
      "role": "ADMIN"
    }
  }'
```

**Expected Response (201 Created):**
```json
{
  "clinic_id": "uuid-here",
  "user_id": "uuid-here",
  "message": "Clinic and admin user created successfully"
}
```

---

### Login
```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@example.com",
    "password": "SecurePassword123!"
  }'
```

**Expected Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Expected Response (401 if wrong credentials):**
```json
{
  "detail": "Invalid credentials"
}
```

**Expected Response (500 if error):**
```json
{
  "detail": "Internal server error"
}
```

---

### Refresh Token
```bash
# Replace YOUR_REFRESH_TOKEN with actual refresh token
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

---

## 4️⃣ Protected Endpoints (Require Authentication)

### Get Current User Info
```bash
# Replace YOUR_ACCESS_TOKEN with actual token from login
curl https://prontivus-backend-wnw2.onrender.com/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Expected Response:**
```json
{
  "id": "uuid",
  "email": "doctor@example.com",
  "name": "Dr. Test",
  "role": "ADMIN",
  "clinic_id": "uuid",
  "is_active": true
}
```

---

### List Patients
```bash
curl "https://prontivus-backend-wnw2.onrender.com/api/v1/patients?page=1&size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### Get Dashboard Stats
```bash
curl https://prontivus-backend-wnw2.onrender.com/api/v1/dashboard/stats \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 5️⃣ Test with PowerShell (Windows)

### Health Check
```powershell
Invoke-WebRequest -Uri "https://prontivus-backend-wnw2.onrender.com/health" | Select-Object -ExpandProperty Content
```

---

### Login
```powershell
$body = @{
    email = "doctor@example.com"
    password = "SecurePassword123!"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "https://prontivus-backend-wnw2.onrender.com/api/v1/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$response.Content
```

---

### Save Token and Use It
```powershell
# Parse response and save token
$result = $response.Content | ConvertFrom-Json
$token = $result.access_token

# Use token to get user info
Invoke-WebRequest -Uri "https://prontivus-backend-wnw2.onrender.com/api/v1/users/me" `
    -Headers @{Authorization = "Bearer $token"} | 
    Select-Object -ExpandProperty Content
```

---

## 6️⃣ Debug 500 Error

### Detailed Error Response
```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}' \
  -v
```

**Look for:**
- Response status code
- Response body (might contain error details)
- Response headers (CORS headers should be present)

---

### Test with Invalid Data
```bash
# Missing password
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com"}'
```

**Expected**: 422 Validation Error

---

## 7️⃣ WebSocket Test

### Test WebSocket Connection
```bash
# Note: WebSocket requires a token parameter
wscat -c "wss://prontivus-backend-wnw2.onrender.com/ws/notifications?token=YOUR_ACCESS_TOKEN"
```

---

## 8️⃣ Public Endpoints (No Auth)

### Verify Digital Prescription
```bash
curl https://prontivus-backend-wnw2.onrender.com/api/v1/prescriptions/verify/VERIFICATION_CODE
```

---

### Password Reset Request
```bash
curl -X POST https://prontivus-backend-wnw2.onrender.com/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@example.com"
  }'
```

---

## 9️⃣ Quick Test Script (PowerShell)

Save this as `test-api.ps1`:

```powershell
# Prontivus API Quick Test Script

$baseUrl = "https://prontivus-backend-wnw2.onrender.com"

Write-Host "Testing Prontivus Backend API..." -ForegroundColor Green
Write-Host ""

# Test 1: Health Check
Write-Host "[1] Testing health endpoint..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "$baseUrl/health" | Select-Object -ExpandProperty Content
    Write-Host "  [OK] $health" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

Write-Host ""

# Test 2: Login
Write-Host "[2] Testing login endpoint..." -ForegroundColor Yellow
$loginBody = @{
    email = "admin@clinica.com.br"
    password = "admin123"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-WebRequest -Uri "$baseUrl/api/v1/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body $loginBody
    
    $result = $loginResponse.Content | ConvertFrom-Json
    Write-Host "  [OK] Login successful!" -ForegroundColor Green
    Write-Host "  Token: $($result.access_token.Substring(0, 50))..." -ForegroundColor Cyan
    
    $global:token = $result.access_token
    
} catch {
    Write-Host "  [FAIL] Status: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
}

Write-Host ""

# Test 3: Get User Info (if login succeeded)
if ($global:token) {
    Write-Host "[3] Testing authenticated endpoint..." -ForegroundColor Yellow
    try {
        $userInfo = Invoke-WebRequest -Uri "$baseUrl/api/v1/users/me" `
            -Headers @{Authorization = "Bearer $global:token"} |
            Select-Object -ExpandProperty Content
        
        Write-Host "  [OK] $userInfo" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Test complete!" -ForegroundColor Green
```

**Run it:**
```powershell
.\test-api.ps1
```

---

## 🔍 **Debugging the Current 500 Error**

### **Quick PowerShell Test:**
```powershell
try {
    $response = Invoke-WebRequest -Uri "https://prontivus-backend-wnw2.onrender.com/api/v1/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"email":"admin@clinica.com.br","password":"admin123"}'
    
    Write-Host "Success: $($response.Content)"
    
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $errorBody = $_.ErrorDetails.Message
    
    Write-Host "Status Code: $statusCode"
    Write-Host "Error Body: $errorBody"
}
```

This will show you the **exact error message** from the backend!

---

## 📋 **Summary:**

✅ **Database works locally**  
✅ **15 users exist**  
✅ **26 tables created**  
✅ **Both async and sync connections work**  

❌ **500 error on Render** - Need to check Render logs to see why

**Next: Check Render logs or run the PowerShell test above to see the exact error!** 🔍
