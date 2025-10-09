# Prontivus Backend Startup Script
Write-Host "Starting Prontivus Backend Server..." -ForegroundColor Green
Write-Host ""

# Set environment variables
$env:DATABASE_URL = "postgresql+asyncpg://prontivus_v52p_user:E01bQ3fektSOxxZXX6EGz57YfPXIExDW@dpg-d3iej3k9c44c73anq430-a.oregon-postgres.render.com/prontivus_v52p"
$env:SECRET_KEY = "your-secret-key-change-in-production"
$env:JWT_SECRET_KEY = "your-jwt-secret-key-change-in-production"
$env:REDIS_URL = "redis://localhost:6379/0"

Write-Host "Environment variables set." -ForegroundColor Yellow
Write-Host ""

# Start the server
Write-Host "Starting FastAPI server on http://127.0.0.1:8001" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
