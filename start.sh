#!/bin/bash
set -e

echo "[+] Starting WhatsApp Baileys Bridge..."
cd /app/whatsapp-bridge
node server.js &

echo "[+] Starting Collections Ledger Dashboard..."
cd /app
PORT="${PORT:-8000}"
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"