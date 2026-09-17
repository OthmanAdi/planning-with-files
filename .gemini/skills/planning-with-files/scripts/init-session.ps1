# Initialize planning files for a new session
# Usage: .\init-session.ps1 [-Template TYPE] [project-name]
#        .\init-session.ps1 -PlanDir             # isolated plan with generated slug
#        .\init-session.ps1 -Autonomous        # v3 autonomous mode (opt-in)
#        .\init-session.ps1 -Gated             # v3 gated mode (opt-in, implies autonomous)
# Templates: default, analytics
#
# v3 modes (opt-in): -Autonomous / -Gated write a .mode marker next to the plan,
# reset the .stop_blocks gate counter, clear any stale gate ledger, write a fresh
# 16-hex nonce for delimiter framing, and auto-attest the plan. With NO v3 switch
# and no .mode file, behavior is byte-equivalent to v2.43.0.

param(
    [string]$ProjectName = "project",
    [string]$Template = "default",
    [switch]$PlanDir,
    [switch]$Autonomous,
    [switch]$Gated
)

$DATE = Get-Date -Format "yyyy-MM-dd"

# Resolve v3 opt-in mode. -Gated implies autonomous and is the stronger marker.
$Mode = ""
if ($Gated) {
    $Mode = "gated"
} elseif ($Autonomous) {
    $Mode = "autonomous"
}

# Resolve template directory (skill root is one level up from scripts/)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillRoot = Split-Path -Parent $ScriptDir
$TemplateDir = Join-Path $SkillRoot "templates"

function Get-Nonce {
    # 16 hex chars for the plan-data delimiter framing (security strand rec 8).
    $bytes = New-Object 'System.Byte[]' 8
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Get-PlanSlug([string]$Name) {
    # -creplace: the case-insensitive -replace lets letters that .NET folds to
    # ASCII (a dotted capital I, the Kelvin sign) survive into the plan id.
    $slug = $Name.ToLowerInvariant() -creplace '[^a-z0-9]', '-'
    $slug = $slug -creplace '-{2,}', '-'
    $slug = $slug.Trim('-')
    if ($slug.Length -gt 40) {
        $slug = $slug.Substring(0, 40).TrimEnd('-')
    }
    # The resolvers and the selector only accept ASCII plan ids.
    if ($slug -cnotmatch '^[a-z0-9-]*$') {
        return ""
    }
    return $slug
}

function Get-ShortId {
    return ([Guid]::NewGuid().ToString('N')).Substring(0, 8)
}

function Get-InheritedMode([string]$CurrentMode) {
    $RootModePath = Join-Path (Get-Location).Path ".mode"
    if (-not (Test-Path -LiteralPath $RootModePath)) {
        return $CurrentMode
    }
    if ($CurrentMode -eq "gated") {
        return $CurrentMode
    }

    $RootMode = Get-Content -LiteralPath $RootModePath -Raw -ErrorAction SilentlyContinue
    # Case-sensitive like inherit_root_mode in init-session.sh and the injector.
    if ($RootMode -cmatch 'gate') {
        return "gated"
    }
    if ($RootMode -cmatch 'autonomous') {
        return "autonomous"
    }
    return $CurrentMode
}

# Validate template
if ($Template -ne "default" -and $Template -ne "analytics") {
    Write-Host "Unknown template: $Template (available: default, analytics). Using default."
    $Template = "default"
}

# Match init-session.sh: zero args (or an empty name) preserve legacy root
# mode. A positional project name or -PlanDir creates an isolated
# .planning/<date>-<slug>/ plan.
$NamedPlan = $PSBoundParameters.ContainsKey("ProjectName") -and -not [string]::IsNullOrEmpty($ProjectName)
$UsePlanDir = $PlanDir -or $NamedPlan
if ($UsePlanDir) {
    $PlanningRoot = Join-Path (Get-Location).Path ".planning"
    # Match init-session.sh: set-active-plan.ps1 owns every write to the
    # shared pointer, so a named plan cannot be created without it.
    $PlanSelector = Join-Path $ScriptDir "set-active-plan.ps1"
    if (-not (Test-Path -LiteralPath $PlanSelector -PathType Leaf)) {
        Write-Error "Error: set-active-plan.ps1 is required to create a named plan safely."
        exit 1
    }
    New-Item -ItemType Directory -Path $PlanningRoot -Force | Out-Null
    # Verify the physical planning root and the existing pointer before
    # creating anything below it. A symlink or junction that escapes the
    # project must not redirect init writes, and a linked or non-regular
    # pointer must be refused before a plan directory exists on disk. A
    # script that returns without exit leaves $LASTEXITCODE alone, so reset
    # it first and treat a thrown error as a failure too.
    $global:LASTEXITCODE = 0
    try {
        & $PlanSelector -VerifyRoot *> $null
    } catch {
        $global:LASTEXITCODE = 1
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Error: the planning directory or the active plan pointer is outside the project or cannot be verified."
        exit 1
    }

    if ($NamedPlan) {
        $Slug = Get-PlanSlug $ProjectName
    } else {
        $Slug = ""
        $ProjectName = "untitled"
    }
    if ([string]::IsNullOrEmpty($Slug)) {
        $Slug = "untitled-$(Get-ShortId)"
    }

    $BaseId = "$DATE-$Slug"
    $PlanId = $BaseId
    $Counter = 2
    while (Test-Path -LiteralPath (Join-Path $PlanningRoot $PlanId)) {
        $PlanId = "$BaseId-$Counter"
        $Counter++
    }
    $TargetDir = Join-Path $PlanningRoot $PlanId
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    # Reuse the selector's contained, atomic pointer replacement. Set-Content
    # would follow a reparse point and truncate a hardlinked pointer in place,
    # overwriting whichever file shares that inode.
    $global:LASTEXITCODE = 0
    try {
        & $PlanSelector $PlanId *> $null
    } catch {
        $global:LASTEXITCODE = 1
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Error: could not safely update the active plan pointer at $(Join-Path $PlanningRoot '.active_plan')."
        exit 1
    }
    $Mode = Get-InheritedMode $Mode
} else {
    $TargetDir = (Get-Location).Path
}

$TaskPlanPath = Join-Path $TargetDir "task_plan.md"
$FindingsPath = Join-Path $TargetDir "findings.md"
$ProgressPath = Join-Path $TargetDir "progress.md"
if ($UsePlanDir) {
    $TaskPlanDisplay = $TaskPlanPath
    $FindingsDisplay = $FindingsPath
    $ProgressDisplay = $ProgressPath
} else {
    $TaskPlanDisplay = "task_plan.md"
    $FindingsDisplay = "findings.md"
    $ProgressDisplay = "progress.md"
}

Write-Host "Initializing planning files for: $ProjectName (template: $Template)"
if ($UsePlanDir) {
    Write-Host "PLAN_ID=$PlanId"
}

# Create task_plan.md if it doesn't exist
if (-not (Test-Path -LiteralPath $TaskPlanPath)) {
    $AnalyticsPlan = Join-Path $TemplateDir "analytics_task_plan.md"
    if ($Template -eq "analytics" -and (Test-Path $AnalyticsPlan)) {
        Copy-Item -LiteralPath $AnalyticsPlan -Destination $TaskPlanPath
    } else {
        @"
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Next Step
[The single next action. Update whenever phase status changes.]

## Current Phase
Phase 1

## Phases

### Phase 1: Requirements & Discovery
- [ ] Understand user intent
- [ ] Identify constraints
- [ ] Document in findings.md
- **Status:** in_progress

### Phase 2: Planning & Structure
- [ ] Define approach
- [ ] Create project structure
- **Status:** pending

### Phase 3: Implementation
- [ ] Execute the plan
- [ ] Write to files before executing
- **Status:** pending

### Phase 4: Testing & Verification
- [ ] Verify requirements met
- [ ] Document test results
- **Status:** pending

### Phase 5: Delivery
- [ ] Review outputs
- [ ] Deliver to user
- **Status:** pending

## Decisions Made
| Decision | Rationale |
|----------|-----------|

## Errors Encountered
| Error | Resolution |
|-------|------------|
"@ | Out-File -LiteralPath $TaskPlanPath -Encoding UTF8
    }
    Write-Host "Created $TaskPlanDisplay"
} else {
    Write-Host "$TaskPlanDisplay already exists, skipping"
}

# Create findings.md if it doesn't exist
if (-not (Test-Path -LiteralPath $FindingsPath)) {
    $AnalyticsFindings = Join-Path $TemplateDir "analytics_findings.md"
    if ($Template -eq "analytics" -and (Test-Path $AnalyticsFindings)) {
        Copy-Item -LiteralPath $AnalyticsFindings -Destination $FindingsPath
    } else {
        @"
# Findings & Decisions

## Requirements
-

## Research Findings
-

## Technical Decisions
| Decision | Rationale |
|----------|-----------|

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
-
"@ | Out-File -LiteralPath $FindingsPath -Encoding UTF8
    }
    Write-Host "Created $FindingsDisplay"
} else {
    Write-Host "$FindingsDisplay already exists, skipping"
}

# Create progress.md if it doesn't exist
if (-not (Test-Path -LiteralPath $ProgressPath)) {
    if ($Template -eq "analytics") {
        @"
# Progress Log

## Session: $DATE

### Current Status
- **Phase:** 1 - Data Discovery
- **Started:** $DATE

### Actions Taken
-

### Query Log
| Query | Result Summary | Interpretation |
|-------|---------------|----------------|

### Errors
| Error | Resolution |
|-------|------------|
"@ | Out-File -LiteralPath $ProgressPath -Encoding UTF8
    } else {
        @"
# Progress Log

## Session: $DATE

### Current Status
- **Phase:** 1 - Requirements & Discovery
- **Started:** $DATE

### Actions Taken
-

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|

### Errors
| Error | Resolution |
|-------|------------|
"@ | Out-File -LiteralPath $ProgressPath -Encoding UTF8
    }
    Write-Host "Created $ProgressDisplay"
} else {
    Write-Host "$ProgressDisplay already exists, skipping"
}

Write-Host ""
Write-Host "Planning files initialized!"
if ($UsePlanDir) {
    Write-Host "Active plan recorded: $(Join-Path $PlanningRoot '.active_plan')"
    Write-Host "Pin this terminal to the plan for parallel sessions:"
    Write-Host "  `$env:PLAN_ID='$PlanId'"
} else {
    Write-Host "Files: task_plan.md, findings.md, progress.md"
}

# v3 opt-in mode side effects. No-op when -Autonomous/-Gated were not passed, so
# the default path stays byte-equivalent to v2.43.0. Dotfiles live beside the
# selected plan; root mode therefore retains the legacy project-root behavior.
if ($Mode -ne "") {
    $PlanDirPwf = $TargetDir

    # (a) reset gate block counter, drop stale gate ledger.
    Set-Content -LiteralPath (Join-Path $PlanDirPwf ".stop_blocks") -Value "0" -Encoding ascii
    $StaleLedger = Join-Path $PlanDirPwf ".gate_last_ledger"
    if (Test-Path -LiteralPath $StaleLedger) { Remove-Item -LiteralPath $StaleLedger -Force }

    # (b) fresh 16-hex nonce for delimiter framing.
    Set-Content -LiteralPath (Join-Path $PlanDirPwf ".nonce") -Value (Get-Nonce) -NoNewline -Encoding ascii

    # mode marker. gated implies autonomous, so it carries both tokens.
    if ($Mode -eq "gated") {
        $MarkerText = "autonomous gate"
    } else {
        $MarkerText = "autonomous"
    }
    Set-Content -LiteralPath (Join-Path $PlanDirPwf ".mode") -Value $MarkerText -Encoding ascii

    # (c) auto-attest (attestation default-on in v3 modes, security strand rec 1).
    # attest-plan.ps1 intentionally refuses non-Windows hosts because its secure
    # no-follow implementation uses Win32 handles. On Unix, use the POSIX
    # attester instead. Bind slug mode to the plan we just created so an
    # inherited PLAN_ID cannot redirect attestation to another plan.
    $PlanFilePwf = Join-Path $PlanDirPwf "task_plan.md"
    if (Test-Path -LiteralPath $PlanFilePwf) {
        $HadPlanId = Test-Path Env:PLAN_ID
        $PreviousPlanId = $env:PLAN_ID
        $HadPlanRoot = Test-Path Env:PWF_PLAN_ROOT
        $PreviousPlanRoot = $env:PWF_PLAN_ROOT
        try {
            $env:PWF_PLAN_ROOT = (Get-Location).Path
            if ($UsePlanDir) {
                $env:PLAN_ID = $PlanId
            } else {
                Remove-Item Env:PLAN_ID -ErrorAction SilentlyContinue
            }

            $IsWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
            if ($IsWindowsHost) {
                $AttestPs1 = Join-Path $ScriptDir "attest-plan.ps1"
                if (Test-Path -LiteralPath $AttestPs1) {
                    & $AttestPs1 *> $null
                }
            } else {
                $AttestSh = Join-Path $ScriptDir "attest-plan.sh"
                $Sh = Get-Command sh -ErrorAction SilentlyContinue
                if ($Sh -and (Test-Path -LiteralPath $AttestSh)) {
                    & $Sh.Path $AttestSh *> $null
                }
            }
        } catch {
            # attestation failure must not abort init; the mode marker still stands.
        } finally {
            if ($HadPlanId) {
                $env:PLAN_ID = $PreviousPlanId
            } else {
                Remove-Item Env:PLAN_ID -ErrorAction SilentlyContinue
            }
            if ($HadPlanRoot) {
                $env:PWF_PLAN_ROOT = $PreviousPlanRoot
            } else {
                Remove-Item Env:PWF_PLAN_ROOT -ErrorAction SilentlyContinue
            }
        }
    }

    Write-Host "Mode: $MarkerText (attested, gate counter reset)"
}
