#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "==================================================="
echo "  Setting up Collections Ledger on Android Termux  "
echo "==================================================="

pkg update -y
pkg install -y git python nodejs clang make libjpeg-turbo freetype libpng

pip install --upgrade pip
pip install -r requirements.txt

cd whatsapp-bridge
npm install
cd ..

chmod +x start.sh

echo "==================================================="
echo "  Installation Complete! Launching Ledger...      "
echo "  Open your mobile browser at: http://localhost:8000"
echo "==================================================="

./start.sh
