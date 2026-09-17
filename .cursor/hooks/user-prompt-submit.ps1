# planning-with-files: User prompt submit hook for Cursor (PowerShell)
# Injects plan context on every user message.
# Critical for session recovery after /clear — dumps actual content, not just advice.

# Issue #195 opt-out. The disabled branch reproduces this hook's own
# no-plan-file behaviour, so the Cursor protocol shape never changes.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

. (Join-Path $PSScriptRoot "resolve-plan-context.ps1")
$PlanContext = Resolve-CursorPlanContext

if (-not $PlanContext.Directory) {
    if ($PlanContext.Status -eq 'ambiguous') {
        Write-Output "[planning-with-files] Multiple plans are available. Set PLAN_ID=<slug> for this session; nothing injected."
    } else {
        Write-Output "[planning-with-files] The selected plan could not be resolved safely. Check PLAN_ID, PWF_PLAN_ROOT, and .active_plan; nothing injected."
    }
    exit 0
}

$planFile = Join-Path $PlanContext.Directory "task_plan.md"
$progressFile = Join-Path $PlanContext.Directory "progress.md"

if (Test-Path -LiteralPath $planFile -PathType Leaf) {
    # --- Nested-root conflict detection (issue #212): fail CLOSED on ambiguity.
    # A shared pointer or newest-plan fallback is still a cwd GUESS unless an
    # explicit PWF_PLAN_ROOT or PLAN_ID selected it. If a direct child carries
    # its own competing .planning (an .active_plan pointer, or at least one
    # <slug>/task_plan.md), this cwd is a shared parent and injecting the root
    # plan is the wrong answer for at least one thread — inject NOTHING and
    # say why. Depth 1 only, matching the sh twin's single glob; dot-named
    # children are skipped for parity with the sh glob (`*` never matches
    # them), so the root's own .planning is never a hit.
    if (-not $env:PWF_PLAN_ROOT -and -not $env:PLAN_ID) {
        $nestedRoots = @()
        foreach ($child in @(Get-ChildItem -Directory -ErrorAction SilentlyContinue)) {
            if ($child.Name.StartsWith('.')) { continue }
            $nestedPlanning = Join-Path $child.FullName ".planning"
            if (-not (Test-Path $nestedPlanning -PathType Container)) { continue }
            $competing = Test-Path (Join-Path $nestedPlanning ".active_plan") -PathType Leaf
            if (-not $competing) {
                foreach ($slug in @(Get-ChildItem -Path $nestedPlanning -Directory -ErrorAction SilentlyContinue)) {
                    if (Test-Path (Join-Path $slug.FullName "task_plan.md") -PathType Leaf) {
                        $competing = $true
                        break
                    }
                }
            }
            if ($competing) { $nestedRoots += $child.Name }
        }
        if ($nestedRoots.Count -gt 0) {
            $nestedList = (@($nestedRoots | Select-Object -First 3)) -join ", "
            Write-Output "[planning-with-files] Ambiguous plan: this cwd has an active plan and a nested project below it has its own ($nestedList). Nothing injected. Pin the thread with PWF_PLAN_ROOT=<absolute path> or PLAN_ID=<slug>."
            exit 0
        }
    }

    Write-Output "[planning-with-files] ACTIVE PLAN — current state:"
    Get-Content -LiteralPath $planFile -TotalCount 50 -Encoding UTF8
    Write-Output ""
    Write-Output "=== recent progress ==="
    if (Test-Path -LiteralPath $progressFile -PathType Leaf) {
        # Timestamp normalization matches scripts/inject-plan.sh and the sh twin
        # (KV-cache stability, v2.40): wall-clock times in the injected tail move
        # every fire otherwise.
        Get-Content -LiteralPath $progressFile -Tail 20 -Encoding UTF8 |
            ForEach-Object {
                $line = $_ -replace 'T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z', 'T00:00:00Z'
                $line -replace 'T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([+-][0-9]{2}:[0-9]{2})', 'T00:00:00$2'
            }
    }
    Write-Output ""
    Write-Output "[planning-with-files] Read findings.md for research context. Continue from the current phase."
}
exit 0
