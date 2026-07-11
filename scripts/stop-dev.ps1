param(
    [switch]$OnlyRecorded
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $Root ".run"

function Stop-ProcessTree {
    param([int]$ProcessId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId ([int]$child.ProcessId)
    }
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force
    }
}

function Stop-PidFile {
    param([string]$Name)
    $path = Join-Path $RunDir "$Name.pid"
    if (-not (Test-Path -LiteralPath $path)) {
        return
    }
    $pidText = (Get-Content -LiteralPath $path -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($pidText -match "^\d+$") {
        $process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-Host "Stopped $Name PID $($process.Id)"
        }
    }
    Remove-Item -LiteralPath $path -ErrorAction SilentlyContinue
}

function Stop-PortOwner {
    param([int]$Port)
    $owners = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Listen" } |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($owner in $owners) {
        $process = Get-Process -Id $owner -ErrorAction SilentlyContinue
        if ($process) {
            Stop-ProcessTree -ProcessId $process.Id
            Write-Host "Stopped process on port $Port PID $($process.Id)"
        }
    }
}

Stop-PidFile -Name "backend"
Stop-PidFile -Name "frontend"

if (-not $OnlyRecorded) {
    Stop-PortOwner -Port 8000
    Stop-PortOwner -Port 5173
}

Write-Host "Dev services stopped."
