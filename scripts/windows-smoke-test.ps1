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
    param(
        [int]$RootProcessId,
        [string]$ExecutablePath,
        [datetime]$RootStartTime,
        [bool]$RootProcessAlive
    )

    # The root PID and image path are known from Start-Process. Seed that
    # identity directly. The native Toolhelp snapshot provides parent IDs
    # without querying protected process details through system-wide CIM.
    $rows = [System.Collections.Generic.List[object]]::new()
    $errors = [System.Collections.Generic.List[string]]::new()
    $expectedPath = ConvertTo-SmokeFullPath $ExecutablePath
    if ($RootProcessAlive) {
        $rows.Add([pscustomobject]@{
            ProcessId = $RootProcessId
            ParentProcessId = 0
            ExecutablePath = $expectedPath
            CreationDate = $RootStartTime
        })
    }

    # Discover only descendants linked to this launch. Inspect path/start time
    # only for same-name candidates, and accept those only when all checks pass.
    try { $snapshot = @(Get-SmokeProcessSnapshot) }
    catch {
        $errors.Add("Native process snapshot failed: $($_.Exception.Message)")
        return [pscustomobject]@{ Rows = @($rows.ToArray()); Errors = @($errors.ToArray()) }
    }
    $expectedName = [System.IO.Path]::GetFileName($expectedPath)
    $pendingParents = [System.Collections.Generic.Queue[int]]::new()
    $pendingParents.Enqueue($RootProcessId)
    $visitedParents = [System.Collections.Generic.HashSet[int]]::new()
    $visitedParents.Add($RootProcessId) | Out-Null
    while ($pendingParents.Count -gt 0) {
        $parentId = $pendingParents.Dequeue()
        foreach ($child in $snapshot | Where-Object { [int]$_.ParentProcessId -eq $parentId }) {
            $childId = [int]$child.ProcessId
            if (-not [string]::Equals([string]$child.ExecutableName, $expectedName, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            try {
                $candidate = Get-Process -Id $childId -ErrorAction Stop
                $candidate.Refresh()
                if ($candidate.HasExited) { continue }
                $childPath = ConvertTo-SmokeFullPath ([string]$candidate.Path)
                $created = $candidate.StartTime
            } catch {
                $errors.Add("Could not validate candidate child PID ${childId}: $($_.Exception.Message)")
                continue
            }
            if (-not [string]::Equals($childPath, $expectedPath, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            if ($created -lt $RootStartTime.AddSeconds(-2)) { continue }
            $rows.Add([pscustomobject]@{
                ProcessId = $childId
                ParentProcessId = $parentId
                ExecutablePath = $childPath
                CreationDate = $created
            })
            if ($visitedParents.Add($childId)) { $pendingParents.Enqueue($childId) }
        }
    }

    return [pscustomobject]@{ Rows = @($rows.ToArray()); Errors = @($errors.ToArray()) }
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
        $RootProcess.Refresh()
        $probe = Get-SmokeProcessRows -RootProcessId $rootId -ExecutablePath $ExpectedPath -RootStartTime $RootStartTime -RootProcessAlive (-not $RootProcess.HasExited)
        $records += Select-SmokeOwnedProcesses -RootProcessId $rootId -ExecutablePath $ExpectedPath -RootStartTime $RootStartTime -ProcessRows $probe.Rows
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
$smokeSession = Get-Process -Id $PID
$smokeSessionId = [int]$smokeSession.SessionId
$interactiveSession = [bool][Environment]::UserInteractive
$rootProcess = $null
$rootSessionId = $null
$rootStartTime = [datetime]::Now
$launchTimeUtc = $null
$windowDetectedAtUtc = $null
$startupSeconds = $null
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
        $launchTimeUtc = [DateTime]::UtcNow
        $rootProcess = Start-Process -FilePath $resolvedExe -WorkingDirectory $WorkingDirectory -PassThru -ErrorAction Stop
        try { $rootStartTime = $rootProcess.StartTime } catch { $rootStartTime = [datetime]::Now }
        try { $rootSessionId = [int]$rootProcess.SessionId } catch { }
    } catch {
        $failureStatus = "process-start-failed"
        throw "Could not start '$resolvedExe': $($_.Exception.Message)"
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $rootExitObservedAt = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        $rootProcess.Refresh()
        $rootExited = $rootProcess.HasExited
        $exitCode = $null
        if ($rootExited) {
            try { $exitCode = $rootProcess.ExitCode } catch { }
        }
        $processProbeError = $null
        $windowProbeError = $null
        $owned = @()
        $windows = @()
        $decision = $null

        # First check the exact process handle returned by Start-Process.
        # Only if it has no qualifying window do we discover/verify children.
        if (-not $rootExited) {
            $rootRecord = [pscustomobject]@{
                ProcessId = [int]$rootProcess.Id
                ParentProcessId = 0
                ExecutablePath = ConvertTo-SmokeFullPath $resolvedExe
                CreationDate = $rootStartTime
            }
            $owned = @($rootRecord)
            try {
                $windows = @(Get-SmokeVisibleTopLevelWindows -ProcessIds ([int[]]@([int]$rootProcess.Id)))
                $decision = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows $windows
            } catch { $windowProbeError = $_.Exception.Message }
        }

        if (-not $decision -or $decision.Status -ne "visible-window-detected") {
            try {
                $rootProcess.Refresh()
                $probe = Get-SmokeProcessRows -RootProcessId $rootProcess.Id -ExecutablePath $resolvedExe -RootStartTime $rootStartTime -RootProcessAlive (-not $rootProcess.HasExited)
                $owned = @(Select-SmokeOwnedProcesses -RootProcessId $rootProcess.Id -ExecutablePath $resolvedExe -RootStartTime $rootStartTime -ProcessRows $probe.Rows)
                foreach ($record in $owned) { $observedProcesses[[int]$record.ProcessId] = $record }
                if ($probe.Errors.Count -gt 0) { $processProbeError = $probe.Errors -join '; ' }
            } catch { $processProbeError = $_.Exception.Message }

            if ($owned.Count -gt 0) {
                try { $windows = @(Get-SmokeVisibleTopLevelWindows -ProcessIds ([int[]]@($owned | ForEach-Object { [int]$_.ProcessId }))) }
                catch {
                    if ($windowProbeError) { $windowProbeError += "; $($_.Exception.Message)" }
                    else { $windowProbeError = $_.Exception.Message }
                }
            }

            $rootProcess.Refresh()
            $rootExited = $rootProcess.HasExited
            if ($rootExited) { try { $exitCode = $rootProcess.ExitCode } catch { } }
            $decision = Get-SmokeStartupDecision -ProcessTreeProbeFailed ($null -ne $processProbeError) -RootProcessExited $rootExited -OwnedProcesses $owned -Windows $windows
        }
        $now = [DateTime]::UtcNow
        if ($decision.Status -eq "process-exited-before-gui") {
            if (-not $rootExitObservedAt) { $rootExitObservedAt = $now }
            if (($now - $rootExitObservedAt).TotalSeconds -lt 2) { $decision = [pscustomobject]@{ Status = "process-alive-without-visible-window"; Window = $null } }
        } else { $rootExitObservedAt = $null }

        $lastObservation = [pscustomobject]@{
            observed_at_utc = $now.ToString("o")
            status = $decision.Status
            root_process_id = [int]$rootProcess.Id
            smoke_session_id = $smokeSessionId
            root_process_session_id = $rootSessionId
            interactive_session = $interactiveSession
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
            $windowDetectedAtUtc = [DateTime]::UtcNow
            $startupSeconds = [math]::Round(($windowDetectedAtUtc - $launchTimeUtc).TotalSeconds, 3)
            Write-Host "Smoke test passed: visible top-level window owned by PID $($decision.Window.ProcessId), handle $($decision.Window.Handle), title '$($decision.Window.Title)'."
            Write-Host "Smoke receipt: root_pid=$($rootProcess.Id); window_pid=$($decision.Window.ProcessId); handle=$($decision.Window.Handle); session=$rootSessionId; interactive=$interactiveSession; launch_utc=$($launchTimeUtc.ToString('o')); detected_utc=$($windowDetectedAtUtc.ToString('o')); startup_seconds=$startupSeconds."
            break
        }
        if ($decision.Status -eq "process-exited-before-gui") {
            $failureStatus = $decision.Status
            throw "Process $($rootProcess.Id) exited before a visible GUI window appeared (exit code $exitCode)."
        }
        Start-Sleep -Milliseconds 400
    }

    if (-not $succeeded) {
        if ($lastObservation -and $lastObservation.status -eq "process-tree-probe-failed") {
            $failureStatus = "process-tree-probe-failed"
            throw "Process-tree inspection failed; no verified visible window was detected. $($lastObservation.process_probe_error)"
        }
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
        smoke_session_id = $smokeSessionId
        root_process_session_id = $rootSessionId
        interactive_session = $interactiveSession
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
