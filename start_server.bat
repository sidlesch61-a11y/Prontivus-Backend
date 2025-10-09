@echo off
echo Starting Prontivus Backend Server...
echo.

REM Set environment variables
set DATABASE_URL=postgresql+asyncpg://prontivus_v52p_user:E01bQ3fektSOxxZXX6EGz57YfPXIExDW@dpg-d3iej3k9c44c73anq430-a.oregon-postgres.render.com/prontivus_v52p
set SECRET_KEY=your-secret-key-change-in-production
set JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
set REDIS_URL=redis://localhost:6379/0

echo Environment variables set.
echo.

REM Start the server
echo Starting FastAPI server on http://127.0.0.1:8001
echo Press Ctrl+C to stop the server
echo.

py -3.11 -m uvicorn app.main:app --host 127.0.0.1 --port 8001

pause
