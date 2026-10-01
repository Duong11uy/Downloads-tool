#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "==================================================="
echo "    WEB NOVEL DOWNLOADER - KHỞI CHẠY TRÊN LINUX"
echo "==================================================="

# Kiểm tra python3
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] python3 chưa được cài đặt. Vui lòng cài đặt: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

# Khởi tạo venv nếu chưa có
if [ ! -d "venv" ]; then
    echo "[*] Đang khởi tạo môi trường ảo Python (venv)..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[*] Cài đặt dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "==================================================="
echo "  Máy chủ đang chạy tại: http://localhost:8000"
echo "==================================================="
echo ""

python3 src/app.py
