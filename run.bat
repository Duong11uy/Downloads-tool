@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo     WEB NOVEL DOWNLOADER - LOCAL SERVER LAUNCHER
echo ===================================================
echo.

rem Them thu muc DLL cua MSYS2 neu co
if exist "C:\msys64\ucrt64\bin" set "PATH=C:\msys64\ucrt64\bin;%PATH%"

rem Thiet lap PYTHONPATH tro den thu muc goc cua du an
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

rem 1. Tim Python tren he thong
set "PY="
python --version >nul 2>&1 && set "PY=python"
if "%PY%"=="" py -3 --version >nul 2>&1 && set "PY=py -3"
if "%PY%"=="" py --version >nul 2>&1 && set "PY=py"
if "%PY%"=="" python3 --version >nul 2>&1 && set "PY=python3"
if "%PY%"=="" if exist "C:\msys64\ucrt64\bin\python.exe" set "PY=C:\msys64\ucrt64\bin\python.exe"
if "%PY%"=="" if exist "C:\msys64\mingw64\bin\python.exe" set "PY=C:\msys64\mingw64\bin\python.exe"
if "%PY%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"

if "%PY%"=="" (
    echo [ERROR] Khong tim thay Python tren may tinh!
    echo Vui long cai dat Python tu https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [*] Tim thay Python: %PY%

rem 2. Xac dinh trinh thong dich
set "RUN_PY=venv\Scripts\python.exe"
if not exist "%RUN_PY%" set "RUN_PY=venv\bin\python.exe"
if not exist "%RUN_PY%" set "RUN_PY=%PY%"

echo [*] Trinh thong dich: %RUN_PY%
echo [*] Dang kiem tra va cai dat thu vien...
echo.

"%RUN_PY%" -m pip install beautifulsoup4 requests httpx 2>nul || echo [*] Tiep tuc khoi dong may chu...

:server_loop
echo.
echo ===================================================
echo   DANG KHOI CHAY MAY CHU WEB NOVEL DOWNLOADER...
echo ===================================================
echo.

"%RUN_PY%" src\app.py

set "EXIT_CODE=%errorlevel%"
if %EXIT_CODE% equ 42 (
    echo.
    echo [*] [HOT-RELOAD] Phat hien code thay doi. Dang nap lai may chu ngay lap tuc...
    timeout /t 1 /nobreak >nul
    goto server_loop
)

echo.
echo ===================================================
if %EXIT_CODE% neq 0 (
    echo [THONG BAO] May chu dung voi ma: %EXIT_CODE%. Dang tu dong khoi dong lai sau 2 giay...
    timeout /t 2 /nobreak >nul
    goto server_loop
) else (
    echo [THONG BAO] May chu da dung.
)
echo ===================================================
echo.
pause
