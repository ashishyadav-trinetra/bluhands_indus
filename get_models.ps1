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

$Url = "$($BaseUrl.TrimEnd('/'))/models"
$Headers = @{
    "Authorization" = "Bearer $ApiKey"
}
try {
    $Response = Invoke-RestMethod -Uri $Url -Method Get -Headers $Headers -ErrorAction Stop
    Write-Host "Available Models:"
    $Response.data | ForEach-Object { Write-Host "- $($_.id)" }
} catch {
    Write-Host "Failed!"
    Write-Host $_.Exception.Message
}
