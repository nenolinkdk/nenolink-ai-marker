Set-StrictMode -Version Latest

function ConvertTo-SmokeFullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
}

function Get-SmokeChildProcessFilter {
    param([Parameter(Mandatory = $true)][ValidateRange(1, 2147483647)][int]$ParentProcessId)
    return "ParentProcessId = $ParentProcessId"
}

function Select-SmokeOwnedProcesses {
    param(
        [Parameter(Mandatory = $true)][int]$RootProcessId,
        [Parameter(Mandatory = $true)][string]$ExecutablePath,
        [Parameter(Mandatory = $true)][datetime]$RootStartTime,
        [Parameter(Mandatory = $true)][object[]]$ProcessRows
    )

    $expectedPath = ConvertTo-SmokeFullPath $ExecutablePath
    $parentIds = [System.Collections.Generic.HashSet[int]]::new()
    $null = $parentIds.Add($RootProcessId)
    $owned = [System.Collections.Generic.Dictionary[int, object]]::new()
    $changed = $true

    while ($changed) {
        $changed = $false
        foreach ($row in $ProcessRows) {
            $id = [int]$row.ProcessId
            if ($owned.ContainsKey($id)) { continue }
            if ($id -ne $RootProcessId -and -not $parentIds.Contains([int]$row.ParentProcessId)) { continue }
            if (-not $row.ExecutablePath) { continue }
            try { $rowPath = ConvertTo-SmokeFullPath ([string]$row.ExecutablePath) }
            catch { continue }
            if (-not [string]::Equals($rowPath, $expectedPath, [System.StringComparison]::OrdinalIgnoreCase)) { continue }

            $created = [datetime]$row.CreationDate
            if ($created -lt $RootStartTime.AddSeconds(-2)) { continue }
            $record = [pscustomobject]@{
                ProcessId = $id
                ParentProcessId = [int]$row.ParentProcessId
                ExecutablePath = $rowPath
                CreationDate = $created
            }
            $owned[$id] = $record
            $null = $parentIds.Add($id)
            $changed = $true
        }
    }

    return @($owned.Values | Sort-Object ProcessId)
}

function Get-SmokeStartupDecision {
    param(
        [bool]$ProcessStartFailed = $false,
        [bool]$ProcessTreeProbeFailed = $false,
        [bool]$RootProcessExited = $false,
        [object[]]$OwnedProcesses = @(),
        [object[]]$Windows = @(),
        [bool]$TimedOut = $false
    )

    if ($ProcessStartFailed) {
        return [pscustomobject]@{ Status = 'process-start-failed'; Window = $null }
    }

    $ownedIds = @($OwnedProcesses | ForEach-Object { [int]$_.ProcessId })
    $window = $Windows | Where-Object {
        [long]$_.Handle -ne 0 -and
        $_.Visible -and
        $_.TopLevel -and
        $ownedIds -contains [int]$_.ProcessId
    } | Select-Object -First 1
    if ($window) {
        return [pscustomobject]@{ Status = 'visible-window-detected'; Window = $window }
    }

    if ($ProcessTreeProbeFailed) {
        if ($TimedOut) { return [pscustomobject]@{ Status = 'timeout-no-visible-window'; Window = $null } }
        return [pscustomobject]@{ Status = 'process-tree-probe-failed'; Window = $null }
    }
    if ($RootProcessExited -and $ownedIds.Count -eq 0) {
        return [pscustomobject]@{ Status = 'process-exited-before-gui'; Window = $null }
    }
    if ($TimedOut) {
        return [pscustomobject]@{ Status = 'timeout-no-visible-window'; Window = $null }
    }
    return [pscustomobject]@{ Status = 'process-alive-without-visible-window'; Window = $null }
}

function Get-SmokeVisibleTopLevelWindows {
    param([Parameter(Mandatory = $true)][int[]]$ProcessIds)

    if (-not ('NenolinkSmoke.NativeWindowProbe' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

namespace NenolinkSmoke {
    public sealed class WindowReceipt {
        public long Handle { get; set; }
        public int ProcessId { get; set; }
        public bool Visible { get; set; }
        public bool TopLevel { get; set; }
        public string Title { get; set; }
    }

    public static class NativeWindowProbe {
        private delegate bool EnumWindowsCallback(IntPtr hwnd, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr lParam);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
        [DllImport("user32.dll")] private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowTextLengthW(IntPtr hwnd);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowTextW(IntPtr hwnd, StringBuilder text, int maxCount);

        public static WindowReceipt[] FindVisibleTopLevelWindows(int[] processIds) {
            var wanted = new HashSet<int>(processIds ?? Array.Empty<int>());
            var results = new List<WindowReceipt>();
            EnumWindows((hwnd, unused) => {
                uint ownerPid;
                GetWindowThreadProcessId(hwnd, out ownerPid);
                if (!wanted.Contains((int)ownerPid) || !IsWindowVisible(hwnd)) return true;
                bool topLevel = GetAncestor(hwnd, 2) == hwnd; // GA_ROOT
                int length = GetWindowTextLengthW(hwnd);
                var title = new StringBuilder(Math.Max(length + 1, 2));
                GetWindowTextW(hwnd, title, title.Capacity);
                results.Add(new WindowReceipt {
                    Handle = hwnd.ToInt64(), ProcessId = (int)ownerPid,
                    Visible = true, TopLevel = topLevel, Title = title.ToString()
                });
                return true;
            }, IntPtr.Zero);
            return results.ToArray();
        }
    }
}
'@ -ErrorAction Stop
    }

    return @([NenolinkSmoke.NativeWindowProbe]::FindVisibleTopLevelWindows($ProcessIds))
}

function Complete-SmokeArtifacts {
    param(
        [Parameter(Mandatory = $true)][string]$BootLogPath,
        [Parameter(Mandatory = $true)][string]$DiagnosticReportPath,
        [Parameter(Mandatory = $true)][bool]$Succeeded
    )

    if ($Succeeded) {
        foreach ($path in @($BootLogPath, $DiagnosticReportPath)) {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
        }
        return [pscustomobject]@{ Retained = $false; BootLogPath = $null; DiagnosticReportPath = $null }
    }

    return [pscustomobject]@{
        Retained = $true
        BootLogPath = if (Test-Path -LiteralPath $BootLogPath) { $BootLogPath } else { $null }
        DiagnosticReportPath = if (Test-Path -LiteralPath $DiagnosticReportPath) { $DiagnosticReportPath } else { $null }
    }
}

Export-ModuleMember -Function ConvertTo-SmokeFullPath, Get-SmokeChildProcessFilter, Select-SmokeOwnedProcesses, Get-SmokeStartupDecision, Get-SmokeVisibleTopLevelWindows, Complete-SmokeArtifacts
