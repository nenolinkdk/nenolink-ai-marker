$ErrorActionPreference = 'Stop'
if (-not (Get-Command Select-SmokeOwnedProcesses -ErrorAction SilentlyContinue)) {
    throw 'The harness module must be loaded before these checks run.'
}

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) { throw "$Message; expected '$Expected', got '$Actual'." }
}

$exe = Join-Path $env:TEMP 'NenolinkSmokeHarnessTest\Nenolink-AI-Marker-1.0.3.exe'
$now = [datetime]::Now
$rows = @(
    [pscustomobject]@{ ProcessId = 101; ParentProcessId = 10; ExecutablePath = $exe; CreationDate = $now },
    [pscustomobject]@{ ProcessId = 102; ParentProcessId = 101; ExecutablePath = $exe; CreationDate = $now.AddMilliseconds(200) },
    [pscustomobject]@{ ProcessId = 103; ParentProcessId = 101; ExecutablePath = (Join-Path $env:TEMP 'other\Nenolink-AI-Marker-1.0.3.exe'); CreationDate = $now.AddMilliseconds(250) },
    [pscustomobject]@{ ProcessId = 201; ParentProcessId = 20; ExecutablePath = $exe; CreationDate = $now.AddMilliseconds(300) }
)
$owned = @(Select-SmokeOwnedProcesses -RootProcessId 101 -ExecutablePath $exe -RootStartTime $now -ProcessRows $rows)
Assert-Equal (($owned.ProcessId | Sort-Object) -join ',') '101,102' 'Process identity/tree filtering failed'

$visible = [pscustomobject]@{ Handle = 9001L; ProcessId = 102; Visible = $true; TopLevel = $true; Title = 'CTk' }
$success = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @($visible)
Assert-Equal $success.Status 'visible-window-detected' 'A visible owned window with a non-product title must pass'
Assert-Equal $success.Window.Title 'CTk' 'Window title should be retained as diagnostic data'

$startFailed = Get-SmokeStartupDecision -ProcessStartFailed $true
Assert-Equal $startFailed.Status 'process-start-failed' 'Start failure classification failed'

$earlyExit = Get-SmokeStartupDecision -RootProcessExited $true -OwnedProcesses @() -Windows @()
Assert-Equal $earlyExit.Status 'process-exited-before-gui' 'Early exit classification failed'
$probeFailure = Get-SmokeStartupDecision -ProcessTreeProbeFailed $true -RootProcessExited $true -OwnedProcesses @() -Windows @()
Assert-Equal $probeFailure.Status 'process-tree-probe-failed' 'A process query error must not be misreported as an early app exit'

$timeout = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @() -TimedOut $true
Assert-Equal $timeout.Status 'timeout-no-visible-window' 'Alive-process timeout classification failed'

$unrelated = [pscustomobject]@{ Handle = 9002L; ProcessId = 201; Visible = $true; TopLevel = $true; Title = 'Nenolink AI Marker' }
$unrelatedOnly = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @($unrelated) -TimedOut $true
Assert-Equal $unrelatedOnly.Status 'timeout-no-visible-window' 'An unrelated process window must not satisfy the gate'

$invisible = [pscustomobject]@{ Handle = 9003L; ProcessId = 102; Visible = $false; TopLevel = $true; Title = 'Hidden' }
$notTopLevel = [pscustomobject]@{ Handle = 9004L; ProcessId = 102; Visible = $true; TopLevel = $false; Title = 'Child' }
$invalidWindowOnly = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @($invisible, $notTopLevel) -TimedOut $true
Assert-Equal $invalidWindowOnly.Status 'timeout-no-visible-window' 'Invisible/child windows must not satisfy the gate'

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("NenolinkSmokeRetention-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    $boot = Join-Path $tempRoot 'boot.log'
    $report = Join-Path $tempRoot 'diagnostics.json'
    Set-Content -LiteralPath $boot -Value 'failure boot receipt'
    Set-Content -LiteralPath $report -Value 'failure diagnostic receipt'
    $retained = Complete-SmokeArtifacts -BootLogPath $boot -DiagnosticReportPath $report -Succeeded $false
    Assert-Equal $retained.Retained $true 'Failure artifacts must be retained'
    Assert-Equal (Test-Path -LiteralPath $boot) $true 'Failure boot log disappeared'
    Assert-Equal (Test-Path -LiteralPath $report) $true 'Failure report disappeared'
    $cleaned = Complete-SmokeArtifacts -BootLogPath $boot -DiagnosticReportPath $report -Succeeded $true
    Assert-Equal $cleaned.Retained $false 'Success artifacts should be marked cleaned'
    Assert-Equal (Test-Path -LiteralPath $boot) $false 'Successful boot log was not cleaned'
    Assert-Equal (Test-Path -LiteralPath $report) $false 'Successful report was not cleaned'
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output 'Smoke harness helper checks passed: success, early exit, timeout, unrelated/invisible windows, process ownership and artifact retention.'
