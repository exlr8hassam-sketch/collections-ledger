@echo off
title Switch WhatsApp Sender Account - Payment Reminder
cls
echo ================================================================
echo          Switch WhatsApp Sender Account
echo ================================================================
echo.
echo This tool resets your WhatsApp connection and lets you connect
echo a different WhatsApp account to send reminders.
echo.
echo [1] Disconnect current WhatsApp and link a NEW account
echo [2] Keep current account and exit
echo.
set /p CHOICE="Select an option (1 or 2): "
if not "%CHOICE%"=="1" (
    echo Operation cancelled. Exiting...
    pause
    exit /b
)

echo.
echo [*] Stopping running WhatsApp bridge processes...
taskkill /f /im node.exe 2>nul
timeout /t 1 /nobreak >nul

echo [*] Removing saved login session...
if exist "%~dp0whatsapp-bridge\.wwebjs_auth" (
    rmdir /s /q "%~dp0whatsapp-bridge\.wwebjs_auth"
)
if exist "%~dp0whatsapp-bridge\qr.png" (
    del /f /q "%~dp0whatsapp-bridge\qr.png"
)
if exist "%~dp0whatsapp-bridge\pairing_code.txt" (
    del /f /q "%~dp0whatsapp-bridge\pairing_code.txt"
)

echo [OK] Previous session removed!
echo.
echo ================================================================
echo How would you like to link the new WhatsApp account?
echo ================================================================
echo - Option A (Pairing Code): Enter phone number with country code
echo   (e.g., 923001234567 or 15551234567)
echo - Option B (QR Code Scan): Just press ENTER
echo.
set /p NEW_PHONE="Enter new sender phone number (or press ENTER for QR scan): "

if not "%NEW_PHONE%"=="" (
    set WHATSAPP_PHONE=%NEW_PHONE%
    echo [*] Configured pairing phone to: %NEW_PHONE%
)

echo.
echo [*] Starting WhatsApp Bridge to link your new account...
echo [*] Keep this window open while linking.
echo.
cd /d "%~dp0whatsapp-bridge"
node server.js
pause
