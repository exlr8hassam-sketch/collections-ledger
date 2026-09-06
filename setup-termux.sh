#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "==================================================="
echo "  Setting up Collections Ledger on Android Termux  "
echo "==================================================="

pkg update -y
pkg install -y git python nodejs clang make libjpeg-turbo freetype libpng rust binutils
pkg install -y tur-repo || true
pkg install -y python-pydantic python-cryptography python-pillow || true

pip install fastapi uvicorn requests python-dotenv reportlab google-genai pydantic

cd whatsapp-bridge
npm install
cd ..

chmod +x start.sh

echo "==================================================="
echo "  Installation Complete! Launching Ledger...      "
echo "  Open your mobile browser at: http://localhost:8000"
echo "==================================================="

./start.sh
