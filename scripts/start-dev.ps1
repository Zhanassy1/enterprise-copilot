# Запуск окружения: Docker (db+redis), миграции, API на :8000
# Требуется: Docker Desktop (или уже запущенный engine), Python venv с зависимостями backend.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

$DockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $DockerExe) {
    try {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Start-Process $DockerExe; Start-Sleep -Seconds 15 }
    } catch { Start-Process $DockerExe; Start-Sleep -Seconds 15 }
}

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker не отвечает. Запусти Docker Desktop и выполни скрипт снова."
    exit 1
}

Set-Location $Root
docker compose up -d db redis
Start-Sleep -Seconds 8

$Py = if (Test-Path "C:\venvs\ec314\Scripts\python.exe") {
    "C:\venvs\ec314\Scripts\python.exe"
} elseif (Test-Path (Join-Path $Backend ".venv\Scripts\python.exe")) {
    Join-Path $Backend ".venv\Scripts\python.exe"
} else {
    Write-Host "Нет Python venv (ожидал C:\venvs\ec314 или backend\.venv). Создай venv и pip install -r backend\requirements.txt"
    exit 1
}

Set-Location $Backend
& $Py -m alembic upgrade head

$EnableAsyncIngestion = ($env:ENABLE_ASYNC_INGESTION -eq "1")
if ($EnableAsyncIngestion) {
    Write-Host "Async ingestion enabled: starting Celery worker in separate PowerShell window"
    $workerCmd = @"
Set-Location '$Backend'
`$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/enterprise_copilot'
`$env:REDIS_URL='redis://localhost:6379/0'
`$env:INGESTION_ASYNC_ENABLED='1'
& '$Py' -m celery -A app.celery_app.celery_app worker --loglevel=INFO --queues=ingestion
"@
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $workerCmd) | Out-Null
    $env:INGESTION_ASYNC_ENABLED = "1"
}

Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "API: http://127.0.0.1:8000  (Ctrl+C остановит)"
& $Py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
