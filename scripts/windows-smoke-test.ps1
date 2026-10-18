param(
    [Parameter(Mandatory = $true)] [string]$ExePath,
    [int]$TimeoutSeconds = 45,
    [string]$WorkingDirectory = [System.IO.Path]::GetTempPath(),
    [string]$RuntimeRoot = "",
    [switch]$EmbeddedResources
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "windows-smoke-harness.psm1") -Force

function Get-SmokeProcessRows {
    return @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop |
        Select-Object ProcessId, ParentProcessId, ExecutablePath, CreationDate)
}

function Test-SmokeProcessIdentity {
    param([System.Diagnostics.Process]$Process, [string]$ExpectedPath, [datetime]$NotBefore)
    try {
        $Process.Refresh()
        if ($Process.HasExited -or -not $Process.Path) { return $false }
        $actualPath = ConvertTo-SmokeFullPath $Process.Path
        $expected = ConvertTo-SmokeFullPath $ExpectedPath
        return [string]::Equals($actualPath, $expected, [System.StringComparison]::OrdinalIgnoreCase) -and
            $Process.StartTime -ge $NotBefore.AddSeconds(-2)
    } catch { return $false }
}

function Stop-SmokeLaunchedProcesses {
    param(
        [System.Diagnostics.Process]$RootProcess,
        [string]$ExpectedPath,
        [datetime]$RootStartTime,
        [System.Collections.IDictionary]$ObservedProcesses
    )

    if (-not $RootProcess) { return }
    $rootId = [int]$RootProcess.Id
    $records = @($ObservedProcesses.Values)
    try {
        $rows = Get-SmokeProcessRows
        $records += Select-SmokeOwnedProcesses -RootProcessId $rootId -ExecutablePath $ExpectedPath -RootStartTime $RootStartTime -ProcessRows $rows
    } catch { }

    $targets = @{}
    foreach ($record in $records) { $targets[[int]$record.ProcessId] = $record }
    $targets[$rootId] = [pscustomobject]@{ ProcessId = $rootId; ExecutablePath = $ExpectedPath; CreationDate = $RootStartTime }

    foreach ($id in @($targets.Keys)) {
        try {
            $candidate = Get-Process -Id ([int]$id) -ErrorAction Stop
            if (Test-SmokeProcessIdentity -Process $candidate -ExpectedPath $ExpectedPath -NotBefore $RootStartTime) {
                $null = $candidate.CloseMainWindow()
            }
        } catch { }
    }
    Start-Sleep -Milliseconds 500

    foreach ($id in @($targets.Keys)) {
        try {
            $candidate = Get-Process -Id ([int]$id) -ErrorAction Stop
            if (Test-SmokeProcessIdentity -Process $candidate -ExpectedPath $ExpectedPath -NotBefore $RootStartTime) {
                Stop-Process -Id ([int]$id) -Force -ErrorAction Stop
            }
        } catch { }
    }
}

$resolvedExe = (Resolve-Path -LiteralPath $ExePath -ErrorAction Stop).Path
$installRoot = Split-Path -Parent $resolvedExe
$processName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedExe)
$runId = [Guid]::NewGuid().ToString("N")
$bootLog = Join-Path $WorkingDirectory "Nenolink-AI-Marker-Smoke-$runId.boot.log"
$diagnosticReport = Join-Path $WorkingDirectory "Nenolink-AI-Marker-Smoke-$runId.diagnostics.json"
$previousRuntimeRoot = [Environment]::GetEnvironmentVariable("NENOLINK_RUNTIME_ROOT", "Process")
$previousBootLog = [Environment]::GetEnvironmentVariable("NENOLINK_BOOT_LOG", "Process")
$rootProcess = $null
$rootStartTime = [datetime]::Now
$observedProcesses = @{}
$lastObservation = $null
$history = [System.Collections.Generic.List[object]]::new()
$succeeded = $false
$failureStatus = "not-started"
$failureMessage = $null

try {
    if (-not $EmbeddedResources) {
        $badgeFiles = @(Get-ChildItem -Path (Join-Path $installRoot "assets\badges") -File -Filter "*.png" -ErrorAction SilentlyContinue)
        $localeFiles = @(Get-ChildItem -Path (Join-Path $installRoot "locales") -File -Filter "*.json" -ErrorAction SilentlyContinue)
        if ($badgeFiles.Count -ne 11) { throw "Package resource check failed: expected 11 badge PNGs, found $($badgeFiles.Count)." }
        foreach ($relative in @(
            "assets\badges\no-ai.png", "assets\badges\badges.json",
            "assets\ui\welcome-europe.png", "docs\Nenolink-AI-Marker-User-Guide-EN.pdf",
            "docs\Nenolink-AI-Marker-User-Guide-DA.pdf", "tools\ffmpeg\ffmpeg.exe",
            "THIRD_PARTY_NOTICES\FFMPEG.md"
        )) {
            if (-not (Test-Path -LiteralPath (Join-Path $installRoot $relative))) { throw "Package resource check failed: missing $relative." }
        }
        if ($localeFiles.Count -lt 12) { throw "Package resource check failed: expected at least 12 locale files, found $($localeFiles.Count)." }
    }

    if ($RuntimeRoot) { $env:NENOLINK_RUNTIME_ROOT = $RuntimeRoot }
    else { Remove-Item Env:NENOLINK_RUNTIME_ROOT -ErrorAction SilentlyContinue }
    $env:NENOLINK_BOOT_LOG = $bootLog

    try {
        $rootProcess = Start-Process -FilePath $resolvedExe -WorkingDirectory $WorkingDirectory -PassThru -ErrorAction Stop
        try { $rootStartTime = $rootProcess.StartTime } catch { $rootStartTime = [datetime]::Now }
    } catch {
        $failureStatus = "process-start-failed"
        throw "Could not start '$resolvedExe': $($_.Exception.Message)"
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $rootExitObservedAt = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        $processProbeError = $null
        $windowProbeError = $null
        $owned = @()
        $windows = @()
        try {
            $rows = Get-SmokeProcessRows
            $owned = @(Select-SmokeOwnedProcesses -RootProcessId $rootProcess.Id -ExecutablePath $resolvedExe -RootStartTime $rootStartTime -ProcessRows $rows)
            foreach ($record in $owned) { $observedProcesses[[int]$record.ProcessId] = $record }
        } catch { $processProbeError = $_.Exception.Message }

        if ($owned.Count -gt 0) {
            try { $windows = @(Get-SmokeVisibleTopLevelWindows -ProcessIds ([int[]]@($owned | ForEach-Object { [int]$_.ProcessId }))) }
            catch { $windowProbeError = $_.Exception.Message }
        }

        $rootProcess.Refresh()
        $rootExited = $rootProcess.HasExited
        $exitCode = $null
        if ($rootExited) {
            try { $exitCode = $rootProcess.ExitCode } catch { }
        }
        $decision = Get-SmokeStartupDecision -ProcessTreeProbeFailed ($null -ne $processProbeError) -RootProcessExited $rootExited -OwnedProcesses $owned -Windows $windows
        $now = [DateTime]::UtcNow
        if ($decision.Status -eq "process-exited-before-gui") {
            if (-not $rootExitObservedAt) { $rootExitObservedAt = $now }
            if (($now - $rootExitObservedAt).TotalSeconds -lt 2) { $decision = [pscustomobject]@{ Status = "process-alive-without-visible-window"; Window = $null } }
        } else { $rootExitObservedAt = $null }

        $lastObservation = [pscustomobject]@{
            observed_at_utc = $now.ToString("o")
            status = $decision.Status
            root_process_id = [int]$rootProcess.Id
            root_process_exited = $rootExited
            root_exit_code = $exitCode
            owned_processes = @($owned | ForEach-Object { [pscustomobject]@{ pid = $_.ProcessId; ppid = $_.ParentProcessId; executable = $_.ExecutablePath } })
            visible_windows = @($windows | ForEach-Object { [pscustomobject]@{ handle = $_.Handle; pid = $_.ProcessId; title = $_.Title; visible = $_.Visible; top_level = $_.TopLevel } })
            process_probe_error = $processProbeError
            window_probe_error = $windowProbeError
        }
        if ($history.Count -eq 0 -or ($now - [datetime]$history[$history.Count - 1].observed_at_utc).TotalSeconds -ge 1) {
            $history.Add($lastObservation)
            if ($history.Count -gt 25) { $history.RemoveAt(0) }
        }

        if ($decision.Status -eq "visible-window-detected") {
            $failureStatus = "visible-window-detected"
            $succeeded = $true
            Write-Host "Smoke test passed: visible top-level window owned by PID $($decision.Window.ProcessId), handle $($decision.Window.Handle), title '$($decision.Window.Title)'."
            break
        }
        if ($decision.Status -eq "process-exited-before-gui") {
            $failureStatus = $decision.Status
            throw "Process $($rootProcess.Id) exited before a visible GUI window appeared (exit code $exitCode)."
        }
        Start-Sleep -Milliseconds 400
    }

    if (-not $succeeded) {
        $failureStatus = "timeout-no-visible-window"
        throw "No visible top-level window owned by the launched executable was detected within $TimeoutSeconds seconds."
    }
} catch {
    $failureMessage = $_.Exception.Message
    if ($failureStatus -eq "not-started") { $failureStatus = "preflight-failed" }
    $report = [ordered]@{
        outcome = "failure"
        status = $failureStatus
        executable = $resolvedExe
        process_name = $processName
        timeout_seconds = $TimeoutSeconds
        root_process_id = if ($rootProcess) { [int]$rootProcess.Id } else { $null }
        root_start_time = $rootStartTime.ToString("o")
        failure = $failureMessage
        last_observation = $lastObservation
        observation_history = @($history.ToArray())
        boot_log_path = $bootLog
        diagnostic_report_path = $diagnosticReport
    }
    [System.IO.File]::WriteAllText($diagnosticReport, ($report | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
    throw "Windows smoke test $failureStatus`: $failureMessage`nDiagnostics preserved: $diagnosticReport`nBoot log (if emitted): $bootLog"
} finally {
    if ($null -eq $previousRuntimeRoot) { Remove-Item Env:NENOLINK_RUNTIME_ROOT -ErrorAction SilentlyContinue }
    else { $env:NENOLINK_RUNTIME_ROOT = $previousRuntimeRoot }
    if ($null -eq $previousBootLog) { Remove-Item Env:NENOLINK_BOOT_LOG -ErrorAction SilentlyContinue }
    else { $env:NENOLINK_BOOT_LOG = $previousBootLog }

    if ($rootProcess) {
        Stop-SmokeLaunchedProcesses -RootProcess $rootProcess -ExpectedPath $resolvedExe -RootStartTime $rootStartTime -ObservedProcesses $observedProcesses
    }
    $artifactResult = Complete-SmokeArtifacts -BootLogPath $bootLog -DiagnosticReportPath $diagnosticReport -Succeeded $succeeded
    if (-not $succeeded) {
        Write-Host "Smoke failure artifacts retained. Diagnostics: $($artifactResult.DiagnosticReportPath); boot log: $($artifactResult.BootLogPath)"
    }
}
