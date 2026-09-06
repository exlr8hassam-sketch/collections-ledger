#!/bin/bash
set -e

if [ -f "/app/whatsapp-bridge/session.tar.gz" ] && [ ! -d "/app/whatsapp-bridge/.wwebjs_auth" ]; then
    echo "[+] Unpacking pre-authenticated WhatsApp session..."
    tar -xzf /app/whatsapp-bridge/session.tar.gz -C /app/whatsapp-bridge
fi

echo "[+] Starting WhatsApp Web Bridge on internal port 3000..."
cd /app/whatsapp-bridge
BRIDGE_PORT=3000 node server.js &

PUBLIC_PORT="${PORT:-10000}"
echo "[+] Starting Collections Ledger Dashboard on port $PUBLIC_PORT..."
cd /app
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PUBLIC_PORT"