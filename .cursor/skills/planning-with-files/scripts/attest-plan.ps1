#requires -Version 5.0
<#
.SYNOPSIS
    Lock the current task_plan.md content with a SHA-256 attestation.

.DESCRIPTION
    Use after you finalise (or intentionally edit) a plan. The hooks then refuse
    to inject plan content into the model context if the file diverges from the
    attested hash, surfacing a "[PLAN TAMPERED]" warning instead.

    Plan resolution:
      1. $env:PLAN_ID  -> ./.planning/$PLAN_ID/
      2. ./.planning/.active_plan
      3. Newest ./.planning/<dir>/ by LastWriteTime
      4. Legacy ./task_plan.md at project root

.PARAMETER Show
    Print the stored hash for the active plan.

.PARAMETER Clear
    Remove the attestation (re-open the plan).
#>
[CmdletBinding(DefaultParameterSetName = "Attest")]
param(
    [Parameter(ParameterSetName = "Show")]
    [switch] $Show,

    [Parameter(ParameterSetName = "Clear")]
    [switch] $Clear
)

$ErrorActionPreference = "Stop"

$script:IsWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
if (-not $script:IsWindowsHost) {
    throw "Safe no-follow descriptor operations are unavailable in this PowerShell script on Unix. Use scripts/attest-plan.sh instead."
}
if ($script:IsWindowsHost -and -not ("PwfAttestationNative" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class PwfAttestationNative {
    private const uint GENERIC_READ = 0x80000000;
    private const uint GENERIC_WRITE = 0x40000000;
    private const uint DELETE = 0x00010000;
    private const uint FILE_READ_ATTRIBUTES = 0x00000080;
    private const uint FILE_SHARE_READ = 0x00000001;
    private const uint FILE_SHARE_WRITE = 0x00000002;
    private const uint FILE_SHARE_DELETE = 0x00000004;
    private const uint CREATE_NEW = 1;
    private const uint OPEN_EXISTING = 3;
    private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
    private const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
    private const uint FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400;
    private const int FileAttributeTagInfo = 9;
    private const int FileDispositionInfo = 4;
    private const int ERROR_FILE_EXISTS = 80;
    private const int ERROR_ALREADY_EXISTS = 183;

    [StructLayout(LayoutKind.Sequential)]
    private struct FILE_ATTRIBUTE_TAG_INFO {
        public uint FileAttributes;
        public uint ReparseTag;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BY_HANDLE_FILE_INFORMATION {
        public uint FileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FILE_DISPOSITION_INFO {
        [MarshalAs(UnmanagedType.Bool)] public bool DeleteFile;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(
        string name, uint access, uint share, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandleEx(
        SafeFileHandle handle, int infoClass,
        out FILE_ATTRIBUTE_TAG_INFO info, uint size);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle handle, out BY_HANDLE_FILE_INFORMATION info);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetFileInformationByHandle(
        SafeFileHandle handle, int infoClass,
        ref FILE_DISPOSITION_INFO info, uint size);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandleW(
        SafeFileHandle handle, StringBuilder path, uint length, uint flags);

    private static void ValidateRegular(SafeFileHandle handle, bool singleLink) {
        FILE_ATTRIBUTE_TAG_INFO tag;
        if (!GetFileInformationByHandleEx(
            handle, FileAttributeTagInfo, out tag,
            (uint)Marshal.SizeOf(typeof(FILE_ATTRIBUTE_TAG_INFO))))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        if ((tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0)
            throw new IOException("Refusing a reparse-point file.");
        if ((tag.FileAttributes & (uint)FileAttributes.Directory) != 0)
            throw new IOException("Refusing a directory where a regular file is required.");
        if (singleLink) {
            BY_HANDLE_FILE_INFORMATION info;
            if (!GetFileInformationByHandle(handle, out info))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            if (info.NumberOfLinks != 1)
                throw new IOException("Refusing a multiply-linked attestation file.");
        }
    }

    public static SafeFileHandle OpenRead(string path, bool singleLink) {
        SafeFileHandle handle = CreateFileW(
            path, GENERIC_READ | FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ, IntPtr.Zero, OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT, IntPtr.Zero);
        if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
        try { ValidateRegular(handle, singleLink); return handle; }
        catch { handle.Dispose(); throw; }
    }

    public static SafeFileHandle OpenAttestationWrite(string path) {
        uint access = GENERIC_READ | GENERIC_WRITE | DELETE | FILE_READ_ATTRIBUTES;
        SafeFileHandle handle = CreateFileW(
            path, access, 0, IntPtr.Zero, CREATE_NEW,
            FILE_FLAG_OPEN_REPARSE_POINT, IntPtr.Zero);
        if (handle.IsInvalid) {
            int error = Marshal.GetLastWin32Error();
            if (error != ERROR_FILE_EXISTS && error != ERROR_ALREADY_EXISTS)
                throw new Win32Exception(error);
            handle = CreateFileW(
                path, access, 0, IntPtr.Zero, OPEN_EXISTING,
                FILE_FLAG_OPEN_REPARSE_POINT, IntPtr.Zero);
            if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        try { ValidateRegular(handle, true); return handle; }
        catch { handle.Dispose(); throw; }
    }

    public static SafeFileHandle OpenDelete(string path) {
        SafeFileHandle handle = CreateFileW(
            path, DELETE | FILE_READ_ATTRIBUTES, 0, IntPtr.Zero, OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT, IntPtr.Zero);
        if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
        try { ValidateRegular(handle, true); return handle; }
        catch { handle.Dispose(); throw; }
    }

    public static void DeleteOpened(SafeFileHandle handle) {
        FILE_DISPOSITION_INFO info = new FILE_DISPOSITION_INFO { DeleteFile = true };
        if (!SetFileInformationByHandle(
            handle, FileDispositionInfo, ref info,
            (uint)Marshal.SizeOf(typeof(FILE_DISPOSITION_INFO))))
            throw new Win32Exception(Marshal.GetLastWin32Error());
    }

    public static string FinalPath(SafeFileHandle handle) {
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

    public static string FileIdentity(SafeFileHandle handle) {
        BY_HANDLE_FILE_INFORMATION info;
        if (!GetFileInformationByHandle(handle, out info))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        return info.VolumeSerialNumber.ToString("X8") + ":" +
            info.FileIndexHigh.ToString("X8") + info.FileIndexLow.ToString("X8");
    }

    public static string FinalDirectoryPath(string path) {
        using (SafeFileHandle handle = OpenDirectory(path)) {
            return FinalPath(handle);
        }
    }

    public static SafeFileHandle OpenDirectory(string path) {
        SafeFileHandle handle = CreateFileW(
            path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, IntPtr.Zero);
        if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
        return handle;
    }
}
'@
}

$script:SecurityRootHandle = $null
$script:SecurityRootFinalPath = $null
if ($script:IsWindowsHost) {
    $securityRootPath = (Get-Location).Path
    if ($env:PWF_PLAN_ROOT) {
        $pin = $env:PWF_PLAN_ROOT
        # Windows PowerShell 5.1 has no IsPathFullyQualified; a drive-qualified
        # local path is the only accepted shape, as in resolve-plan-dir.ps1.
        $isUnc = $pin.StartsWith('\\') -or $pin.StartsWith('//')
        if ($isUnc -or ($pin -notmatch '^[A-Za-z]:[\\/]')) {
            throw "[plan-attest] PWF_PLAN_ROOT must be an absolute local path."
        }
        $securityRootPath = $pin
    }
    $script:SecurityRootHandle = [PwfAttestationNative]::OpenDirectory($securityRootPath)
    $script:SecurityRootFinalPath = [PwfAttestationNative]::FinalPath($script:SecurityRootHandle).TrimEnd('\', '/')
}

function Test-FinalPathWithinSecurityRoot {
    param([string] $FinalPath)
    $candidate = $FinalPath.TrimEnd('\', '/')
    if ([string]::Equals($candidate, $script:SecurityRootFinalPath, [StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return $candidate.StartsWith(
        $script:SecurityRootFinalPath + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Open-TrustedDirectory {
    param([string] $ExpectedDirectory)
    $handle = [PwfAttestationNative]::OpenDirectory($ExpectedDirectory)
    try {
        $finalPath = [PwfAttestationNative]::FinalPath($handle).TrimEnd('\', '/')
        if (-not (Test-FinalPathWithinSecurityRoot $finalPath)) {
            throw "Refusing a plan directory outside the frozen project root."
        }
        return [PSCustomObject]@{
            Handle = $handle
            FinalPath = $finalPath
            Identity = [PwfAttestationNative]::FileIdentity($handle)
        }
    } catch {
        $handle.Dispose()
        throw
    }
}

function Assert-HandleParent {
    param(
        [Microsoft.Win32.SafeHandles.SafeFileHandle] $Handle,
        [string] $ExpectedDirectoryFinal,
        [string] $ExpectedDirectoryIdentity
    )
    if (-not $script:IsWindowsHost) { return }
    $openedPath = [PwfAttestationNative]::FinalPath($Handle)
    $openedParent = (Split-Path -Parent $openedPath).TrimEnd('\', '/')
    if (-not [string]::Equals($openedParent, $ExpectedDirectoryFinal, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing file outside the expected plan directory."
    }
    $parentHandle = [PwfAttestationNative]::OpenDirectory($openedParent)
    try {
        $openedIdentity = [PwfAttestationNative]::FileIdentity($parentHandle)
        if (-not [string]::Equals($openedIdentity, $ExpectedDirectoryIdentity, [StringComparison]::Ordinal)) {
            throw "Refusing a file whose parent directory identity changed."
        }
    } finally {
        $parentHandle.Dispose()
    }
}

function Open-SafeReadStream {
    param([string] $Path, [string] $ExpectedDirectory, [switch] $SingleLink)
    if (-not $script:IsWindowsHost) {
        throw "[plan-attest] Safe no-follow descriptor operations are unavailable in this PowerShell script on Unix. Use scripts/attest-plan.sh instead."
    }
    $directory = Open-TrustedDirectory -ExpectedDirectory $ExpectedDirectory
    try {
        $handle = [PwfAttestationNative]::OpenRead($Path, [bool]$SingleLink)
        try {
            Assert-HandleParent -Handle $handle -ExpectedDirectoryFinal $directory.FinalPath -ExpectedDirectoryIdentity $directory.Identity
            return New-Object System.IO.FileStream($handle, [IO.FileAccess]::Read)
        } catch {
            $handle.Dispose()
            throw
        }
    } finally {
        $directory.Handle.Dispose()
    }
}

function Read-SafeText {
    param([string] $Path, [string] $ExpectedDirectory, [int64] $MaxBytes)
    $stream = Open-SafeReadStream -Path $Path -ExpectedDirectory $ExpectedDirectory -SingleLink
    try {
        if ($stream.Length -gt $MaxBytes) { throw "Refusing oversized metadata file."
        }
        $buffer = New-Object byte[] ([int]$stream.Length)
        $offset = 0
        while ($offset -lt $buffer.Length) {
            $read = $stream.Read($buffer, $offset, $buffer.Length - $offset)
            if ($read -le 0) { break }
            $offset += $read
        }
        return [Text.Encoding]::UTF8.GetString($buffer, 0, $offset)
    } finally {
        $stream.Dispose()
    }
}

function Write-SafeAscii {
    param([string] $Path, [string] $ExpectedDirectory, [string] $Value)
    $bytes = [Text.Encoding]::ASCII.GetBytes($Value)
    if (-not $script:IsWindowsHost) {
        throw "[plan-attest] Safe no-follow descriptor operations are unavailable in this PowerShell script on Unix. Use scripts/attest-plan.sh instead."
    }
    $directory = Open-TrustedDirectory -ExpectedDirectory $ExpectedDirectory
    try {
        $handle = [PwfAttestationNative]::OpenAttestationWrite($Path)
        try {
            Assert-HandleParent -Handle $handle -ExpectedDirectoryFinal $directory.FinalPath -ExpectedDirectoryIdentity $directory.Identity
            $stream = New-Object System.IO.FileStream($handle, [IO.FileAccess]::ReadWrite)
            $handle = $null
            try {
                $stream.SetLength(0)
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Flush($true)
                $stream.Position = 0
                $verify = New-Object byte[] $bytes.Length
                $read = $stream.Read($verify, 0, $verify.Length)
                return [Text.Encoding]::ASCII.GetString($verify, 0, $read)
            } finally {
                $stream.Dispose()
            }
        } finally {
            if ($handle) { $handle.Dispose() }
        }
    } finally {
        $directory.Handle.Dispose()
    }
}

function Remove-SafeFile {
    param([string] $Path, [string] $ExpectedDirectory)
    if (-not $script:IsWindowsHost) {
        throw "[plan-attest] Safe no-follow descriptor operations are unavailable in this PowerShell script on Unix. Use scripts/attest-plan.sh instead."
    }
    $directory = Open-TrustedDirectory -ExpectedDirectory $ExpectedDirectory
    try {
        $handle = [PwfAttestationNative]::OpenDelete($Path)
        try {
            Assert-HandleParent -Handle $handle -ExpectedDirectoryFinal $directory.FinalPath -ExpectedDirectoryIdentity $directory.Identity
            [PwfAttestationNative]::DeleteOpened($handle)
        } finally {
            $handle.Dispose()
        }
    } finally {
        $directory.Handle.Dispose()
    }
}

function Resolve-ContainedPlanFile {
    param(
        [string] $Candidate,
        [string] $ExpectedDirectory
    )
    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { return $null }
    try {
        $stream = Open-SafeReadStream -Path $Candidate -ExpectedDirectory $ExpectedDirectory
        $stream.Dispose()
        return (Get-Item -LiteralPath $Candidate -Force -ErrorAction Stop).FullName
    } catch { return $null }
}

function Test-SlugPlanDirectory {
    param([string] $Directory)
    try {
        $finalDirectory = [PwfAttestationNative]::FinalDirectoryPath($Directory)
    } catch {
        return $false
    }
    $planningDirectory = Split-Path -Parent $finalDirectory
    $planId = Split-Path -Leaf $finalDirectory
    return (
        (Split-Path -Leaf $planningDirectory) -eq ".planning" -and
        $planId -match '^[A-Za-z0-9_][A-Za-z0-9._-]*$'
    )
}

function Resolve-PlanFile {
    $resolver = Join-Path $PSScriptRoot "resolve-plan-dir.ps1"
    if (-not (Test-Path -LiteralPath $resolver -PathType Leaf)) { return $null }
    $resolvedDir = @(& $resolver | Where-Object { $_ }) | Select-Object -First 1
    if (-not $resolvedDir -and ((& $resolver -CheckAmbiguity) -eq "PWF_PLAN_AMBIGUOUS_V1")) { return $null }
    if ($resolvedDir) {
        $planFile = Join-Path $resolvedDir "task_plan.md"
        return (Resolve-ContainedPlanFile -Candidate $planFile -ExpectedDirectory $resolvedDir)
    }

    # An explicit pin or a scoped selector that failed validation must never
    # fall through and attest an unrelated legacy-root plan.
    if ($env:PWF_PLAN_ROOT -or $env:PLAN_ID) { return $null }
    $activePointer = Join-Path (Join-Path (Get-Location) ".planning") ".active_plan"
    $activePointerItem = Get-Item -LiteralPath $activePointer -Force -ErrorAction SilentlyContinue
    if ($activePointerItem) { return $null }

    $currentDirectory = (Get-Location).Path
    if (Test-SlugPlanDirectory $currentDirectory) {
        $slugPlan = Join-Path $currentDirectory "task_plan.md"
        return (Resolve-ContainedPlanFile -Candidate $slugPlan -ExpectedDirectory $currentDirectory)
    }

    $legacy = Join-Path $currentDirectory "task_plan.md"
    return (Resolve-ContainedPlanFile -Candidate $legacy -ExpectedDirectory $currentDirectory)
}

function Get-AttestationPath {
    param([string] $PlanFile)
    $planDir = Split-Path -Parent $PlanFile
    $cwd     = (Get-Location).Path
    if ($planDir -eq $cwd) {
        if (Test-SlugPlanDirectory $cwd) {
            return (Join-Path $cwd ".attestation")
        }
        return (Join-Path $cwd ".plan-attestation")
    }
    return (Join-Path $planDir ".attestation")
}

$planFile = Resolve-PlanFile
if (-not $planFile) {
    Write-Error "[plan-attest] No task_plan.md found. Create a plan first."
    exit 1
}

$attestationFile = Get-AttestationPath -PlanFile $planFile
$attestationDir = Split-Path -Parent $attestationFile

if ($Show) {
    if (Get-Item -LiteralPath $attestationFile -Force -ErrorAction SilentlyContinue) {
        Write-Output "Plan: $planFile"
        Write-Output "Attestation: $attestationFile"
        Write-Output ("SHA-256: " + (Read-SafeText -Path $attestationFile -ExpectedDirectory $attestationDir -MaxBytes 4096).Trim())
        # Nonce (security A1.4): surface the per-plan nonce if init-session
        # generated one next to the attestation. Informational only here; the
        # hooks consume it to build collision-proof BEGIN/END delimiters.
        $nonceFile = Join-Path (Split-Path -Parent $attestationFile) ".nonce"
        if (Get-Item -LiteralPath $nonceFile -Force -ErrorAction SilentlyContinue) {
            $nonceVal = (Read-SafeText -Path $nonceFile -ExpectedDirectory $attestationDir -MaxBytes 4096).Trim()
            if ($nonceVal) { Write-Output "Nonce: $nonceVal" }
        }
    } else {
        Write-Output "[plan-attest] No attestation set for $planFile."
        exit 1
    }
    exit 0
}

if ($Clear) {
    if (Get-Item -LiteralPath $attestationFile -Force -ErrorAction SilentlyContinue) {
        Remove-SafeFile -Path $attestationFile -ExpectedDirectory $attestationDir
        Write-Output "[plan-attest] Cleared attestation for $planFile."
    } else {
        Write-Output "[plan-attest] No attestation to clear."
    }
    exit 0
}

$planStream = Open-SafeReadStream -Path $planFile -ExpectedDirectory (Split-Path -Parent $planFile)
try {
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $sha256.ComputeHash($planStream)
    } finally {
        $sha256.Dispose()
    }
} finally {
    $planStream.Dispose()
}
$hashVal = ([BitConverter]::ToString($hashBytes)).Replace("-", "").ToLowerInvariant()
$storedHash = Write-SafeAscii -Path $attestationFile -ExpectedDirectory $attestationDir -Value $hashVal

# Integrity verification (security A2.1): confirm the on-disk attestation
# matches the intended hash before reporting success. A silent write failure
# (permissions, full disk) must not leave a stale attestation and exit clean.
if ($null -ne $storedHash) { $storedHash = $storedHash.Trim() }
if ($storedHash -ne $hashVal) {
    Write-Error "[plan-attest] Attestation write verification FAILED for $attestationFile. Expected $hashVal, found $storedHash. The plan is NOT attested."
    exit 1
}

$short = $hashVal.Substring(0, 12)
Write-Output "[plan-attest] Locked $planFile"
Write-Output "[plan-attest] SHA-256: $short... (stored in $attestationFile)"
Write-Output "[plan-attest] Hooks will block injection if the file is modified without re-running this command."
exit 0
