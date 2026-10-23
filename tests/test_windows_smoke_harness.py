"""Focused Windows smoke-gate behavior and wiring checks."""

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PS_TEST = ROOT / "tests" / "windows_smoke_harness_checks.ps1"
MODULE = ROOT / "scripts" / "windows-smoke-harness.psm1"
SMOKE = ROOT / "scripts" / "windows-smoke-test.ps1"


def test_windows_smoke_harness_decisions_and_artifact_lifecycle():
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        pytest.skip("PowerShell is required to execute the Windows smoke harness checks")

    module_path = str(MODULE).replace("'", "''")
    test_path = str(PS_TEST).replace("'", "''")
    command = (
        f"$moduleText=[IO.File]::ReadAllText('{module_path}'); "
        "$moduleText=[regex]::Replace($moduleText,'(?m)^Export-ModuleMember.*$',''); "
        ". ([scriptblock]::Create($moduleText)); "
        f"$testText=[IO.File]::ReadAllText('{test_path}'); "
        "& ([scriptblock]::Create($testText))"
    )
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "Smoke harness helper checks passed" in result.stdout


def test_smoke_script_uses_process_owned_window_gate_and_keeps_both_build_modes():
    smoke = SMOKE.read_text(encoding="utf-8")
    build = (ROOT / "build.ps1").read_text(encoding="utf-8")

    assert "NENOLINK_VERIFY_REPORT" not in smoke
    assert "Nenolink AI Marker*" not in smoke
    assert "NENOLINK_BOOT_LOG" in smoke
    assert "Get-SmokeVisibleTopLevelWindows" in smoke
    assert "Select-SmokeOwnedProcesses" in smoke
    assert "Get-SmokeChildProcessFilter" in smoke
    assert "-Filter $filter" in smoke
    assert "Get-CimInstance -ClassName Win32_Process -ErrorAction Stop |" not in smoke
    assert "interactive_session = $interactiveSession" in smoke
    assert "root_process_session_id = $rootSessionId" in smoke
    assert "diagnostics.json" in smoke
    assert "-EmbeddedResources" in build
    assert "-ExePath $packagedExe" in build

    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        pytest.skip("PowerShell parser is required for the smoke script syntax check")
    paths = [SMOKE, MODULE, PS_TEST]
    parse_lines = []
    for path in paths:
        quoted = str(path).replace("'", "''")
        parse_lines.append(
            "$tokens=$null;$errors=$null;"
            f"[System.Management.Automation.Language.Parser]::ParseFile('{quoted}',[ref]$tokens,[ref]$errors)|Out-Null;"
            "if($errors.Count){$errors|ForEach-Object{Write-Error $_};exit 1}"
        )
    parsed = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-Command", ";".join(parse_lines)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert parsed.returncode == 0, f"PowerShell parse failed:\n{parsed.stdout}\n{parsed.stderr}"
