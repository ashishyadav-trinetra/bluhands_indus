# Reads credentials from the environment so no key is committed.
# Set them first, e.g.  $env:BLUHANDS_SELFHOSTED_API_KEY = "<key>"
$BaseUrl = $env:BLUHANDS_SELFHOSTED_BASE_URL
if (-not $BaseUrl) { $BaseUrl = "http://122.160.253.37:8000/v1" }
$ApiKey = $env:BLUHANDS_SELFHOSTED_API_KEY
if (-not $ApiKey) {
    Write-Host "BLUHANDS_SELFHOSTED_API_KEY is not set. Set it and re-run:"
    Write-Host '  $env:BLUHANDS_SELFHOSTED_API_KEY = "<key>"'
    exit 1
}
$Model = $env:BLUHANDS_SELFHOSTED_MODEL
if (-not $Model) { $Model = "qwen3.6-35b-a3b" }
$Model = $Model.Split("/")[-1]

$Url = "$($BaseUrl.TrimEnd('/'))/chat/completions"
$Headers = @{
    "Authorization" = "Bearer $ApiKey"
    "Content-Type" = "application/json"
}
$Body = @{
    model = $Model
    messages = @(
        @{ role = "user"; content = "Write a comprehensive 500 word essay about artificial intelligence." }
    )
    stream = $false
    max_tokens = 512
} | ConvertTo-Json

Write-Host "Starting benchmark on $Url..."
$StartTime = Get-Date
try {
    $Response = Invoke-RestMethod -Uri $Url -Method Post -Headers $Headers -Body $Body -ErrorAction Stop
    $EndTime = Get-Date

    $Duration = ($EndTime - $StartTime).TotalSeconds
    $Tokens = $Response.usage.completion_tokens

    if ($Tokens -gt 0) {
        $Tps = $Tokens / $Duration
        Write-Host ""
        Write-Host "--- Benchmark Results ---"
        Write-Host "Total Time: $Duration seconds"
        Write-Host "Tokens Generated: $Tokens"
        Write-Host "TPS: $($Tps.ToString('0.00')) tokens/sec"
        Write-Host "-------------------------"
    } else {
        Write-Host "Error: No tokens were generated."
    }
} catch {
    Write-Host "API Request Failed!"
    Write-Host $_.Exception.Message
}
