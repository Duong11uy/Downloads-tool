#!/bin/bash
set -e

echo "[1] Pulling latest code..."
cd /root/Downloads-tool
git fetch origin
git reset --hard origin/main

echo "[2] Installing dependencies..."
pip install -r requirements.txt --break-system-packages

echo "[3] Configuring systemd service..."
cat > /etc/systemd/system/novel-downloader.service << 'EOF'
[Unit]
Description=Web Novel Downloader
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Downloads-tool
ExecStart=/usr/bin/python3 /root/Downloads-tool/src/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "[4] Reloading systemd and starting service..."
systemctl daemon-reload
systemctl enable novel-downloader
systemctl restart novel-downloader

echo "[5] Checking status..."
sleep 3
systemctl status novel-downloader --no-pager
curl -I http://localhost:8000
