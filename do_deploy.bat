@echo off
set "SSH_ASKPASS=C:\Users\TOPV.LAPTOP.144\askpass.bat"
set "SSH_ASKPASS_REQUIRE=force"
set "DISPLAY=dummy:0"

echo [1/4] Dang ket noi SSH va cap nhat ma nguon tu GitHub...
ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "if [ ! -d /root/Downloads-tool ]; then git clone https://github.com/Duong11uy/Downloads-tool.git /root/Downloads-tool; else cd /root/Downloads-tool && git pull origin main; fi" < nul > "d:\HuySpace\Downloads tool\deploy_exec.log" 2>&1

echo [2/4] Dang cai dat thu vien Python tren server...
ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "cd /root/Downloads-tool && apt update && apt install -y python3 python3-pip && (pip install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt)" < nul >> "d:\HuySpace\Downloads tool\deploy_exec.log" 2>&1

echo [3/4] Dang khoi dong ung dung tren server...
ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "pkill -f 'src/app.py' || true; cd /root/Downloads-tool && nohup python3 src/app.py > app.log 2>&1 &" < nul >> "d:\HuySpace\Downloads tool\deploy_exec.log" 2>&1

echo [4/4] Dang kiem tra trang thai server...
ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "sleep 3; curl -I http://localhost:8000; ps aux | grep 'src/app.py'" < nul >> "d:\HuySpace\Downloads tool\deploy_exec.log" 2>&1

echo [XONG] Hoan tat trien khai! >> "d:\HuySpace\Downloads tool\deploy_exec.log"
