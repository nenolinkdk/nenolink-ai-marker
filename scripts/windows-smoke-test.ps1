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
    if ($badgeFiles.Count -ne 11) { throw "Packaged badge folder must contain exactly 11 PNG files; found $($badgeFiles.Count)." }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot "assets\badges\no-ai.png"))) { throw "Packaged No AI badge is missing." }
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
if ($RuntimeRoot) { $env:NENOLINK_RUNTIME_ROOT = $RuntimeRoot }
else { Remove-Item Env:NENOLINK_RUNTIME_ROOT -ErrorAction SilentlyContinue }
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
            foreach ($tab in @("single", "batch", "badges", "inspect")) {
                if (-not $report.tab_switching.$tab.selected -or -not $report.tab_switching.$tab.visible -or $report.tab_switching.$tab.other_visible) { throw "Packaged tab switching failed for $tab." }
            }
            if (-not $report.back_navigation.badges_preserved -or -not $report.back_navigation.batch_preserved -or $report.back_navigation.english_label -ne "← Back" -or $report.back_navigation.danish_label -ne "← Tilbage") { throw "Packaged Back navigation changed application state." }
            $expectedFooter = "© Copyright Henrik Nielsen - nenolink.com · v$($report.version) ·"
            if ($report.version -ne "1.0.1" -or $report.packaged_ui_evidence.footer_text -ne $expectedFooter -or -not $report.packaged_ui_evidence.footer_visible -or -not $report.packaged_ui_evidence.footer_update_visible -or -not $report.packaged_ui_evidence.footer_update_action -or $report.packaged_ui_evidence.footer_update_cursor -ne "hand2" -or $report.packaged_ui_evidence.footer_update_text -eq "update.check") { throw "Packaged footer/version/manual-update verification failed." }
            if ($report.packaged_ui_evidence.badges_update_button_present) { throw "Obsolete large Badges-tab update button is still present." }
            if (-not $report.packaged_ui_evidence.shortcut_visible -or $report.packaged_ui_evidence.shortcut_text -eq "shortcut.create" -or -not $report.packaged_ui_evidence.shortcut_callable -or $report.packaged_ui_evidence.shortcut_module -ne "nenolink_ai_marker.shortcut") { throw "Packaged desktop-shortcut UI/module verification failed." }
            $offer=$report.packaged_ui_evidence.first_run_offer
            if (-not $offer.visible -or -not $offer.persisted -or $offer.title -eq "shortcut.offer_title" -or $offer.message -eq "shortcut.offer_message" -or $offer.create -eq "shortcut.offer_create" -or $offer.not_now -eq "shortcut.offer_not_now") { throw "Packaged first-run desktop-shortcut offer verification failed." }
            if (-not $report.packaged_ui_evidence.update_notification_present -or $report.packaged_ui_evidence.update_notification_cursor -ne "hand2" -or -not $report.packaged_ui_evidence.approved_update_handler) { throw "Packaged update-notification functionality is missing." }
            if (-not $report.ffmpeg_found) { throw "Packaged application could not discover bundled FFmpeg." }
            if ($report.layout_verification) {
                foreach ($size in @("1280x720", "1366x768", "1920x1080")) { if (-not $report.layout_verification.sizes.$size.process_reachable) { throw "Single File action is inaccessible at $size." } }
                foreach ($language in @("English", "Dansk", "Deutsch", "Français")) { $check=$report.layout_verification.languages.$language; if (-not $check.process_visible -or -not $check.video_mode_visible -or -not $check.duration_visible) { throw "Video controls are inaccessible in $language." } }
                if (-not $report.layout_verification.permanent_hides_duration) { throw "Permanent mode did not hide Duration." }
            }
            if ($report.reset_verification.source -ne "standard" -or $report.reset_verification.selection -ne "ai-assisted.png" -or $report.reset_verification.video_mode -ne "permanent" -or $report.reset_verification.video_duration -ne 5 -or $report.reset_verification.batch_suffix -ne "_ai" -or -not $report.reset_verification.folder_retained -or $report.reset_verification.sources -ne 0 -or -not $report.reset_verification.scan_cleared -or -not $report.reset_verification.inspection_cleared -or -not $report.reset_verification.single_selected -or -not $report.reset_verification.welcome -or -not $report.reset_verification.welcome_mapped -or -not $report.reset_verification.welcome_illustration -or -not $report.reset_verification.preview_hidden) { throw "Packaged reset verification failed." }
            if ($report.translation_keys_visible -or -not $report.welcome_before_image -or -not $report.welcome_illustration -or $report.badges_found -ne 11 -or -not $report.badge_selector_visible -or $report.gallery_badges -ne 11 -or -not $report.gallery_selection_persisted -or -not $report.badges_tab_is_distinct -or -not $report.friendly_status -or $report.guide_filename -ne "Nenolink-AI-Marker-User-Guide-DA.pdf" -or $report.guide_paths.fr -ne "Nenolink-AI-Marker-User-Guide-EN.pdf" -or $report.danish.welcome_title -ne "Velkommen til Nenolink AI Marker" -or $report.german.welcome_title -ne "Willkommen bei Nenolink AI Marker") { throw "Packaged GUI verification report failed." }
            $noAi=$report.no_ai_verification
            if (-not $noAi.packaged_badge -or -not $noAi.written -or -not $noAi.inspected -or -not $noAi.source_unchanged -or -not $noAi.visible_overlay -or $noAi.label -ne "No AI" -or $noAi.version -ne "1.0.1") { throw "Packaged No AI metadata round-trip verification failed." }
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
