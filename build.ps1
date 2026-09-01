param(
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath $python)) {
    if ($PythonPath) {
        $bootstrapPython = $PythonPath
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $bootstrapPython = "py"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $bootstrapPython = "python"
    } else {
        throw "Python 3 was not found. Install Python or pass -PythonPath C:\path\to\python.exe."
    }
    & $bootstrapPython -m venv (Join-Path $projectRoot ".venv")
}

& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $projectRoot "requirements-build.txt")
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "Nenolink-AI-Marker" `
    (Join-Path $projectRoot "main.py")

$distBadges = Join-Path $projectRoot "dist\assets\badges"
New-Item -ItemType Directory -Force -Path $distBadges | Out-Null
Copy-Item -Path (Join-Path $projectRoot "assets\badges\*") -Destination $distBadges -Force -ErrorAction SilentlyContinue

Write-Host "Built: $projectRoot\dist\Nenolink-AI-Marker.exe"
