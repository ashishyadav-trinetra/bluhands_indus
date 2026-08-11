$Url = "http://122.160.253.37:8000/v1/chat/completions"
$Headers = @{
    "Authorization" = "Bearer Himanshu@126"
    "Content-Type" = "application/json"
}
$Body = @{
    model = "qwen3.6-35b-a3b"
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
