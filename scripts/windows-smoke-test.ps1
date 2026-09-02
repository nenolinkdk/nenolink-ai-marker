param(
    [Parameter(Mandatory = $true)] [string]$ExePath,
    [int]$TimeoutSeconds = 45,
    [string]$WorkingDirectory = [System.IO.Path]::GetTempPath(),
    [string]$RuntimeRoot = "",
    [switch]$EmbeddedResources
)

$ErrorActionPreference = "Stop"
$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$installRoot = Split-Path -Parent $resolvedExe
$badgeFiles = @(Get-ChildItem -Path (Join-Path $installRoot "assets\badges") -File -Filter "*.png" -ErrorAction SilentlyContinue)
$localeFiles = @(Get-ChildItem -Path (Join-Path $installRoot "locales") -File -Filter "*.json" -ErrorAction SilentlyContinue)
if (-not $EmbeddedResources) {
    if ($badgeFiles.Count -ne 10) { throw "Packaged badge folder must contain exactly 10 PNG files; found $($badgeFiles.Count)." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "assets\badges\badges.json"))) { throw "Packaged badge metadata is missing." }
    if ($localeFiles.Count -lt 12) { throw "Packaged locale folder contains only $($localeFiles.Count) JSON files." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "docs\Nenolink-AI-Marker-User-Guide-EN.pdf"))) { throw "Packaged PDF guide is missing." }
}
$processName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedExe)
$existingIds = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$previousRuntimeRoot = $env:NENOLINK_RUNTIME_ROOT
$previousVerifyReport = $env:NENOLINK_VERIFY_REPORT
$env:NENOLINK_RUNTIME_ROOT = if ($RuntimeRoot) { $RuntimeRoot } else { Join-Path $WorkingDirectory "Nenolink-AI-Marker-Smoke-Runtime" }
$verifyReport = Join-Path $WorkingDirectory "Nenolink-AI-Marker-Smoke-$([Guid]::NewGuid().ToString('N')).json"
$env:NENOLINK_VERIFY_REPORT = $verifyReport
$process = Start-Process -FilePath $resolvedExe -WorkingDirectory $WorkingDirectory -PassThru
$env:NENOLINK_RUNTIME_ROOT = $previousRuntimeRoot
$env:NENOLINK_VERIFY_REPORT = $previousVerifyReport
$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$windowFound = $false
$launchedProcesses = @()
try {
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $launchedProcesses = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })
        if (Test-Path -LiteralPath $verifyReport) {
            $report = Get-Content -LiteralPath $verifyReport -Raw | ConvertFrom-Json
            if ($report.translation_keys_visible -or $report.badges_found -lt 1) { throw "Packaged GUI verification report failed." }
            $windowFound = $true
            break
        }
        if ($launchedProcesses.Count -eq 0 -and $process.HasExited) {
            throw "Executable exited during startup with code $($process.ExitCode)."
        }
        if ($launchedProcesses | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "Nenolink AI Marker*" }) { $windowFound = $true; break }
    }
    if (-not $windowFound) { throw "No application window appeared within $TimeoutSeconds seconds." }
    $resourceMode = if ($EmbeddedResources) { "embedded resources" } else { "$($badgeFiles.Count) external badges and $($localeFiles.Count) locales" }
    Write-Host "Smoke test passed from '$WorkingDirectory': window launched with $resourceMode."
}
finally {
    if (Test-Path -LiteralPath $verifyReport) { Remove-Item -LiteralPath $verifyReport -Force }
    $launchedProcesses = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })
    foreach ($launchedProcess in $launchedProcesses) {
        if ($launchedProcess.MainWindowHandle -ne 0) { $null = $launchedProcess.CloseMainWindow() }
    }
    Start-Sleep -Milliseconds 500
    foreach ($launchedProcess in @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })) {
        Stop-Process -Id $launchedProcess.Id -Force
    }
}
