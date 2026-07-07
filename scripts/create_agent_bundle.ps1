param(
    [string]$ExtraDatasetZip = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutDir = Join-Path $Root "agent_handoff"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Stage = Join-Path $OutDir "langgraph-agent-workbench-handoff-$Stamp"
$ZipPath = Join-Path $OutDir "langgraph-agent-workbench-handoff-$Stamp.zip"

New-Item -ItemType Directory -Force -Path $Stage | Out-Null

function Copy-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $Source = Join-Path $Root $RelativePath
    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    $Destination = Join-Path $Stage $RelativePath
    $DestinationParent = Split-Path -Parent $Destination
    if ($DestinationParent) {
        New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

@(
    ".gitignore",
    ".dockerignore",
    ".env.example",
    "README.md",
    "AGENT_HANDOFF.md",
    "Makefile",
    "docker-compose.yml",
    "start-dev.bat",
    "stop-dev.bat",
    "requirements.txt",
    "pytest.ini",
    "backend/app",
    "backend/Dockerfile",
    "backend/pyproject.toml",
    "backend/data/uploads/.gitkeep",
    "frontend/src",
    "frontend/Dockerfile",
    "frontend/nginx.conf",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "samples",
    "docs",
    "agent_eval/README.md",
    "agent_eval/cases.json",
    "agent_eval/run_batch_eval.py",
    "agent_eval/enterprise_business_eval.py",
    "agent_eval/fixtures",
    "scripts/create_agent_bundle.ps1",
    "scripts/start-dev.ps1",
    "scripts/stop-dev.ps1"
) | ForEach-Object { Copy-ProjectPath $_ }

if ($ExtraDatasetZip) {
    $ResolvedDatasetZip = (Resolve-Path -LiteralPath $ExtraDatasetZip).Path
    $ExternalDataDir = Join-Path $Stage "external_eval_data"
    New-Item -ItemType Directory -Force -Path $ExternalDataDir | Out-Null
    Copy-Item -LiteralPath $ResolvedDatasetZip -Destination $ExternalDataDir -Force
}

$TopLevelItems = Get-ChildItem -LiteralPath $Stage | Select-Object -ExpandProperty FullName
Compress-Archive -LiteralPath $TopLevelItems -DestinationPath $ZipPath -Force

Write-Host "Created bundle:"
Write-Host $ZipPath
