@echo off
chcp 65001 >nul
title Push to GitHub - Downloads Tool
echo ======================================================================
echo   ĐẨY DỰ ÁN LÊN GITHUB: https://github.com/Duong11uy/Downloads-tool
echo ======================================================================
echo.

if not exist .git (
    echo [*] Khoi tao Git repository...
    git init
)

echo [*] Dat nhanh mac dinh la main...
git branch -M main

echo [*] Cau hinh Remote GitHub...
git remote remove origin 2>nul
git remote add origin https://github.com/Duong11uy/Downloads-tool.git

echo [*] Them tat ca cac file...
git add .

echo [*] Tao Commit...
git commit -m "feat: Novel Downloader web app with XTruyen support, Cloudflare bypass, and chapter sync"

echo.
echo [*] Dang day ma nguon len GitHub (git push)...
git push -u origin main

echo.
if %errorlevel% equ 0 (
    echo ======================================================================
    echo   [THANH CONG] Ma nguon da duoc day len GitHub thanh cong!
    echo ======================================================================
) else (
    echo ======================================================================
    echo   [LUU Y] Neu gap loi tu choi (rejected/conflict), ban co the thu:
    echo   git push -u origin main --force
    echo ======================================================================
)
echo.
pause
