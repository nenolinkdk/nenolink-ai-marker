$ErrorActionPreference = 'Stop'
if (-not (Get-Command Select-SmokeOwnedProcesses -ErrorAction SilentlyContinue)) {
    throw 'The harness module must be loaded before these checks run.'
}

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) { throw "$Message; expected '$Expected', got '$Actual'." }
}

$exe = Join-Path $env:TEMP 'NenolinkSmokeHarnessTest\Nenolink-AI-Marker-1.0.3.exe'
$nativeSnapshot = @(Get-SmokeProcessSnapshot)
if (-not ($nativeSnapshot | Where-Object { $_.ProcessId -eq $PID })) { throw 'Native process snapshot omitted the current PowerShell PID.' }

$now = [datetime]::Now
$rows = @(
    [pscustomobject]@{ ProcessId = 101; ParentProcessId = 10; ExecutablePath = $exe; CreationDate = $now },
    [pscustomobject]@{ ProcessId = 102; ParentProcessId = 101; ExecutablePath = $exe; CreationDate = $now.AddMilliseconds(200) },
    [pscustomobject]@{ ProcessId = 103; ParentProcessId = 101; ExecutablePath = (Join-Path $env:TEMP 'other\Nenolink-AI-Marker-1.0.3.exe'); CreationDate = $now.AddMilliseconds(250) },
    [pscustomobject]@{ ProcessId = 201; ParentProcessId = 20; ExecutablePath = $exe; CreationDate = $now.AddMilliseconds(300) }
)
$owned = @(Select-SmokeOwnedProcesses -RootProcessId 101 -ExecutablePath $exe -RootStartTime $now -ProcessRows $rows)
Assert-Equal (($owned.ProcessId | Sort-Object) -join ',') '101,102' 'Process identity/tree filtering failed'

$visible = [pscustomobject]@{ Handle = 9001L; ProcessId = 102; Visible = $true; TopLevel = $true; Title = 'Nenolink AI-marker' }
$success = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @($visible)
Assert-Equal $success.Status 'visible-window-detected' 'A visible owned window with the expected product title must pass'
Assert-Equal $success.Window.Title 'Nenolink AI-marker' 'The exact product title should be retained'

$wrongTitle = [pscustomobject]@{ Handle = 9006L; ProcessId = 102; Visible = $true; TopLevel = $true; Title = 'CTk' }
$wrongTitleDecision = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @($wrongTitle)
Assert-Equal $wrongTitleDecision.Status 'window-title-mismatch' 'A wrong visible app title must not pass'
Assert-Equal $wrongTitleDecision.Window.Title 'CTk' 'Wrong title should be retained for diagnostics'
$blankTitle = [pscustomobject]@{ Handle = 9007L; ProcessId = 102; Visible = $true; TopLevel = $true; Title = '' }
$blankTitleDecision = Get-SmokeStartupDecision -OwnedProcesses $owned -Windows @($blankTitle)
Assert-Equal $blankTitleDecision.Status 'window-title-mismatch' 'A blank visible app title must not pass'

$startFailed = Get-SmokeStartupDecision -ProcessStartFailed $true
Assert-Equal $startFailed.Status 'process-start-failed' 'Start failure classification failed'

$earlyExit = Get-SmokeStartupDecision -RootProcessExited $true -OwnedProcesses @() -Windows @()
Assert-Equal $earlyExit.Status 'process-exited-before-gui' 'Early exit classification failed'
$probeFailure = Get-SmokeStartupDecision -ProcessTreeProbeFailed $true -RootProcessExited $true -OwnedProcesses @() -Windows @()
Assert-Equal $probeFailure.Status 'process-tree-probe-failed' 'A process query error must not be misreported as an early app exit'
$rootReceipt = [pscustomobject]@{ ProcessId = 101 }
$rootWindow = [pscustomobject]@{ Handle = 9005L; ProcessId = 101; Visible = $true; TopLevel = $true; Title = 'Nenolink AI-marker' }
$verifiedRootWindow = Get-SmokeStartupDecision -ProcessTreeProbeFailed $true -OwnedProcesses @($rootReceipt) -Windows @($rootWindow)
Assert-Equal $verifiedRootWindow.Status 'visible-window-detected' 'An actual visible window owned by the exact launched PID may pass despite child-enumeration errors'
$accessDeniedWithoutWindow = Get-SmokeStartupDecision -ProcessTreeProbeFailed $true -OwnedProcesses @($rootReceipt) -Windows @()
Assert-Equal $accessDeniedWithoutWindow.Status 'process-tree-probe-failed' 'Access denied without an owned visible window must remain a failure'

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

Write-Output 'Smoke harness helper checks passed: native process snapshot, direct/child window ownership, process-probe failure, early exit, timeout, unrelated/invisible windows, process ownership and artifact retention.'
