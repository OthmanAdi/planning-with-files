# Inject the selected plan as initial session context using Cursor's sessionStart schema.
if ($env:PLANNING_DISABLED -eq '1') {
    Write-Output '{}'
    exit 0
}

try {
    $context = & (Join-Path $PSScriptRoot 'user-prompt-submit.ps1') | Out-String
    if ([string]::IsNullOrWhiteSpace($context)) {
        Write-Output '{}'
        exit 0
    }

    $response = @{ additional_context = $context.TrimEnd() }
    Write-Output ($response | ConvertTo-Json -Compress)
} catch {
    Write-Output '{}'
}
