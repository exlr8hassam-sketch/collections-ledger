#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$DIR/whatsapp-bridge/session.tar.gz" ] && [ ! -d "$DIR/whatsapp-bridge/.wwebjs_auth" ]; then
    echo "[+] Unpacking pre-authenticated WhatsApp session..."
    tar -xzf "$DIR/whatsapp-bridge/session.tar.gz" -C "$DIR/whatsapp-bridge"
fi

echo "[+] Starting WhatsApp Web Bridge on internal port 3000..."
cd "$DIR/whatsapp-bridge"
BRIDGE_PORT=3000 node server.js &

PUBLIC_PORT="${PORT:-8000}"
echo "[+] Starting Collections Ledger Dashboard on port $PUBLIC_PORT..."
cd "$DIR"
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PUBLIC_PORT"