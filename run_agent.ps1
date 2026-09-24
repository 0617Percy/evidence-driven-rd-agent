# ============================================================
# AUTO-001 Y Runnable Handoff - Launch the Agent
# Usage:  .\run_agent.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"

if (Test-Path $activate) {
    . $activate
    Write-Host "Activated .venv"
} else {
    Write-Host "[WARN] .venv not found - using system python. Run .\setup_y.ps1 first." -ForegroundColor Yellow
}

Write-Host "Starting AUTO-001 Agent ..."
Write-Host "Open http://localhost:8501 in your browser." -ForegroundColor Green
Write-Host "(Press Ctrl+C to stop.)"

python -m streamlit run (Join-Path $Root "app.py")
