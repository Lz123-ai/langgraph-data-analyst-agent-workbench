$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an Administrator PowerShell. Windows returned elevation error 740 in the current session."
}

Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -All -NoRestart | Out-Null
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart | Out-Null

winget install --id Microsoft.WSL -e `
    --silent `
    --accept-package-agreements `
    --accept-source-agreements `
    --disable-interactivity
if ($LASTEXITCODE -ne 0) {
    throw "Microsoft.WSL installation failed with exit code $LASTEXITCODE."
}

winget install --id Docker.DockerDesktop -e `
    --silent `
    --accept-package-agreements `
    --accept-source-agreements `
    --disable-interactivity
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop installation failed with exit code $LASTEXITCODE."
}

Write-Host "Docker Desktop prerequisites are installed. Restart Windows, launch Docker Desktop once, then run scripts\verify-docker.ps1."
