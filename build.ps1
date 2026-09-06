param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildVenv = Join-Path $projectRoot ".venv-release"
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

$tkInfo = & $python -c "import sys, tkinter; from pathlib import Path; root=Path(sys.base_prefix); print(sys.version.split()[0]); print(tkinter.TkVersion); print(root / 'tcl' / 'tcl8.6'); print(root / 'tcl' / 'tk8.6')"
if ($LASTEXITCODE -ne 0 -or $tkInfo.Count -lt 4) { throw "tkinter failed inside the build environment." }
$env:NENOLINK_TCL_LIBRARY = $tkInfo[2]
$env:NENOLINK_TK_LIBRARY = $tkInfo[3]
$env:NENOLINK_PYTHON_BIN = Split-Path -Parent $sourcePython
$version = (& $python -c "from nenolink_ai_marker import __version__; print(__version__)").Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid application version: $version" }
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

& $python (Join-Path $projectRoot "scripts\run-pyinstaller.py") --noconfirm --clean (Join-Path $projectRoot "Nenolink-AI-Marker.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$releaseName = "Nenolink-AI-Marker-$version"
$packageRoot = Join-Path $projectRoot "dist\$releaseName"
$packagedExe = Join-Path $packageRoot "$releaseName.exe"
$distBadges = Join-Path $packageRoot "assets\badges"
$distUi = Join-Path $packageRoot "assets\ui"
$distLocales = Join-Path $packageRoot "locales"
$distDocs = Join-Path $packageRoot "docs"
$distFfmpeg = Join-Path $packageRoot "tools\ffmpeg"
$distNotices = Join-Path $packageRoot "THIRD_PARTY_NOTICES"
New-Item -ItemType Directory -Force -Path $distBadges | Out-Null
New-Item -ItemType Directory -Force -Path $distUi | Out-Null
New-Item -ItemType Directory -Force -Path $distLocales | Out-Null
New-Item -ItemType Directory -Force -Path $distDocs | Out-Null
New-Item -ItemType Directory -Force -Path $distFfmpeg | Out-Null
New-Item -ItemType Directory -Force -Path $distNotices | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "dist\$releaseName.exe") -Destination $packagedExe -Force
Copy-Item -Path (Join-Path $projectRoot "assets\badges\*") -Destination $distBadges -Force
Copy-Item -Path (Join-Path $projectRoot "assets\ui\*") -Destination $distUi -Force
Copy-Item -Path (Join-Path $projectRoot "locales\*.json") -Destination $distLocales -Force
Copy-Item -Path (Join-Path $projectRoot "docs\*.pdf") -Destination $distDocs -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "tools\ffmpeg\ffmpeg.exe") -Destination (Join-Path $distFfmpeg "ffmpeg.exe") -Force
Copy-Item -Path (Join-Path $projectRoot "THIRD_PARTY_NOTICES\*") -Destination $distNotices -Force

# Preserve the authoritative license files supplied by the exact runtime
# components selected above. Fail the release build if any expected notice
# cannot be located instead of silently producing an incomplete package.
$pythonLicense = & $python -c "import pathlib, sys; candidates=(pathlib.Path(sys.base_prefix)/'LICENSE.txt', pathlib.Path(sys.prefix)/'LICENSE.txt'); print(next((p for p in candidates if p.is_file()), candidates[0]))"
if (-not (Test-Path -LiteralPath $pythonLicense)) { throw "CPython license file was not found: $pythonLicense" }
Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $distNotices "PYTHON-LICENSE.txt") -Force

$tkLicense = Get-ChildItem -LiteralPath $env:NENOLINK_TK_LIBRARY -Filter "license.terms" -File -Recurse | Select-Object -First 1
if (-not $tkLicense) { throw "Tcl/Tk license terms were not found under $env:NENOLINK_TK_LIBRARY" }
Copy-Item -LiteralPath $tkLicense.FullName -Destination (Join-Path $distNotices "TCL-TK-LICENSE.txt") -Force

$licenseFiles = @(
    @{ Distribution = "customtkinter"; Name = "LICENSE"; Destination = "CUSTOMTKINTER-LICENSE.txt" },
    @{ Distribution = "Pillow"; Name = "LICENSE"; Destination = "PILLOW-LICENSE.txt" },
    @{ Distribution = "darkdetect"; Name = "LICENSE"; Destination = "DARKDETECT-LICENSE.txt" },
    @{ Distribution = "packaging"; Name = "LICENSE"; Destination = "PACKAGING-LICENSE.txt" },
    @{ Distribution = "packaging"; Name = "LICENSE.APACHE"; Destination = "PACKAGING-APACHE-2.0.txt" },
    @{ Distribution = "packaging"; Name = "LICENSE.BSD"; Destination = "PACKAGING-BSD.txt" }
)
foreach ($item in $licenseFiles) {
    $licensePath = & $python -c "import importlib.metadata as m; d=m.distribution('$($item.Distribution)'); print(next(d.locate_file(p) for p in d.files if p.name == '$($item.Name)'))"
    if (-not (Test-Path -LiteralPath $licensePath)) { throw "License file was not found for $($item.Distribution): $licensePath" }
    Copy-Item -LiteralPath $licensePath -Destination (Join-Path $distNotices $item.Destination) -Force
}

& (Join-Path $projectRoot "scripts\windows-smoke-test.ps1") -ExePath $packagedExe
if ($LASTEXITCODE -ne 0) { throw "The executable smoke test failed." }
& (Join-Path $projectRoot "scripts\windows-smoke-test.ps1") -ExePath (Join-Path $projectRoot "dist\$releaseName.exe") -EmbeddedResources
if ($LASTEXITCODE -ne 0) { throw "The standalone executable embedded-resource smoke test failed." }

$zipPath = Join-Path $projectRoot "dist\$releaseName-Windows.zip"
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal -Force
Write-Host "Built and launched successfully: $packagedExe"
Write-Host "Release ZIP: $zipPath"
