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
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "assets\ui\welcome-europe.png"))) { throw "Packaged welcome illustration is missing." }
    if ($localeFiles.Count -lt 12) { throw "Packaged locale folder contains only $($localeFiles.Count) JSON files." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "docs\Nenolink-AI-Marker-User-Guide-EN.pdf"))) { throw "Packaged PDF guide is missing." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "docs\Nenolink-AI-Marker-User-Guide-DA.pdf"))) { throw "Packaged Danish PDF guide is missing." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "tools\ffmpeg\ffmpeg.exe"))) { throw "Packaged FFmpeg component is missing." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "THIRD_PARTY_NOTICES\FFMPEG.md"))) { throw "Packaged FFmpeg notice is missing." }
}
$processName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedExe)
$existingIds = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$previousRuntimeRoot = $env:NENOLINK_RUNTIME_ROOT
$previousVerifyReport = $env:NENOLINK_VERIFY_REPORT
$previousVerifyGuideLanguage = $env:NENOLINK_VERIFY_GUIDE_LANGUAGE
$env:NENOLINK_RUNTIME_ROOT = if ($RuntimeRoot) { $RuntimeRoot } else { Join-Path $WorkingDirectory "Nenolink-AI-Marker-Smoke-Runtime" }
$verifyReport = Join-Path $WorkingDirectory "Nenolink-AI-Marker-Smoke-$([Guid]::NewGuid().ToString('N')).json"
$env:NENOLINK_VERIFY_REPORT = $verifyReport
$env:NENOLINK_VERIFY_GUIDE_LANGUAGE = "da"
$process = Start-Process -FilePath $resolvedExe -WorkingDirectory $WorkingDirectory -PassThru
$env:NENOLINK_RUNTIME_ROOT = $previousRuntimeRoot
$env:NENOLINK_VERIFY_REPORT = $previousVerifyReport
$env:NENOLINK_VERIFY_GUIDE_LANGUAGE = $previousVerifyGuideLanguage
$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$windowFound = $false
$launchedProcesses = @()
try {
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $launchedProcesses = @(Get-Process -Name $processName -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $existingIds })
        if (Test-Path -LiteralPath $verifyReport) {
            $report = Get-Content -LiteralPath $verifyReport -Raw | ConvertFrom-Json
            foreach ($tab in @("single", "batch", "badges")) {
                if (-not $report.tab_switching.$tab.selected -or -not $report.tab_switching.$tab.visible -or $report.tab_switching.$tab.other_visible) { throw "Packaged tab switching failed for $tab." }
            }
            if (-not $report.back_navigation.badges_preserved -or -not $report.back_navigation.batch_preserved -or $report.back_navigation.english_label -ne "← Back" -or $report.back_navigation.danish_label -ne "← Tilbage") { throw "Packaged Back navigation changed application state." }
            if (-not $report.ffmpeg_found) { throw "Packaged application could not discover bundled FFmpeg." }
            if ($report.reset_verification.source -ne "standard" -or $report.reset_verification.selection -ne "ai-assisted.png" -or $report.reset_verification.video_mode -ne "permanent" -or $report.reset_verification.video_duration -ne 5 -or $report.reset_verification.batch_suffix -ne "_ai" -or -not $report.reset_verification.folder_retained -or $report.reset_verification.sources -ne 0 -or -not $report.reset_verification.scan_cleared -or -not $report.reset_verification.single_selected -or -not $report.reset_verification.welcome -or -not $report.reset_verification.welcome_mapped -or -not $report.reset_verification.welcome_illustration -or -not $report.reset_verification.preview_hidden) { throw "Packaged reset verification failed." }
            if ($report.translation_keys_visible -or -not $report.welcome_before_image -or -not $report.welcome_illustration -or $report.badges_found -ne 10 -or -not $report.badge_selector_visible -or $report.gallery_badges -ne 10 -or -not $report.gallery_selection_persisted -or -not $report.badges_tab_is_distinct -or -not $report.friendly_status -or $report.guide_filename -ne "Nenolink-AI-Marker-User-Guide-DA.pdf" -or $report.guide_paths.fr -ne "Nenolink-AI-Marker-User-Guide-EN.pdf" -or $report.danish.welcome_title -ne "Velkommen til Nenolink AI Marker" -or $report.german.welcome_title -ne "Willkommen bei Nenolink AI Marker") { throw "Packaged GUI verification report failed." }
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
        Stop-Process -Id $launchedProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
