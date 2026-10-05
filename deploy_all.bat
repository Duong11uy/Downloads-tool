@echo off
cd /d "%~dp0"

echo ======================================================================
echo   BUOC 1: DANG DAY CODE MOI LEN GITHUB...
echo ======================================================================
echo.

git add -A
git commit -m "feat: add truyenfull crawler configuration"
git push origin main

echo.
echo ======================================================================
echo   BUOC 2: DANG CAP NHAT VA KHOI DONG LAI SERVER (100.93.95.78)...
echo ======================================================================
echo.

copy /y "%~dp0askpass.bat" "C:\Users\TOPV.LAPTOP.144\askpass.bat" >nul 2>&1
set "SSH_ASKPASS=C:\Users\TOPV.LAPTOP.144\askpass.bat"
set "SSH_ASKPASS_REQUIRE=force"
set "DISPLAY=dummy:0"

echo [*] Dang ket noi SSH va cap nhat code tren server...
ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL root@100.93.95.78 "cd /root/Downloads-tool && git fetch origin && git reset --hard origin/main && pkill -f 'src/app.py' || true; nohup python3 src/app.py > app.log 2>&1 & sleep 3 && curl -I http://localhost:8000" < nul

echo.
echo ======================================================================
echo   DA HOAN TAT TRIEN KHAI LEN SERVER!
echo ======================================================================
echo.
pause