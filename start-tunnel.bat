@echo off
title Cloudflare Tunnel - Remote Phone Access
echo ===================================================
echo   Starting Remote Access Tunnel for Mobile...
echo ===================================================
echo.
echo Below is your secure public link for your phone:
echo.
npx --yes cloudflared tunnel --url http://127.0.0.1:8000
pause
