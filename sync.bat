@echo off
cd /d "%~dp0"
git add -A
git commit -m "chore: clean temp files"
git push origin main
ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "cd /root/Downloads-tool && git fetch origin && git reset --hard origin/main" < nul
