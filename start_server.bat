@echo off
set "SSH_ASKPASS=C:\Users\TOPV.LAPTOP.144\askpass.bat"
set "SSH_ASKPASS_REQUIRE=force"
set "DISPLAY=dummy:0"

ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "pkill -f 'src/app.py' || true; cd /root/Downloads-tool && nohup python3 src/app.py > app.log 2>&1 & sleep 3 && curl -I http://localhost:8000" < nul > "d:\HuySpace\Downloads tool\start_log.txt" 2>&1
