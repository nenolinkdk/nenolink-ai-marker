param(
    [Parameter(Mandatory = $true)] [string]$ExePath,
    [Parameter(Mandatory = $true)] [string]$ReportPath,
    [Parameter(Mandatory = $true)] [string]$ImagePath,
    [Parameter(Mandatory = $true)] [string]$LogoPath,
    [Parameter(Mandatory = $true)] [string]$CustomBadgesPath,
    [Parameter(Mandatory = $true)] [string]$VideoPath,
    [Parameter(Mandatory = $true)] [string]$AppDataPath
)

$ErrorActionPreference = "Stop"
$resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$resolvedReport = [System.IO.Path]::GetFullPath($ReportPath)
New-Item -ItemType Directory -Force -Path $AppDataPath | Out-Null
Remove-Item -LiteralPath $resolvedReport -Force -ErrorAction SilentlyContinue

$env:NENOLINK_VERIFY_REPORT = $resolvedReport
$env:NENOLINK_VERIFY_IMAGE = (Resolve-Path -LiteralPath $ImagePath).Path
$env:NENOLINK_VERIFY_LOGO = (Resolve-Path -LiteralPath $LogoPath).Path
$env:NENOLINK_VERIFY_CUSTOM_BADGES = (Resolve-Path -LiteralPath $CustomBadgesPath).Path
$env:NENOLINK_VERIFY_VIDEO = (Resolve-Path -LiteralPath $VideoPath).Path
$env:NENOLINK_VERIFY_GUIDE_LANGUAGE = "da"
$env:NENOLINK_VERIFY_RESET_LANGUAGE = "da"
$env:APPDATA = [System.IO.Path]::GetFullPath($AppDataPath)
$env:PATH = "C:\Windows\System32"

$process = Start-Process -FilePath $resolvedExe -WorkingDirectory ([System.IO.Path]::GetTempPath()) -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(600000)) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "Packaged release verification timed out."
}
if ($process.ExitCode -ne 0) { throw "Packaged release verification exited with code $($process.ExitCode)." }
if (-not (Test-Path -LiteralPath $resolvedReport)) { throw "Packaged release verification report was not created." }

Write-Output $resolvedReport
