# MindMate - start the server (Windows PowerShell)
#   powershell -ExecutionPolicy Bypass -File .\run.ps1 -Mock     # UI test, no model
#   powershell -ExecutionPolicy Bypass -File .\run.ps1           # real local model (Gemma 4 12B, 4-bit)
#
# Reuses Sanad's Python environment if this folder has no .venv of its own,
# so nothing big needs to be downloaded again.
param(
    [switch]$Mock,
    [string]$Model = "",
    [string]$Python = ""
)
Set-Location $PSScriptRoot

$candidates = @(
    $Python,
    ".\.venv\Scripts\python.exe",
    "$env:USERPROFILE\Desktop\nola-kids-ai\kids-ai\.venv\Scripts\python.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if (-not $candidates) {
    Write-Host "No Python environment found. Run setup.ps1 first:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\setup.ps1"
    exit 1
}
$py = @($candidates)[0]
Write-Host "Using Python: $py"

& $py -c "import flask" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Flask (one time) ..."
    & $py -m pip install "flask>=3.0"
}

if ($Mock) { $env:MOCK = "1" } else { $env:MOCK = "0" }
if ($Model) { $env:MODEL_ID = $Model } else { Remove-Item Env:MODEL_ID -ErrorAction SilentlyContinue }

Write-Host "Open http://127.0.0.1:5000 once you see 'Running on'."
& $py app.py
