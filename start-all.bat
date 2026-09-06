@echo off
title Launch All - WhatsApp Reminder Agent & Dashboard
echo ===================================================
echo   Launching WhatsApp Bridge & Web Dashboard...
echo ===================================================

echo [*] Starting WhatsApp Web Bridge in background window...
start "WhatsApp Web Bridge" cmd /k "cd /d %~dp0whatsapp-bridge && node server.js"

echo [*] Waiting 3 seconds for bridge initialization...
timeout /t 3 /nobreak >nul

for /f "tokens=*" %%i in ('powershell -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169\.'} | Select-Object -First 1).IPAddress"') do set LOCAL_IP=%%i

echo ===================================================
echo   DASHBOARD IS READY!
echo   * On this PC:    http://localhost:8000
if not "%LOCAL_IP%"=="" (
echo   * On your Phone: http://%LOCAL_IP%:8000
)
echo ===================================================
start "" "http://localhost:8000"
cd /d "%~dp0"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
pause
