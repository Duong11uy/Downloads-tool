@echo off
set "SSH_ASKPASS=C:\Users\TOPV.LAPTOP.144\askpass.bat"
set "SSH_ASKPASS_REQUIRE=force"
set "DISPLAY=dummy:0"

ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "cat /root/Downloads-tool/app.log" < nul > "d:\HuySpace\Downloads tool\server_app.log" 2>&1
