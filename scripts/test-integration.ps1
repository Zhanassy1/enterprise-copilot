# Local integration run: Postgres test container (docker-compose profile `test`, host port 5434).
# CI uses GitHub Actions service Postgres on :5433 — same DATABASE_URL shape, different port.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

Set-Location $Root
docker compose --profile test up -d db_test

try {
    $containerId = (docker compose --profile test ps -q db_test).Trim()
    if (-not $containerId) {
        throw "db_test container was not created (docker compose --profile test up -d db_test)"
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
    # docker-compose.yml maps db_test to host:5434 (dev db uses 5433)
    $env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/enterprise_copilot_test"
    $env:RUN_INTEGRATION_TESTS = "1"

    py -3 -m alembic upgrade head
    py -3 -m unittest discover -s tests -v
    if ($env:RUN_ASYNC_PIPELINE_SMOKE -eq "1") {
        $env:INGESTION_ASYNC_ENABLED = "1"
        $env:CELERY_TASK_ALWAYS_EAGER = "1"
        $env:CELERY_TASK_EAGER_PROPAGATES = "1"
        py -3 -m unittest tests.test_ingestion_async_pipeline -v
    }
}
finally {
    Set-Location $Root
    docker compose --profile test stop db_test 2>$null
}
