$ErrorActionPreference = "Stop"

if (-Not (Test-Path ".venv")) {
  Write-Host "[setup] Creating venv (.venv)..."
  python -m venv .venv
}

Write-Host "[setup] Installing editable package..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .

Write-Host "[setup] Done."
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  pm migrate"