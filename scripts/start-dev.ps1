param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$RunDir = Join-Path $Root ".run"
$LogDir = Join-Path $Root "logs"
$Python = Join-Path $Root ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $RunDir, $LogDir | Out-Null

function Get-PortOwner {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Listen" } |
        Select-Object -First 1
    if ($connection) {
        return $connection.OwningProcess
    }
    return $null
}

function Wait-Port {
    param(
        [int]$Port,
        [int]$Seconds = 30
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Get-PortOwner -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

if ($Install) {
    if (-not (Test-Path -LiteralPath $Python)) {
        python -m venv (Join-Path $Root ".venv")
    }
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found. Run: powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -Install"
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "node_modules"))) {
    throw "frontend\node_modules not found. Run: powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -Install"
}

$backendPid = Get-PortOwner -Port 8000
if ($backendPid) {
    Write-Host "Backend already running on http://127.0.0.1:8000 (PID $backendPid)"
} else {
    $backendOut = Join-Path $LogDir "backend-server.out.log"
    $backendErr = Join-Path $LogDir "backend-server.err.log"
    $backend = Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload") `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Encoding ascii -Path (Join-Path $RunDir "backend.pid") -Value $backend.Id
    if (-not (Wait-Port -Port 8000 -Seconds 30)) {
        throw "Backend did not start within 30 seconds. Check $backendErr"
    }
    Write-Host "Backend started on http://127.0.0.1:8000 (PID $($backend.Id))"
}

$frontendPid = Get-PortOwner -Port 5173
if ($frontendPid) {
    Write-Host "Frontend already running on http://127.0.0.1:5173 (PID $frontendPid)"
} else {
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $frontendOut = Join-Path $LogDir "frontend-server.out.log"
    $frontendErr = Join-Path $LogDir "frontend-server.err.log"
    $frontend = Start-Process `
        -FilePath $npm `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Encoding ascii -Path (Join-Path $RunDir "frontend.pid") -Value $frontend.Id
    if (-not (Wait-Port -Port 5173 -Seconds 30)) {
        throw "Frontend did not start within 30 seconds. Check $frontendErr"
    }
    Write-Host "Frontend started on http://127.0.0.1:5173 (PID $($frontend.Id))"
}

Write-Host ""
Write-Host "Open: http://127.0.0.1:5173/"
Write-Host "Health: http://127.0.0.1:8000/api/health"
Write-Host "Stop: powershell -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1"
