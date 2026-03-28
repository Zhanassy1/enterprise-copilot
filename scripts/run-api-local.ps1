# Запуск API без Docker: избегает баг Windows launcher у `uvicorn.exe` при не-ASCII пути в профиле.
# Использование: powershell -ExecutionPolicy Bypass -File .\scripts\run-api-local.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
Set-Location $Backend
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
Write-Host "Starting API from $Backend using: $py -m uvicorn ..."
Write-Host "Docs: http://127.0.0.1:8000/docs"
& $py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
