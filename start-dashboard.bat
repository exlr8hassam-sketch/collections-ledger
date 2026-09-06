@echo off
title Payment Reminder Agent - Web Dashboard
echo ===================================================
echo   Starting Payment Reminder Dashboard UI...
echo ===================================================
cd /d "%~dp0"

for /f "tokens=*" %%i in ('powershell -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169\.'} | Select-Object -First 1).IPAddress"') do set LOCAL_IP=%%i

echo ===================================================
echo   DASHBOARD IS READY!
echo   * On this PC:    http://localhost:8000
if not "%LOCAL_IP%"=="" (
echo   * On your Phone: http://%LOCAL_IP%:8000
)
echo ===================================================
start "" "http://localhost:8000"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000
pause
