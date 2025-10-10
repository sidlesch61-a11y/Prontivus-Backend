# PowerShell script to test registration endpoint

$body = @{
    clinic = @{
        name = "Clínica Teste"
        cnpj_cpf = "12345678000100"
        contact_email = "teste@clinica.com.br"
        contact_phone = "11987654321"
    }
    user = @{
        name = "Dr. Teste"
        email = "teste@clinica.com.br"
        password = "SenhaSegura123!"
        role = "admin"
    }
} | ConvertTo-Json -Depth 10

Write-Host "Testing Registration Endpoint..." -ForegroundColor Cyan
Write-Host "URL: https://prontivus-backend-wnw2.onrender.com/api/v1/auth/register" -ForegroundColor Yellow
Write-Host ""
Write-Host "Request Body:" -ForegroundColor Green
Write-Host $body
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "https://prontivus-backend-wnw2.onrender.com/api/v1/auth/register" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "SUCCESS!" -ForegroundColor Green
    Write-Host ($response | ConvertTo-Json -Depth 10)
} catch {
    Write-Host "ERROR!" -ForegroundColor Red
    Write-Host "Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    Write-Host "Status Description: $($_.Exception.Response.StatusDescription)" -ForegroundColor Red
    Write-Host ""
    
    if ($_.ErrorDetails.Message) {
        Write-Host "Error Details:" -ForegroundColor Yellow
        $errorObj = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host ($errorObj | ConvertTo-Json -Depth 10)
    } else {
        Write-Host "Raw Error: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

