const express = require('express');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');

// Global error handlers so puppeteer frame detach/navigation never crashes server
process.on('uncaughtException', (err) => {
    console.log('[Notice] Background uncaught exception handled:', err.message);
});
process.on('unhandledRejection', (reason) => {
    console.log('[Notice] Background unhandled rejection handled:', reason?.message || reason);
});

const app = express();
app.use(express.json());

app.get('/', (req, res) => {
    res.json({ status: 'WhatsApp Bridge Online', ready: isReady });
});

const PORT = process.env.BRIDGE_PORT || 3000;
let isReady = false;
let currentQrData = null;
let client = null;
let pairingCodeRequested = false;

const USER_PHONE = process.env.WHATSAPP_PHONE || '923329755091';

console.log('====================================================');
console.log('       WhatsApp Web Bridge for Reminder Agent        ');
console.log('====================================================');

function createWhatsAppClient() {
    isReady = false;
    pairingCodeRequested = false;

    console.log('[*] Initializing WhatsApp Web client instance...');

    const isWin = process.platform === 'win32';
    const winChrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
    let execPath = process.env.PUPPETEER_EXECUTABLE_PATH;
    if (!execPath) {
        if (isWin && fs.existsSync(winChrome)) {
            execPath = winChrome;
        } else if (!isWin && fs.existsSync('/usr/bin/chromium')) {
            execPath = '/usr/bin/chromium';
        } else if (!isWin && fs.existsSync('/usr/bin/chromium-browser')) {
            execPath = '/usr/bin/chromium-browser';
        }
    }

    const puppeteerConfig = {
        headless: true,
        protocolTimeout: 120000,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--no-first-run',
            '--disable-gpu',
            '--disable-blink-features=AutomationControlled',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ]
    };
    if (execPath) {
        puppeteerConfig.executablePath = execPath;
    }

    client = new Client({
        authStrategy: new LocalAuth({
            dataPath: path.join(__dirname, '.wwebjs_auth')
        }),
        puppeteer: puppeteerConfig
    });

    client.on('qr', async (qr) => {
        currentQrData = qr;
        console.log('\n[!] QR code ready. Generating 8-digit Pairing Code for', USER_PHONE, '...');
        qrcodeTerminal.generate(qr, { small: true });

        try {
            const qrImagePath = path.join(__dirname, 'qr.png');
            await QRCode.toFile(qrImagePath, qr);
        } catch (err) {}

        if (!pairingCodeRequested) {
            pairingCodeRequested = true;
            try {
                const cleanPhone = USER_PHONE.replace(/[^0-9]/g, '');
                const pairingCode = await client.requestPairingCode(cleanPhone);
                console.log('\n====================================================');
                console.log(`[⭐] YOUR 8-CHARACTER PAIRING CODE:  ${pairingCode}`);
                console.log('====================================================');
                console.log('On your phone:');
                console.log('1. Open WhatsApp -> Linked Devices -> Link a Device');
                console.log('2. Tap "Link with phone number instead" at the bottom');
                console.log(`3. Enter this code: ${pairingCode}\n`);
                
                fs.writeFileSync(path.join(__dirname, 'pairing_code.txt'), pairingCode);
            } catch (e) {
                console.log('Could not request pairing code automatically:', e.message);
            }
        }
    });

    client.on('authenticated', () => {
        console.log('[✓] WhatsApp session authenticated successfully!');
    });

    client.on('auth_failure', (msg) => {
        console.error('[X] Authentication failure:', msg);
    });

    client.on('ready', () => {
        isReady = true;
        console.log('\n====================================================');
        console.log('[✓] WhatsApp is READY to send automated messages!');
        console.log(`[✓] Listening for send requests on http://localhost:${PORT}`);
        console.log('====================================================\n');
    });

    client.on('disconnected', async (reason) => {
        isReady = false;
        console.log('[!] WhatsApp disconnected:', reason);
        try {
            await client.destroy();
        } catch (e) {}
        console.log('[!] Recreating fresh client in 4 seconds...');
        setTimeout(() => {
            createWhatsAppClient();
        }, 4000);
    });

    client.initialize().catch(err => {
        console.log('[Notice] Client init notice:', err.message);
    });
}

// Serve live auto-refreshing QR code page in browser
app.get('/qr', (req, res) => {
    if (isReady) {
        return res.send("<h2 style='font-family:sans-serif;color:#008069;text-align:center;margin-top:60px;'>✅ WhatsApp is already connected and ready!</h2>");
    }
    const html = `
    <!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp QR Code - Live</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: system-ui, -apple-system, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f0f2f5; }
            .card { background: white; padding: 32px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.06); text-align: center; border: 1px solid #e2e8f0; }
            img { width: 280px; height: 280px; border-radius: 12px; border: 1px solid #edf2f7; }
            h2 { margin: 0 0 6px 0; color: #0f172a; font-size: 22px; }
            p { margin: 0 0 20px 0; color: #64748b; font-size: 13px; }
            .badge { display: inline-block; background: #dcfce7; color: #166534; font-weight: 700; font-size: 11px; padding: 4px 12px; border-radius: 20px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">● Live QR (Auto-Refreshes)</span>
            <h2>Scan WhatsApp QR Code</h2>
            <p>Open WhatsApp &rarr; Linked Devices &rarr; Link a Device</p>
            <img src="/qr-img?t=${Date.now()}" alt="QR Code" />
            <p style="margin-top: 18px; font-size: 12px; color: #94a3b8;">Refreshes every 5s so the QR never expires while you scan.</p>
        </div>
    </body>
    </html>
    `;
    res.send(html);
});

app.get('/qr-img', (req, res) => {
    const qrImagePath = path.join(__dirname, 'qr.png');
    if (fs.existsSync(qrImagePath)) {
        res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, private');
        res.sendFile(qrImagePath);
    } else {
        res.status(404).send('QR generating...');
    }
});

// Check service status
app.get('/status', (req, res) => {
    const codePath = path.join(__dirname, 'pairing_code.txt');
    let code = null;
    if (fs.existsSync(codePath)) {
        try {
            code = fs.readFileSync(codePath, 'utf8').trim();
        } catch (e) {}
    }
    res.json({
        ready: isReady,
        status: isReady ? 'connected' : 'authenticating_or_disconnected',
        pairingCode: code,
        userPhone: USER_PHONE
    });
});

// Request pairing code for a specific phone number
app.post('/pair', async (req, res) => {
    const phone = req.body?.phone || USER_PHONE;
    try {
        if (!client) {
            return res.status(503).json({ success: false, error: 'Client not ready' });
        }
        let cleanPhone = phone.replace(/[^0-9]/g, '');
        if (cleanPhone.startsWith('03') && cleanPhone.length === 11) {
            cleanPhone = '92' + cleanPhone.slice(1);
        } else if (cleanPhone.startsWith('3') && cleanPhone.length === 10) {
            cleanPhone = '92' + cleanPhone;
        }
        console.log(`[*] Requesting WhatsApp pairing code for: ${cleanPhone}`);
        const code = await client.requestPairingCode(cleanPhone);
        fs.writeFileSync(path.join(__dirname, 'pairing_code.txt'), code);
        console.log(`[⭐] Generated 8-digit Pairing Code: ${code}`);
        return res.json({ success: true, pairingCode: code });
    } catch (e) {
        console.error('[X] Pairing code request failed:', e.message);
        return res.status(500).json({ success: false, error: e.message });
    }
});

// Disconnect current session and allow switching accounts
app.post('/disconnect', async (req, res) => {
    console.log('[*] Disconnect request received. Logging out current WhatsApp account...');
    try {
        isReady = false;
        if (client) {
            try {
                await client.logout();
            } catch (e) {
                console.log('Logout notice:', e.message);
            }
            try {
                await client.destroy();
            } catch (e) {}
        }
        const codePath = path.join(__dirname, 'pairing_code.txt');
        if (fs.existsSync(codePath)) fs.unlinkSync(codePath);
        const qrPath = path.join(__dirname, 'qr.png');
        if (fs.existsSync(qrPath)) fs.unlinkSync(qrPath);

        setTimeout(() => {
            createWhatsAppClient();
        }, 3000);

        return res.json({ success: true, message: 'Logged out. Ready to pair new WhatsApp account.' });
    } catch (err) {
        return res.status(500).json({ success: false, error: err.message });
    }
});

// Send WhatsApp text endpoint
app.post('/send', async (req, res) => {
    const { phone, message } = req.body;

    if (!isReady) {
        return res.status(503).json({
            success: false,
            error: 'WhatsApp client is not ready. Please scan the QR code first.'
        });
    }

    if (!phone || !message) {
        return res.status(400).json({
            success: false,
            error: 'Missing phone or message in request body.'
        });
    }

    try {
        let cleanNumber = phone.replace(/[^0-9]/g, '');
        // Auto-fix Pakistani numbers: 0300... -> 92300... or 300... -> 92300...
        if (cleanNumber.startsWith('03') && cleanNumber.length === 11) {
            cleanNumber = '92' + cleanNumber.substring(1);
        } else if (cleanNumber.startsWith('3') && cleanNumber.length === 10) {
            cleanNumber = '92' + cleanNumber;
        }

        let targetChatId = `${cleanNumber}@c.us`;
        try {
            const numberDetails = await client.getNumberId(cleanNumber);
            if (numberDetails && numberDetails._serialized) {
                targetChatId = numberDetails._serialized;
            }
        } catch (e) {
            console.log('[Notice] getNumberId resolution skipped:', e.message);
        }

        console.log(`[*] Sending WhatsApp message to: ${targetChatId}`);
        const response = await client.sendMessage(targetChatId, message);
        const msgId = response?.id?._serialized || response?.id || 'SENT_OK';

        console.log(`[✓] Message sent successfully to ${targetChatId} (ID: ${msgId})`);
        return res.json({
            success: true,
            messageId: msgId
        });
    } catch (err) {
        console.error(`[X] Failed to send message to ${phone}:`, err);
        return res.status(500).json({
            success: false,
            error: err.message
        });
    }
});

// Send WhatsApp media/PDF endpoint
app.post('/send-media', async (req, res) => {
    const { phone, filePath, caption, filename } = req.body;

    if (!isReady) {
        return res.status(503).json({
            success: false,
            error: 'WhatsApp client is not ready. Please scan the QR code first.'
        });
    }

    if (!phone || !filePath) {
        return res.status(400).json({
            success: false,
            error: 'Missing phone or filePath in request body.'
        });
    }

    if (!fs.existsSync(filePath)) {
        return res.status(404).json({
            success: false,
            error: `File not found on disk: ${filePath}`
        });
    }

    try {
        let cleanNumber = phone.replace(/[^0-9]/g, '');
        if (cleanNumber.startsWith('03') && cleanNumber.length === 11) {
            cleanNumber = '92' + cleanNumber.substring(1);
        } else if (cleanNumber.startsWith('3') && cleanNumber.length === 10) {
            cleanNumber = '92' + cleanNumber;
        }

        let targetChatId = `${cleanNumber}@c.us`;
        try {
            const numberDetails = await client.getNumberId(cleanNumber);
            if (numberDetails && numberDetails._serialized) {
                targetChatId = numberDetails._serialized;
            }
        } catch (e) {
            console.log('[Notice] getNumberId resolution skipped:', e.message);
        }

        console.log(`[*] Sending WhatsApp PDF Media (${filePath}) to: ${targetChatId}`);
        const media = MessageMedia.fromFilePath(filePath);
        if (filename) {
            media.filename = filename;
        }

        const response = await client.sendMessage(targetChatId, media, { caption: caption || '' });
        const msgId = response?.id?._serialized || response?.id || 'SENT_OK';

        console.log(`[✓] PDF Media sent successfully to ${targetChatId} (ID: ${msgId})`);
        return res.json({
            success: true,
            messageId: msgId
        });
    } catch (err) {
        console.error(`[X] Failed to send media to ${phone}:`, err);
        return res.status(500).json({
            success: false,
            error: err.message
        });
    }
});

app.listen(PORT, () => {
    console.log(`[*] Bridge HTTP server listening on port ${PORT}`);
    createWhatsAppClient();
});
