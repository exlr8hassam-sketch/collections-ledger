@echo off
title WhatsApp Web Bridge - Payment Reminder Agent
echo ===================================================
echo   Starting WhatsApp Bridge Service...
echo ===================================================
cd /d "%~dp0whatsapp-bridge"
node server.js
pause
