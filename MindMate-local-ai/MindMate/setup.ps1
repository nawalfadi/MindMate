# MindMate - one-time setup on a new PC (Windows PowerShell)
# Not needed if Sanad is already installed on this PC - run.ps1 reuses its environment.
# Run:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (.venv) ..."
    try { py -3.12 -m venv .venv } catch { }
    if (-not (Test-Path ".\.venv\Scripts\python.exe")) { python -m venv .venv }
}

$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip

Write-Host "Installing PyTorch with CUDA 13.0 (supports RTX 50-series) ..."
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cu130

Write-Host "Installing requirements ..."
& $py -m pip install -r requirements.txt

& $py -c "import torch; ok=torch.cuda.is_available(); print('CUDA available:', ok); print('GPU:', torch.cuda.get_device_name(0) if ok else 'NONE - update your NVIDIA driver')"
Write-Host ""
Write-Host "Done. Next:  powershell -ExecutionPolicy Bypass -File .\run.ps1"
