# Run the Pencil Production Line HMI (Windows PowerShell)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Activate venv
$VenvActivate = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $VenvActivate)) {
    Write-Error ".venv not found. Run: python -m venv .venv; .venv\Scripts\Activate; pip install -r requirements.txt"
    exit 1
}
& $VenvActivate

# Check .env
if (-not (Test-Path ".env")) {
    Write-Error ".env not found. Copy .env.example to .env and fill in your credentials."
    exit 1
}

$Port = if ($env:APP_PORT) { $env:APP_PORT } else { "8000" }
Write-Host "Starting Pencil Production Line HMI on http://localhost:$Port"
uvicorn backend.main:app --host 0.0.0.0 --port $Port --reload
