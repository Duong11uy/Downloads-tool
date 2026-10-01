# PowerShell Launcher for Web Novel Downloader
Set-Location -Path $PSScriptRoot

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    WEB NOVEL DOWNLOADER - KHOI CHAY MAY CHU LOCAL " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Tìm Python
$pyCmd = $null
foreach ($cmd in @("python", "py", "python3", "C:\msys64\ucrt64\bin\python.exe", "C:\msys64\mingw64\bin\python.exe")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $pyCmd = $cmd
        break
    }
}

if (-not $pyCmd) {
    Write-Host "[LOI] Khong tim thay Python tren may!" -ForegroundColor Red
    Write-Host "Vui long cai dat Python 3.10+ tu https://www.python.org/ va nho tich 'Add Python to PATH'." -ForegroundColor Yellow
    Read-Host "Nhan Enter de thoat..."
    exit 1
}

Write-Host "[*] Tim thay Python: $pyCmd" -ForegroundColor Gray

# 2. Khoi tao moi truong ao venv
if (-not (Test-Path "venv")) {
    Write-Host "[*] Dang khoi tao moi truong ao Python (venv)..." -ForegroundColor Yellow
    try {
        & $pyCmd -m venv venv
    } catch {
        Write-Host "[Canh bao] Khong tao duoc venv, su dung truc tiep Python he thong." -ForegroundColor Yellow
    }
}

# 3. Xac dinh python trong venv
$venvPython = $null
if (Test-Path "venv\Scripts\python.exe") {
    $venvPython = "venv\Scripts\python.exe"
} elseif (Test-Path "venv\bin\python.exe") {
    $venvPython = "venv\bin\python.exe"
} else {
    $venvPython = $pyCmd
}

Write-Host "[*] Trinh thong dich: $venvPython" -ForegroundColor Gray
Write-Host "[*] Dang kiem tra va cai dat thu vien..." -ForegroundColor Yellow

try {
    & $venvPython -m pip install -r requirements.txt
} catch {
    Write-Host "[Canh bao] Dang cai dat cac thu vien cot loi..." -ForegroundColor Yellow
    & $venvPython -m pip install fastapi uvicorn httpx beautifulsoup4 lxml requests pydantic python-multipart
}

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "  May chu dang chay tai: http://localhost:8000" -ForegroundColor Green
Write-Host "  Mo trinh duyet va truy cap: http://localhost:8000" -ForegroundColor White
Write-Host "  Nhan Ctrl+C de dung may chu." -ForegroundColor Gray
Write-Host "===================================================`n" -ForegroundColor Cyan

& $venvPython src\app.py
Read-Host "Nhan Enter de thoat..."
