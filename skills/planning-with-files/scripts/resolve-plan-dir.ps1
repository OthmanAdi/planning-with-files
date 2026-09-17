# planning-with-files: resolve active plan directory (PowerShell mirror).
#
# Resolution order matches scripts/resolve-plan-dir.sh:
#   1. $env:PLAN_ID -> .\.planning\$PLAN_ID\
#   2. .\.planning\.active_plan content
#   3. Newest .\.planning\<dir>\ by LastWriteTime
#   4. Empty (legacy fallback to .\task_plan.md handled by caller)
#
# v3.8.0 parity with the sh resolver: slug validation on every branch, the
# newest-dir scan requires task_plan.md inside the candidate (a sessions/ or
# artifacts/ dir must never win), and containment fails CLOSED when
# canonicalization fails. Only successful canonicalization can rule out a
# junction/symlink escape; slug validation alone blocks textual traversal.

param(
    [string]$PlanRoot = (Join-Path (Get-Location) ".planning"),
    [switch]$CheckAmbiguity
)

$projectRoot = (Get-Location).Path

# Resolve-Path is lexical for Windows junctions: it can return the junction's
# spelling rather than the directory opened by the filesystem. Use a directory
# handle and GetFinalPathNameByHandleW on Windows so containment is decided from
# the object the kernel actually opened.
$script:IsWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
if ($script:IsWindowsHost -and -not ("PwfResolverNative" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class PwfResolverNative {
    private const uint FILE_SHARE_READ = 0x00000001;
    private const uint FILE_SHARE_WRITE = 0x00000002;
    private const uint FILE_SHARE_DELETE = 0x00000004;
    private const uint OPEN_EXISTING = 3;
    private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(
        string name, uint access, uint share, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandleW(
        SafeFileHandle handle, StringBuilder path, uint length, uint flags);

    public static string FinalDirectoryPath(string path) {
        using (SafeFileHandle handle = CreateFileW(
            path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, IntPtr.Zero)) {
            if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
            StringBuilder buffer = new StringBuilder(32768);
            uint length = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
            if (length == 0 || length >= buffer.Capacity)
                throw new Win32Exception(Marshal.GetLastWin32Error());
            string result = buffer.ToString();
            if (result.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase))
                return @"\\" + result.Substring(8);
            if (result.StartsWith(@"\\?\", StringComparison.OrdinalIgnoreCase))
                return result.Substring(4);
            return result;
        }
    }
}
'@
}

function Get-FinalDirectoryPath {
    param([string]$Path)
    if ($script:IsWindowsHost) {
        return [PwfResolverNative]::FinalDirectoryPath($Path)
    }
    return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
}

function Test-FullyQualifiedLocalPath {
    param([string]$Path)
    if (-not $Path -or $Path.StartsWith('\\') -or $Path.StartsWith('//')) {
        return $false
    }
    if ($script:IsWindowsHost) {
        return $Path -match '^[A-Za-z]:[\\/]'
    }
    return [System.IO.Path]::IsPathRooted($Path)
}

# PWF_PLAN_ROOT: absolute plan-root binding (issue #212), mirroring
# resolve-plan-dir.sh. A thread whose cwd is a shared PARENT of the real
# project resolves the parent's plan and never sees the nested one;
# PWF_PLAN_ROOT names the project root whose .planning must be used. Highest
# precedence: it overrides both the cwd default and the -PlanRoot argument
# (an adapter passing ".planning" is spelling out the cwd default, not
# overriding a user's deliberate pin). A pin that is not a directory fails
# CLOSED: the resolver emits nothing, so no caller can be handed the
# ambiguous cwd plan the pin was escaping (injection routes own the
# user-facing notice; stdout here is the data channel). Containment is then
# checked against the pinned root. Unset keeps legacy behavior unchanged.
if ($env:PWF_PLAN_ROOT) {
    $pin = $env:PWF_PLAN_ROOT
    if ((Test-FullyQualifiedLocalPath $pin) -and
        (Test-Path -LiteralPath $pin -PathType Container)) {
        $projectRoot = $pin
        $PlanRoot = Join-Path $pin ".planning"
    } else {
        exit 0
    }
}

# Same shape as the sh resolver's slug_is_valid: first char [A-Za-z0-9_],
# rest [A-Za-z0-9._-]. Blocks traversal tokens before any path is built.
function Test-ValidSlug {
    param([string]$Name)
    if (-not $Name) { return $false }
    return $Name -match '^[A-Za-z0-9_][A-Za-z0-9._-]*$'
}

# Containment guard (security A1.3): a resolved plan dir must canonicalize to
# a path under the project root. A directory symlink/junction inside a valid
# slug pointing outside the workspace would otherwise let the hooks hash and
# inject an arbitrary file. Resolve-Path follows reparse points; we compare
# the real paths. Fails CLOSED on canonicalization failure, matching
# resolve-plan-dir.sh.
function Test-WithinRoot {
    param([string]$Candidate)
    try {
        $rootReal = Get-FinalDirectoryPath $projectRoot
        $candReal = Get-FinalDirectoryPath $Candidate
    } catch {
        return $false
    }
    if (-not $rootReal -or -not $candReal) { return $false }
    $rootNorm = $rootReal.TrimEnd('\', '/')
    $candNorm = $candReal.TrimEnd('\', '/')
    if ($candNorm -eq $rootNorm) { return $true }
    return $candNorm.StartsWith($rootNorm + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

$activeFile = Join-Path $PlanRoot ".active_plan"

# A set PLAN_ID is a BINDING, not a hint (issue #237). A selector that names
# no directory, fails slug validation, or fails containment terminates
# resolution instead of falling through to .active_plan and newest-by-mtime:
# the fall-through let a one-character typo attest and inject a DIFFERENT plan
# at rc=0. Emptiness is the fail-closed signal on this channel, matching
# resolve-plan-dir.sh and the PWF_PLAN_ROOT pin. An empty $env:PLAN_ID is
# falsy here and still means "unset".
# The optional probe distinguishes ambiguity from a legacy-root fallback.
# Multiple named plans require PLAN_ID even without a sessions directory.
$planCount = 0
if (-not $env:PLAN_ID) {
    if ((Test-Path -LiteralPath (Join-Path $PlanRoot "sessions") -PathType Container) -and
        (Test-Path -LiteralPath (Join-Path $projectRoot "task_plan.md") -PathType Leaf)) {
        $planCount = 1
    }
    if (Test-Path -LiteralPath $PlanRoot -PathType Container) {
        foreach ($entry in (Get-ChildItem -LiteralPath $PlanRoot -Directory -ErrorAction SilentlyContinue)) {
            if ((Test-ValidSlug $entry.Name) -and
                (Test-Path -LiteralPath (Join-Path $entry.FullName "task_plan.md") -PathType Leaf)) {
                $planCount++
                if ($planCount -gt 1) { break }
            }
        }
    }
}
if ($CheckAmbiguity) {
    if ($planCount -gt 1) { Write-Output "PWF_PLAN_AMBIGUOUS_V1" }
    exit 0
}
if ($planCount -gt 1) { exit 0 }

if ($env:PLAN_ID) {
    if (Test-ValidSlug $env:PLAN_ID) {
        $candidate = Join-Path $PlanRoot $env:PLAN_ID
        if ((Test-Path $candidate -PathType Container) -and (Test-WithinRoot $candidate)) {
            Write-Output $candidate
            exit 0
        }
    }
    exit 0
}

# Get-Item observes the link object even when its target is missing, unlike
# Test-Path which follows the target. An active pointer that is a directory or
# reparse point is an unsafe/ambiguous selector and must terminate resolution;
# falling through would silently select and expose the newest unrelated plan.
$activeItem = Get-Item -LiteralPath $activeFile -Force -ErrorAction SilentlyContinue
if ($activeItem) {
    if ($activeItem.PSIsContainer -or
        (($activeItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        exit 0
    }
    $planId = (Get-Content -LiteralPath $activeFile -Raw).Trim()
    if ($planId -and (Test-ValidSlug $planId)) {
        $candidate = Join-Path $PlanRoot $planId
        if ((Test-Path $candidate -PathType Container) -and (Test-WithinRoot $candidate)) {
            Write-Output $candidate
            exit 0
        }
    }
}

if (Test-Path $PlanRoot -PathType Container) {
    $latest = Get-ChildItem -Path $PlanRoot -Directory |
        Where-Object { -not $_.Name.StartsWith('.') } |
        Where-Object { Test-ValidSlug $_.Name } |
        Where-Object { Test-Path (Join-Path $_.FullName "task_plan.md") -PathType Leaf } |
        Where-Object { Test-WithinRoot $_.FullName } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latest) {
        Write-Output $latest.FullName
    }
}

exit 0
