# planning-with-files: set, display, or list the active plan pointer (PowerShell).
#
# Usage:
#   .\set-active-plan.ps1 <plan_id>   - pin .planning\.active_plan to plan_id
#   .\set-active-plan.ps1             - print the current active plan (if any)
#   .\set-active-plan.ps1 -List       - list available named plans and phase counts
#   .\set-active-plan.ps1 --list      - equivalent to -List and -l
#   .\set-active-plan.ps1 -VerifyRoot - check the planning root and pointer only
#   .\set-active-plan.ps1 --verify-root - equivalent to -VerifyRoot

param(
    [Parameter(Position = 0)]
    [string]$PlanId = "",
    [Alias('l', '-list')]
    [switch]$List,
    [Alias('verify-root')]
    [switch]$VerifyRoot,
    [Alias('h', '-help')]
    [switch]$Help
)

$ProjectRoot = (Get-Location).Path
# Windows PowerShell 5.1 can silently change directories when -File inherits
# a cwd containing wildcard characters. Recover that physical cwd only for a
# direct invocation of this script; interactive Set-Location remains primary.
if ($PSVersionTable.PSVersion.Major -eq 5 -and
    [System.Management.Automation.WildcardPattern]::ContainsWildcardCharacters([Environment]::CurrentDirectory)) {
    $processArgs = [Environment]::GetCommandLineArgs()
    for ($index = 0; $index -lt ($processArgs.Length - 1); $index++) {
        if ($processArgs[$index] -ieq '-File') {
            $entryScript = $processArgs[$index + 1]
            if (-not [IO.Path]::IsPathRooted($entryScript)) {
                $entryScript = Join-Path ([Environment]::CurrentDirectory) $entryScript
            }
            if ([IO.Path]::GetFullPath($entryScript) -eq [IO.Path]::GetFullPath($PSCommandPath)) {
                $ProjectRoot = [Environment]::CurrentDirectory
            }
            break
        }
    }
}
$PlanRoot = Join-Path $ProjectRoot ".planning"
$ActiveFile = Join-Path $PlanRoot ".active_plan"
$script:IsWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT

# Resolve-Path can retain a junction's spelling. Like resolve-plan-dir.ps1,
# open the actual filesystem object before checking the project boundary.
# The Windows handle supports both directories and task_plan.md files.
function Get-FinalPath {
    param([string]$Path)
    if (-not ("PwfPlanListingNative" -as [type])) {
        Add-Type -ErrorAction Stop -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class PwfPlanListingNative {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(
        string name, uint access, uint share, IntPtr security,
        uint creation, uint flags, IntPtr template);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandleW(
        SafeFileHandle handle, StringBuilder path, uint length, uint flags);
    [DllImport("libc", SetLastError = true)]
    private static extern IntPtr realpath(string path, IntPtr resolved);
    [DllImport("libc")]
    private static extern void free(IntPtr pointer);

    public static string FinalPath(string path) {
        if (Environment.OSVersion.Platform != PlatformID.Win32NT) {
            IntPtr resolved = realpath(path, IntPtr.Zero);
            if (resolved == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
            try { return Marshal.PtrToStringAnsi(resolved); }
            finally { free(resolved); }
        }
        // OPEN_EXISTING, FILE_SHARE_READ | WRITE | DELETE, BACKUP_SEMANTICS.
        using (SafeFileHandle handle = CreateFileW(
            path, 0, 7, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero)) {
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
    return [PwfPlanListingNative]::FinalPath($Path)
}

function Test-WithinRoot {
    param([string]$Path)
    try {
        $rootReal = (Get-FinalPath $ProjectRoot).TrimEnd('\', '/')
        $pathReal = (Get-FinalPath $Path).TrimEnd('\', '/')
        $comparison = [StringComparison]::Ordinal
        if ($script:IsWindowsHost) { $comparison = [StringComparison]::OrdinalIgnoreCase }
        return $pathReal.Equals($rootReal, $comparison) -or
            $pathReal.StartsWith($rootReal + [IO.Path]::DirectorySeparatorChar, $comparison)
    } catch {
        return $false
    }
}

function Test-ValidSlug {
    param([string]$Name)
    return $Name -cmatch '^[A-Za-z0-9_][A-Za-z0-9._-]*\z'
}

function Test-SafeActiveFile {
    param([switch]$AllowLink)
    $item = Get-Item -LiteralPath $ActiveFile -Force -ErrorAction SilentlyContinue
    if (-not $item) { return $false }
    # Reading may follow a verified in-project link; writing must not. A link
    # is a symlink or junction by LinkType, never the bare ReparsePoint
    # attribute: OneDrive Files On-Demand marks every synced file as a
    # reparse point, and the pointer must stay writable there (#275).
    $linked = ([string]$item.LinkType) -in @('SymbolicLink', 'Junction')
    return -not $item.PSIsContainer -and
        ($AllowLink -or -not $linked) -and
        (Test-WithinRoot $ActiveFile)
}

function Get-CurrentActivePlan {
    if (-not (Test-SafeActiveFile -AllowLink)) { return "" }
    try {
        $current = ([string](Get-Content -LiteralPath $ActiveFile -Raw -Encoding UTF8 -ErrorAction Stop)).Trim([char[]]"`r`n")
        if (Test-ValidSlug $current) { return $current }
    } catch { }
    return ""
}

function Add-PhaseStatus {
    param([hashtable]$Counts, $Phase)
    if ($null -eq $Phase) { return }
    $status = $Phase.Inline
    if ($Phase.Primary) { $status = $Phase.Primary }
    if ($status) { $Counts[$status]++ }
}

function Get-PhaseStatus {
    param([string]$PlanFile)
    $counts = @{ total = 0; complete = 0; in_progress = 0; pending = 0 }
    $phase = $null
    $fence = ""
    $fenceLength = 0
    # The shipped translations keep status identifiers in English. Unicode
    # escapes preserve Windows PowerShell 5.1 compatibility without a BOM.
    $phaseLabel = '(?:Phase|Fase|\u0627\u0644\u0645\u0631\u062d\u0644\u0629|\u9636\u6bb5|\u968e\u6bb5)'
    $statusLabel = '(?:Status:|Estado:|\u0627\u0644\u062d\u0627\u0644\u0629:|\u72b6\u6001\uff1a|\u72c0\u614b\uff1a)'
    # Read once; an empty file is a valid plan with zero phases.
    $content = [string](Get-Content -LiteralPath $PlanFile -Raw -Encoding UTF8 -ErrorAction Stop)
    foreach ($line in ($content -split '\r?\n')) {
        if ($fence) {
            $closing = '^ {0,3}' + [regex]::Escape($fence) + '{' + $fenceLength + ',}[ \t]*$'
            if ($line -match $closing) { $fence = "" }
            continue
        }
        if ($line -match '^ {0,3}(`{3,}|~{3,})') {
            $fence = $Matches[1].Substring(0, 1)
            $fenceLength = $Matches[1].Length
            continue
        }
        if ($line -cmatch ('^ {0,3}###[ \t]+' + $phaseLabel + '[ \t]+[0-9]+(?:[^0-9A-Za-z_]|$)')) {
            Add-PhaseStatus $counts $phase
            $phase = @{ Primary = ""; Inline = "" }
            $counts.total++
            if ($line -cmatch '\[(complete|in_progress|pending)\]') {
                $phase.Inline = $Matches[1]
            }
            continue
        }
        if ($line -match '^ {0,3}#{1,3}(?:[ \t]+|$)') {
            Add-PhaseStatus $counts $phase
            $phase = $null
            continue
        }
        if ($null -ne $phase -and -not $phase.Primary -and
            $line -cmatch ('^ {0,3}(?:-[ \t]+)?\*\*' + $statusLabel + '\*\*[ \t]+(complete|in_progress|pending)(?:[ \t]|$)')) {
            $phase.Primary = $Matches[1]
        }
    }
    Add-PhaseStatus $counts $phase
    return "$($counts.complete)/$($counts.total) complete, $($counts.in_progress) in_progress, $($counts.pending) pending"
}

function Show-PlanList {
    if (-not (Test-Path -LiteralPath $PlanRoot -PathType Container)) {
        Write-Output "No planning directory found."
        return
    }
    if (-not (Test-WithinRoot $PlanRoot)) {
        Write-Error "Error: planning directory is outside the project or cannot be verified."
        exit 1
    }
    $active = Get-CurrentActivePlan
    Write-Output "Available plans:"
    Write-Output "[active] marks the shared .active_plan pointer; listing does not bind this session."
    $found = $false
    foreach ($plan in (Get-ChildItem -LiteralPath $PlanRoot -Directory -ErrorAction SilentlyContinue | Sort-Object Name)) {
        # A linked plan directory is never a plan (#270): no resolver selects it.
        if (([string]$plan.LinkType) -in @('SymbolicLink', 'Junction')) { continue }
        if (-not (Test-ValidSlug $plan.Name) -or -not (Test-WithinRoot $plan.FullName)) { continue }
        $planFile = Join-Path $plan.FullName "task_plan.md"
        if (-not (Test-Path -LiteralPath $planFile -PathType Leaf) -or -not (Test-WithinRoot $planFile)) { continue }
        try { $status = Get-PhaseStatus $planFile } catch { continue }
        $marker = ""
        if ($plan.Name -ceq $active) { $marker = " [active]" }
        Write-Output "- $($plan.Name)$marker - $status"
        $found = $true
    }
    if (-not $found) { Write-Output "No named plans found." }
}

if ($Help -or $PlanId -eq "--help" -or $PlanId -eq "-h") {
    Write-Output "Usage: set-active-plan.ps1 [-List|-l|--list|-VerifyRoot|PLAN_ID]"
    exit 0
}

# Constant-time check for callers that are about to create a plan: the
# planning root, when present, must be inside the project, and an existing
# pointer must be replaceable. Nothing is read, listed, or written.
if ($VerifyRoot) {
    if ($List -or $PlanId) {
        Write-Error "Error: verify the planning root in a separate call."
        exit 1
    }
    if ((Test-Path -LiteralPath $PlanRoot -PathType Container) -and -not (Test-WithinRoot $PlanRoot)) {
        Write-Error "Error: planning directory is outside the project or cannot be verified."
        exit 1
    }
    $existingPointer = Get-Item -LiteralPath $ActiveFile -Force -ErrorAction SilentlyContinue
    if ($existingPointer -and -not (Test-SafeActiveFile)) {
        Write-Error "Error: the active plan pointer must be a regular file within the project."
        exit 1
    }
    exit 0
}

if ($List -or $PlanId -eq "--list" -or $PlanId -eq "-l") {
    if ($List -and $PlanId) {
        Write-Error "Error: list plans or set PLAN_ID in separate calls."
        exit 1
    }
    Show-PlanList
    exit 0
}

if ($PlanId -eq "") {
    $current = ""
    if ((Test-Path -LiteralPath $PlanRoot -PathType Container) -and -not (Test-WithinRoot $PlanRoot)) {
        Write-Error "Error: planning directory is outside the project or cannot be verified."
        exit 1
    }
    if (Test-WithinRoot $PlanRoot) { $current = Get-CurrentActivePlan }
    if ($current) {
        $planDir = Join-Path $PlanRoot $current
        if ((Test-Path -LiteralPath $planDir -PathType Container) -and (Test-WithinRoot $planDir)) {
            Write-Output "Active plan: $current"
            Write-Output "Path: $planDir"
        } else {
            Write-Output "Active plan pointer: $current (directory not found or outside project - stale pointer)"
        }
    } else {
        Write-Output "No active plan set."
    }
    exit 0
}

if (-not (Test-ValidSlug $PlanId)) {
    Write-Error "Error: invalid plan ID. Use letters, numbers, underscores, dots, or hyphens; start with a letter, number, or underscore."
    exit 1
}
$PlanDir = Join-Path $PlanRoot $PlanId
if (-not (Test-Path -LiteralPath $PlanDir -PathType Container)) {
    Write-Error "Error: plan directory not found: $PlanDir"
    Write-Error "Run: init-session.sh `"$PlanId`" to create it, or check .planning\ for available plans."
    exit 1
}
$planDirItem = Get-Item -LiteralPath $PlanDir -Force -ErrorAction SilentlyContinue
if ($planDirItem -and (([string]$planDirItem.LinkType) -in @('SymbolicLink', 'Junction'))) {
    Write-Error "Error: plan directory is a symlink or junction and no route selects it: $PlanDir"
    exit 1
}
if (-not (Test-WithinRoot $PlanRoot) -or -not (Test-WithinRoot $PlanDir)) {
    Write-Error "Error: plan directory must remain within the project."
    exit 1
}
$activeItem = Get-Item -LiteralPath $ActiveFile -Force -ErrorAction SilentlyContinue
if ($activeItem -and -not (Test-SafeActiveFile)) {
    Write-Error "Error: the active plan pointer must be a regular file within the project."
    exit 1
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
# Replace the directory entry instead of truncating an existing inode: a
# hardlinked pointer must not overwrite another file. The exclusive temporary
# file lives beside the pointer, keeping replacement on the same filesystem.
$tempFile = Join-Path $PlanRoot ('.active_plan.' + [guid]::NewGuid().ToString('N') + '.tmp')
$createdTemp = $false
try {
    $stream = [IO.File]::Open($tempFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $createdTemp = $true
    try {
        $bytes = $utf8NoBom.GetBytes($PlanId)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
    } finally { $stream.Dispose() }
    $maxAttempts = 20
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            $currentActive = Get-Item -LiteralPath $ActiveFile -Force -ErrorAction SilentlyContinue
            if ($currentActive) {
                if (-not (Test-SafeActiveFile)) {
                    throw [InvalidOperationException]::new("the active plan pointer became unsafe during replacement")
                }
                [IO.File]::Replace($tempFile, $ActiveFile, [NullString]::Value)
            } else {
                [IO.File]::Move($tempFile, $ActiveFile)
            }
            break
        } catch [IO.IOException] {
            if ($attempt -eq $maxAttempts) { throw }
            Start-Sleep -Milliseconds 25
        }
    }
} catch {
    Write-Error "Error: could not set the active plan pointer: $($_.Exception.Message)"
    exit 1
} finally {
    if ($createdTemp -and (Test-Path -LiteralPath $tempFile)) {
        Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
    }
}
Write-Output "Active plan set to: $PlanId"
Write-Output "Path: $PlanDir"
Write-Output ""
Write-Output "To pin this terminal session only:"
Write-Output "`$env:PLAN_ID = '$PlanId'"
