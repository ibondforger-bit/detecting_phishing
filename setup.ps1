# PhishGuard — Automated PowerShell Setup Script

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  PhishGuard Security - Automated Setup Script" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# Ensure Python is installed
try {
    $pythonVer = & python --version 2>&1
    Write-Host "[INFO] Detected Python: $pythonVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in system PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.11 or higher and re-run this script." -ForegroundColor Yellow
    Exit 1
}

# 1. Create Virtual Environment if not exists
if (-not (Test-Path ".venv")) {
    Write-Host "[INFO] Creating Python virtual environment (.venv)..." -ForegroundColor Yellow
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        Exit 1
    }
} else {
    Write-Host "[INFO] Existing virtual environment (.venv) detected." -ForegroundColor Green
}

# 2. Activate Virtual Environment and Install Dependencies
Write-Host "[INFO] Installing/updating Python dependencies from requirements.txt..." -ForegroundColor Yellow
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\pip.exe install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Dependency installation failed." -ForegroundColor Red
    Exit 1
}

# 3. Create Folder Structure
Write-Host "[INFO] Setting up /data/ folder structure..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "data", "data/cache", "data/logs", "data/outputs", "whitelist" | Out-Null
New-Item -ItemType File -Force -Path "data/.gitkeep", "data/cache/.gitkeep", "data/logs/.gitkeep", "data/outputs/.gitkeep" | Out-Null

# 4. Create Initial Settings JSON if not exists
if (-not (Test-Path "data/settings.json")) {
    Write-Host "[INFO] Creating initial data/settings.json..." -ForegroundColor Yellow
    $settingsJson = @{
        first_launch = $true
        active_port = 5000
        auto_start = $false
        setup_complete = $false
    } | ConvertTo-Json -Depth 2
    Set-Content -Path "data/settings.json" -Value $settingsJson -Encoding UTF8
}

# 5. Create Initial User Whitelist JSON if not exists
if (-not (Test-Path "whitelist/user_whitelist.json")) {
    Write-Host "[INFO] Creating initial whitelist/user_whitelist.json..." -ForegroundColor Yellow
    $whitelistJson = @{
        version = "1.0"
        user_added_domains = @()
    } | ConvertTo-Json -Depth 2
    Set-Content -Path "whitelist/user_whitelist.json" -Value $whitelistJson -Encoding UTF8
}

Write-Host ""
Write-Host "[SUCCESS] Setup complete! Launching PhishGuard Desktop Console..." -ForegroundColor Green
Write-Host ""

# 6. Launch PhishGuard App
& .venv\Scripts\python.exe gui.py
