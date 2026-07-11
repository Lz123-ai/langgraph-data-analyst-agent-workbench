param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$AccessToken = ""
)

$ErrorActionPreference = "Stop"
$headers = @{}
if ($AccessToken) {
    $headers["Authorization"] = "Bearer $AccessToken"
}

$status = Invoke-RestMethod -Uri "$BaseUrl/api/ops/model-status" -Headers $headers -TimeoutSec 15
if (-not $status.enabled) {
    throw "LLM is disabled. Configure an ignored .env file with USE_LLM=true before running this verification."
}
if (-not $status.api_key_configured -and $status.provider -ne "ollama") {
    throw "No provider API key is configured. Do not pass a key on the command line; place it only in .env or your secret store."
}

$result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/ops/model-smoke-test" -Headers $headers -TimeoutSec 60
if (-not $result.ok) {
    throw "Model smoke test did not return an ok result."
}
Write-Host "LLM smoke test passed: $($result.provider) / $($result.model)"
