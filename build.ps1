param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildVenv = Join-Path $projectRoot ".venv-build"
$sourcePython = (Resolve-Path -LiteralPath $PythonPath).Path
Set-Location -LiteralPath $projectRoot
$env:PIP_CACHE_DIR = Join-Path $projectRoot ".pip-cache"

Write-Host "Checking source Python and tkinter..."
& $sourcePython -c "import sys, tkinter; print(sys.version); print(tkinter.TkVersion)"
if ($LASTEXITCODE -ne 0) { throw "The selected Python does not provide a working tkinter runtime." }

if (-not (Test-Path -LiteralPath $buildVenv)) {
    & $sourcePython -m venv --copies --system-site-packages $buildVenv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the build environment." }
}

$python = @(
    (Join-Path $buildVenv "Scripts\python.exe"),
    (Join-Path $buildVenv "bin\python.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) { throw "The build environment has no Python executable." }

$tkInfo = & $python -c "import sys, tkinter; from pathlib import Path; t=tkinter.Tcl(); lib=Path(t.eval('info library')); print(sys.version.split()[0]); print(tkinter.TkVersion); print(lib); print(lib.parent / f'tk{tkinter.TkVersion}')"
if ($LASTEXITCODE -ne 0 -or $tkInfo.Count -lt 4) { throw "tkinter failed inside the build environment." }
$env:NENOLINK_TCL_LIBRARY = $tkInfo[2]
$env:NENOLINK_TK_LIBRARY = $tkInfo[3]
$env:NENOLINK_PYTHON_BIN = Split-Path -Parent $sourcePython
Write-Host "Python: $($tkInfo[0])"
Write-Host "Tkinter/Tk: $($tkInfo[1])"
Write-Host "Tcl library: $env:NENOLINK_TCL_LIBRARY"
Write-Host "Tk library: $env:NENOLINK_TK_LIBRARY"

& $python -m pip install -r (Join-Path $projectRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing build dependencies failed." }
& $python -m PyInstaller --version

foreach ($name in @("build", "dist")) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $name))
    if (-not $target.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe clean target: $target"
    }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}

& $python -m PyInstaller --noconfirm --clean (Join-Path $projectRoot "Nenolink-AI-Marker.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$packageRoot = Join-Path $projectRoot "dist\Nenolink-AI-Marker"
$packagedExe = Join-Path $packageRoot "Nenolink-AI-Marker.exe"
$distBadges = Join-Path $packageRoot "assets\badges"
$distUi = Join-Path $packageRoot "assets\ui"
$distLocales = Join-Path $packageRoot "locales"
$distDocs = Join-Path $packageRoot "docs"
New-Item -ItemType Directory -Force -Path $distBadges | Out-Null
New-Item -ItemType Directory -Force -Path $distUi | Out-Null
New-Item -ItemType Directory -Force -Path $distLocales | Out-Null
New-Item -ItemType Directory -Force -Path $distDocs | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "dist\Nenolink-AI-Marker.exe") -Destination $packagedExe -Force
Copy-Item -Path (Join-Path $projectRoot "assets\badges\*") -Destination $distBadges -Force
Copy-Item -Path (Join-Path $projectRoot "assets\ui\*") -Destination $distUi -Force
Copy-Item -Path (Join-Path $projectRoot "locales\*.json") -Destination $distLocales -Force
Copy-Item -Path (Join-Path $projectRoot "docs\*") -Destination $distDocs -Force

$verifiedRuntimeRoot = Split-Path -Parent $env:NENOLINK_TCL_LIBRARY
& (Join-Path $projectRoot "scripts\windows-smoke-test.ps1") -ExePath $packagedExe -RuntimeRoot $verifiedRuntimeRoot
if ($LASTEXITCODE -ne 0) { throw "The executable smoke test failed." }
& (Join-Path $projectRoot "scripts\windows-smoke-test.ps1") -ExePath (Join-Path $projectRoot "dist\Nenolink-AI-Marker.exe") -RuntimeRoot $verifiedRuntimeRoot -EmbeddedResources
if ($LASTEXITCODE -ne 0) { throw "The standalone executable embedded-resource smoke test failed." }

Write-Host "Built and launched successfully: $packagedExe"
