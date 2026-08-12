$Url = "http://122.160.253.37:8000/v1/models"
$Headers = @{
    "Authorization" = "Bearer Himanshu@126"
}
try {
    $Response = Invoke-RestMethod -Uri $Url -Method Get -Headers $Headers -ErrorAction Stop
    Write-Host "Available Models:"
    $Response.data | ForEach-Object { Write-Host "- $($_.id)" }
} catch {
    Write-Host "Failed!"
    Write-Host $_.Exception.Message
}
