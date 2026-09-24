# ============================================================
# AUTO-001 Y Runnable Handoff - First-install setup
# Usage:  Set-ExecutionPolicy -Scope Process Bypass
#         .\setup_y.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

Write-Host "=== AUTO-001 Y Handoff Setup ==="

# ---- Detect Python (prefer python, then py -3.12) ----
$pythonCmd = $null
try {
    python --version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $pythonCmd = "python" }
} catch {}

if (-not $pythonCmd) {
    try {
        py -3.12 --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $pythonCmd = "py -3.12" }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "[ERROR] Python not found." -ForegroundColor Red
    Write-Host "Install Python 3.12.x and tick 'Add python.exe to PATH', then retry."
    exit 1
}

Write-Host ("Using Python command: " + $pythonCmd)
if ($pythonCmd -eq "python") {
    python --version
} else {
    py -3.12 --version
}

# ---- Create venv ----
$venv = Join-Path $Root ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment (.venv) ..."
    if ($pythonCmd -eq "python") {
        python -m venv .venv
    } else {
        py -3.12 -m venv .venv
    }
} else {
    Write-Host ".venv already exists."
}

# ---- Activate ----
. (Join-Path $Root ".venv\Scripts\Activate.ps1")

# ---- Install ----
Write-Host "Upgrading pip ..."
python -m pip install --upgrade pip

Write-Host "Installing requirements-handoff.txt ..."
python -m pip install -r (Join-Path $Root "requirements-handoff.txt")

Write-Host ""
Write-Host "SETUP COMPLETE." -ForegroundColor Green
Write-Host "Next: .\verify_y.ps1"
