const fs = require('fs');
const path = require('path');

const utilsPath = path.join(__dirname, 'node_modules', 'whatsapp-web.js', 'src', 'util', 'Injected', 'Utils.js');

if (fs.existsSync(utilsPath)) {
    let content = fs.readFileSync(utilsPath, 'utf8');
    if (!content.includes('delete message.__x_id;')) {
        const target = '...extraOptions,\n        };';
        const targetCrlf = '...extraOptions,\r\n        };';
        const replacement = '...extraOptions,\n        };\n\n        delete message.__x_id;\n        message.id = newMsgKey;';
        
        if (content.includes(target)) {
            content = content.replace(target, replacement);
            fs.writeFileSync(utilsPath, content, 'utf8');
            console.log('[✓] Successfully applied __x_id memoize patch to Utils.js (LF)');
        } else if (content.includes(targetCrlf)) {
            content = content.replace(targetCrlf, replacement.replace(/\n/g, '\r\n'));
            fs.writeFileSync(utilsPath, content, 'utf8');
            console.log('[✓] Successfully applied __x_id memoize patch to Utils.js (CRLF)');
        } else {
            console.log('[!] Warning: Could not locate patch insertion target in Utils.js');
        }
    } else {
        console.log('[i] Utils.js already patched with __x_id fix.');
    }
} else {
    console.log('[i] Utils.js not found at:', utilsPath);
}
