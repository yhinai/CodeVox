# HTTPS Setup Guide

## Why HTTPS is Required

Modern browsers require **HTTPS** (secure connection) to access sensitive APIs like:
- Microphone (`getUserMedia`)
- Camera
- Geolocation
- Other device sensors

**Exception:** `localhost` and `127.0.0.1` are treated as "secure contexts" even with HTTP.

## When You Need HTTPS

You need HTTPS when:
- Accessing the server from a **non-localhost** address (e.g., `192.168.x.x`, `0.0.0.0`)
- Accessing from another device on your network
- Deploying to a remote server
- Using the voice features (microphone access)

## Quick Start

### 1. Enable HTTPS

Edit your `.env` file:

```bash
USE_HTTPS=true
```

### 2. SSL Certificates are Already Generated

Self-signed certificates are included in the `certs/` directory:
- `certs/cert.pem` - SSL certificate
- `certs/key.pem` - Private key

These certificates are valid for **365 days** and work for `localhost`.

### 3. Start the Server

```bash
npm run dev
```

You should see:
```
🔒 HTTPS enabled
🌐 Interface: https://0.0.0.0:7005
🔒 Running with HTTPS (self-signed certificate)
⚠️  You may need to accept the security warning in your browser
```

### 4. Accept the Security Warning

Since we're using a **self-signed certificate** (not from a trusted CA), your browser will show a security warning.

**Chrome/Edge:**
1. You'll see "Your connection is not private"
2. Click "Advanced"
3. Click "Proceed to [your-ip] (unsafe)"

**Firefox:**
1. You'll see "Warning: Potential Security Risk Ahead"
2. Click "Advanced"
3. Click "Accept the Risk and Continue"

**Safari:**
1. Click "Show Details"
2. Click "visit this website"
3. Enter your password if prompted

## Regenerate Certificates (Optional)

If you need to regenerate the SSL certificates:

```bash
cd /home/green/code/claudia/realtime-to-mcp/examples/voice-demo

# Generate new certificates
openssl req -x509 -newkey rsa:4096 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -days 365 \
  -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### Custom Domain/IP

To use a specific IP or domain, change the `CN` (Common Name):

```bash
# For a specific IP address
openssl req -x509 -newkey rsa:4096 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -days 365 \
  -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=192.168.1.100"

# For a domain name
openssl req -x509 -newkey rsa:4096 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -days 365 \
  -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=myserver.local"
```

## Disable HTTPS (Localhost Only)

If you only access from `localhost` or `127.0.0.1`, you can disable HTTPS:

```bash
# In .env file
USE_HTTPS=false
HOST=localhost
PORT=8085
```

Then access via: `http://localhost:8085`

## Production Deployment

For production, use **Let's Encrypt** for free, trusted SSL certificates:

### Using Certbot (Let's Encrypt)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Generate certificate (requires domain name)
sudo certbot certonly --standalone -d yourdomain.com

# Certificates will be at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Copy to project
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem certs/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem certs/key.pem
sudo chown $USER:$USER certs/*.pem
```

### Using Nginx as Reverse Proxy

Alternatively, use Nginx to handle SSL:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:7005;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Then run the app with HTTP (Nginx handles SSL):
```bash
USE_HTTPS=false
HOST=localhost
PORT=7005
```

## Troubleshooting

### "Your connection is not private" keeps appearing

**Solution:** You must accept the certificate warning each time you access from a new browser/incognito window. This is normal for self-signed certificates.

### Microphone still not working

**Checklist:**
1. ✅ HTTPS enabled (`USE_HTTPS=true`)
2. ✅ Accessing via HTTPS URL (look for 🔒 in browser)
3. ✅ Security warning accepted
4. ✅ Microphone permission granted (check browser's address bar)
5. ✅ Microphone not in use by another app

### Certificate expired

Self-signed certificates expire after 365 days. Regenerate them:

```bash
cd /home/green/code/claudia/realtime-to-mcp/examples/voice-demo
rm certs/*.pem
# Run the openssl command from "Regenerate Certificates" section above
```

### "Failed to load SSL certificates"

**Causes:**
- `certs/` directory missing
- Certificate files missing or wrong permissions

**Solution:**
```bash
# Ensure directory exists
mkdir -p certs

# Regenerate certificates (see above)

# Fix permissions
chmod 644 certs/cert.pem
chmod 600 certs/key.pem
```

### WebSocket connection fails with HTTPS

Make sure your client code uses `wss://` (not `ws://`) when HTTPS is enabled:

```javascript
// Wrong
const ws = new WebSocket('ws://example.com:7005');

// Correct
const ws = new WebSocket('wss://example.com:7005');
```

The voice demo automatically handles this based on the current protocol.

## Security Notes

⚠️ **Self-signed certificates are NOT recommended for production**

- Browsers will always show warnings
- No protection against man-in-the-middle attacks
- Users must manually accept the risk

✅ **For production, always use trusted certificates:**
- Let's Encrypt (free)
- Commercial CA (Comodo, DigiCert, etc.)
- Cloudflare (free with their service)

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_HTTPS` | `false` | Enable HTTPS with self-signed certificates |
| `HOST` | `localhost` | Server host address |
| `PORT` | `8085` | Server port |
| `OPENAI_API_KEY` | - | Required: Your OpenAI API key |

## File Structure

```
voice-demo/
├── certs/
│   ├── cert.pem          # SSL certificate
│   └── key.pem           # Private key (keep secure!)
├── .env                  # Configuration (gitignored)
├── .env.example          # Example configuration
├── server.ts             # Server with HTTPS support
└── HTTPS_SETUP.md        # This file
```

## Additional Resources

- [Let's Encrypt](https://letsencrypt.org/) - Free SSL certificates
- [MDN: Secure Contexts](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts) - Browser security requirements
- [OpenSSL Documentation](https://www.openssl.org/docs/) - Certificate generation
