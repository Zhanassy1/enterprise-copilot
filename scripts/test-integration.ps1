$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = "C:\venvs\ec314\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Python venv not found at $Python"
    exit 1
}

Set-Location $Root
docker compose --profile test up -d db_test redis

try {
    $containerId = (docker compose --profile test ps -q db_test).Trim()
    if (-not $containerId) {
        throw "db_test container was not created"
    }

    $maxRetries = 30
    for ($i = 0; $i -lt $maxRetries; $i++) {
        $health = (docker inspect --format "{{.State.Health.Status}}" $containerId).Trim()
        if ($health -eq "healthy") {
            break
        }
        Start-Sleep -Seconds 2
        if ($i -eq ($maxRetries - 1)) {
            throw "db_test did not become healthy in time"
        }
    }

    Set-Location $Backend
    $env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/enterprise_copilot_test"
    $env:RUN_INTEGRATION_TESTS = "1"

    & $Python -m alembic upgrade head
    & $Python -m unittest tests.test_api_integration -v
    if ($env:RUN_ASYNC_PIPELINE_SMOKE -eq "1") {
        $env:INGESTION_ASYNC_ENABLED = "1"
        $env:CELERY_TASK_ALWAYS_EAGER = "1"
        $env:CELERY_TASK_EAGER_PROPAGATES = "1"
        & $Python -m unittest tests.test_ingestion_async_pipeline -v
    }
}
finally {
    Set-Location $Root
    docker compose --profile test stop db_test redis | Out-Null
    docker compose --profile test rm -fsv db_test redis | Out-Null
}
