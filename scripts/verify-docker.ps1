$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ComposeFile = Join-Path $Root "docker-compose.yml"

function Assert-NativeSuccess([string]$Action) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE."
    }
}

docker version
Assert-NativeSuccess "docker version"
docker compose -f $ComposeFile config --quiet
Assert-NativeSuccess "docker compose config"
docker compose -f $ComposeFile build
Assert-NativeSuccess "docker compose build"
docker compose -f $ComposeFile up -d
Assert-NativeSuccess "docker compose up"

try {
    $deadline = (Get-Date).AddMinutes(2)
    do {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3
        } catch {
            $health = $null
            Start-Sleep -Seconds 2
        }
    } while (-not $health -and (Get-Date) -lt $deadline)

    if (-not $health -or $health.status -ne "ok") {
        throw "Docker backend health check did not become ready."
    }
    $frontend = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8080/" -TimeoutSec 5
    if ($frontend.StatusCode -ne 200) {
        throw "Docker frontend returned HTTP $($frontend.StatusCode)."
    }
    Write-Host "Docker images built and Compose smoke test passed."
} finally {
    docker compose -f $ComposeFile down
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "docker compose down failed with exit code $LASTEXITCODE."
    }
}
