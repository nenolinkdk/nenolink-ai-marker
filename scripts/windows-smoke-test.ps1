param(
    [Parameter(Mandatory = $true)] [string]$ExePath,
    [int]$TimeoutSeconds = 15,
    [string]$WorkingDirectory = [System.IO.Path]::GetTempPath()
)

$ErrorActionPreference = "Stop"
$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$processName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedExe)
$existingIds = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$process = Start-Process -FilePath $resolvedExe -WorkingDirectory $WorkingDirectory -PassThru
$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$windowFound = $false
$launchedProcesses = @()
try {
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $launchedProcesses = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })
        if ($launchedProcesses.Count -eq 0 -and $process.HasExited) {
            throw "Executable exited during startup with code $($process.ExitCode)."
        }
        if ($launchedProcesses | Where-Object { $_.MainWindowHandle -ne 0 }) { $windowFound = $true; break }
    }
    if (-not $windowFound) { throw "No application window appeared within $TimeoutSeconds seconds." }
    Write-Host "Smoke test passed from working directory '$WorkingDirectory': application window launched successfully."
}
finally {
    $launchedProcesses = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })
    foreach ($launchedProcess in $launchedProcesses) {
        if ($launchedProcess.MainWindowHandle -ne 0) { $null = $launchedProcess.CloseMainWindow() }
    }
    Start-Sleep -Milliseconds 500
    foreach ($launchedProcess in @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })) {
        Stop-Process -Id $launchedProcess.Id -Force
    }
}
