@echo off
title Trien khai cap nhat len Server - Downloads Tool
color 0A

echo ======================================================================
echo   BƯỚC 1: DANG DAY MA NGUON MOI LEN GITHUB...
echo ======================================================================
echo.

git add .
git commit -m "fix: auto cloudflare bypass with curl_cffi and adaptive rate limit"
git push -u origin main

echo.
echo ======================================================================
echo   BƯỚC 2: DANG CAP NHAT VA KHOI DONG LAI TREN SERVER (100.93.95.78)...
echo ======================================================================
echo.

set "PY_EXEC="
where python >nul 2>&1 && set "PY_EXEC=python"
if not defined PY_EXEC (
    where py >nul 2>&1 && set "PY_EXEC=py"
)
if not defined PY_EXEC (
    if exist "venv\bin\python.exe" set "PY_EXEC=venv\bin\python.exe"
    if exist "venv\Scripts\python.exe" set "PY_EXEC=venv\Scripts\python.exe"
)
if not defined PY_EXEC set "PY_EXEC=python"

echo [*] Dang chay script deploy bang: %PY_EXEC%
%PY_EXEC% deploy_server.py

echo.
echo ======================================================================
echo   DA HOAN TAT TRIEN KHAI!
echo ======================================================================
echo.
pause
