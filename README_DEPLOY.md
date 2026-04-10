# Smart Project Tracker — Deployment Guide (Hostinger VPS)

## Prerequisites
- Hostinger VPS with Ubuntu 20.04+ or Debian 11+
- SSH access to the server
- Domain name (optional, for SSL)

---

## 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# Create application user
sudo useradd -r -s /bin/false tracker

# Create application directory
sudo mkdir -p /opt/tracker
sudo chown tracker:tracker /opt/tracker
```

## 2. Deploy Application

```bash
# Copy project files to server (from your local machine)
scp -r ./* user@your-server:/opt/tracker/
# Or use git clone

# Set permissions
sudo chown -R tracker:tracker /opt/tracker
```

## 3. Install Dependencies

```bash
# Create virtual environment
python3.11 -m venv /opt/tracker/venv

# Activate and install
source /opt/tracker/venv/bin/activate
pip install -r /opt/tracker/requirements.txt
```

## 4. Google Sheets Credentials

```bash
# Upload your credentials.json to the server
scp credentials.json user@your-server:/opt/tracker/credentials.json

# Secure the file
sudo chmod 600 /opt/tracker/credentials.json
sudo chown tracker:tracker /opt/tracker/credentials.json
```

**Before deploying, ensure:**
1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a Service Account
4. Download the JSON key file → rename to `credentials.json`
5. Create a Google Spreadsheet named "Smart Project Tracker"
6. Create sheets: `samawah_projects`, `kinder_projects`, `todos`
7. Share the spreadsheet with the service account email

## 5. Configure Systemd Service

```bash
# Copy service file
sudo cp /opt/tracker/deploy/tracker.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable tracker
sudo systemctl start tracker

# Check status
sudo systemctl status tracker

# View logs
sudo journalctl -u tracker -f
```

## 6. Configure Nginx

```bash
# Install Nginx
sudo apt install nginx -y

# Copy config
sudo cp /opt/tracker/deploy/nginx.conf /etc/nginx/sites-available/tracker

# Edit server_name to match your domain
sudo nano /etc/nginx/sites-available/tracker

# Enable site
sudo ln -s /etc/nginx/sites-available/tracker /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

## 7. SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d tracker.yourdomain.com

# Auto-renewal is set up by default
sudo certbot renew --dry-run
```

## 8. Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

## Management Commands

```bash
# Restart app
sudo systemctl restart tracker

# View logs
sudo journalctl -u tracker -f

# Update app
cd /opt/tracker
sudo -u tracker git pull
sudo systemctl restart tracker

# Update dependencies
source /opt/tracker/venv/bin/activate
pip install -r /opt/tracker/requirements.txt
sudo systemctl restart tracker
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 Bad Gateway | Check `systemctl status tracker` — app may be down |
| WebSocket errors | Verify Nginx config has `proxy_set_header Upgrade` |
| Credentials error | Check file exists and has correct permissions |
| Sheets not found | Verify spreadsheet name matches `SHEET_NAME` in config.py |
