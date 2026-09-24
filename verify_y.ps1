# ============================================================
# AUTO-001 Y Runnable Handoff - Environment verification
# Usage:  .\verify_y.ps1
# Output: Y_RUNTIME_VERIFICATION = PASS / HOLD
# (Delegates all checks to verify_runtime.py - UTF-8 safe.)
# ============================================================

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
Set-Location $Root

$pyOverride = $env:Y_PKG_PYTHON
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

if ($pyOverride -and (Test-Path $pyOverride)) {
    $PY = $pyOverride
} elseif (Test-Path $venvPy) {
    $PY = $venvPy
} else {
    $PY = "python"
}

Write-Host "=== AUTO-001 Y Runtime Verification ==="
Write-Host ("Root: " + $Root)
Write-Host ("Python: " + $PY)
Write-Host ""

& $PY (Join-Path $Root "verify_runtime.py")
exit $LASTEXITCODE
