#!/usr/bin/env bash
# Initialize planning files for a new session.
#
# Usage:
#   ./init-session.sh                              # legacy: root-level task_plan.md, findings.md, progress.md
#   ./init-session.sh [--template TYPE]            # legacy with template choice
#   ./init-session.sh "Backend Refactor"           # slug mode: .planning/<date>-backend-refactor/
#   ./init-session.sh --plan-dir                   # slug mode with auto-generated untitled-<short> name
#   ./init-session.sh --plan-dir "Quick Spike"     # slug mode, explicit slug
#   ./init-session.sh --autonomous "Long Run"      # v3 autonomous mode (opt-in): .mode + nonce + auto-attest
#   ./init-session.sh --gated "Gated Run"          # v3 gated mode (opt-in, implies autonomous): adds Stop-gate marker
#   ./init-session.sh --autonomous                 # v3 flags also work in legacy root mode (dotfiles at root)
#
# Legacy mode (zero positional args, no --plan-dir) preserves v1.x behavior so
# upgrades stay non-breaking. Slug mode addresses parallel multi-task isolation
# (issue #148) by writing each plan under .planning/<date>-<slug>/ and pinning
# .planning/.active_plan so resolve-plan-dir.sh can find it.
#
# v3 modes (opt-in): --autonomous / --gated write a .mode marker next to the
# plan, reset the .stop_blocks gate counter, clear any stale gate ledger, write
# a fresh nonce for delimiter framing, and auto-attest the plan. With NO v3 flag
# and no .mode file, behavior is byte-equivalent to v2.43.0 (no .mode, no nonce,
# no attestation change).

set -e

usage() {
    cat << 'EOF'
Usage: init-session.sh [OPTIONS] [PROJECT NAME]

Initialize task_plan.md, findings.md, and progress.md for a planning session.

Options:
  -t, --template TYPE  Use the default or analytics template.
      --plan-dir       Create an isolated plan directory without a name.
      --autonomous     Enable autonomous mode and plan attestation.
      --gated          Enable autonomous mode with the completion gate.
  -h, --help           Print this help and exit without changing files.
EOF
}

TEMPLATE="default"
PROJECT_NAME=""
USE_PLAN_DIR=0
MODE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --template|-t)
            TEMPLATE="$2"
            shift 2
            ;;
        --plan-dir)
            USE_PLAN_DIR=1
            shift
            ;;
        --autonomous)
            # autonomous wins only if --gated hasn't already been set (gated
            # implies autonomous and is the stronger marker).
            if [ "$MODE" != "gated" ]; then
                MODE="autonomous"
            fi
            shift
            ;;
        --gated)
            MODE="gated"
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            if [ -z "$PROJECT_NAME" ]; then
                PROJECT_NAME="$1"
            else
                PROJECT_NAME="$PROJECT_NAME $1"
            fi
            shift
            ;;
    esac
done

DATE=$(date +%Y-%m-%d)

# CDPATH must not redirect the cd that locates the sibling scripts.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE_DIR="$SKILL_ROOT/templates"

if [ "$TEMPLATE" != "default" ] && [ "$TEMPLATE" != "analytics" ]; then
    echo "Unknown template: $TEMPLATE (available: default, analytics). Using default."
    TEMPLATE="default"
fi

# Slug mode triggers when a project name was given OR --plan-dir was passed.
SLUG_MODE=0
if [ -n "$PROJECT_NAME" ] || [ "$USE_PLAN_DIR" -eq 1 ]; then
    SLUG_MODE=1
fi

slugify() {
    # Lowercase, non-alphanumerics → '-', collapse repeats, trim leading/trailing '-'
    printf '%s' "$1" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -e 's/[^a-z0-9]/-/g' -e 's/-\{2,\}/-/g' -e 's/^-//' -e 's/-$//' \
        | cut -c1-40
}

short_uuid() {
    # Probe each candidate: command -v alone is not enough on Windows because
    # App Execution Aliases report presence but exit non-zero when run.
    _py="${PYTHON_BIN:-}"
    if [ -z "$_py" ]; then
        for _c in python3 python py; do
            if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "import uuid" >/dev/null 2>&1; then
                _py="$_c"
                break
            fi
        done
    fi
    if [ -n "$_py" ]; then
        "$_py" -c "import uuid; print(uuid.uuid4().hex[:8])"
        return
    fi
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-8
        return
    fi
    # Last-ditch: seconds timestamp as 8 hex chars
    printf '%08x' "$(date +%s)" | cut -c1-8
}

gen_nonce() {
    # 16 hex chars for the plan-data delimiter framing (security strand rec 8).
    # short_uuid() yields 8 hex chars; concatenate two draws and clip to 16 so
    # the result stays exactly 16 even if a fallback path over-produces.
    _n1="$(short_uuid)"
    _n2="$(short_uuid)"
    # short_uuid's third-level fallback is printf '%08x' "$(date +%s)" with
    # 1-second resolution: two draws in the same second return the SAME 8 hex,
    # collapsing the nonce to the epoch value doubled (32 bits, not 64). When
    # the halves match, mix the PID into the second half so the nonce keeps 64
    # bits of unpredictability on the no-uuid fallback path (Alpine/minimal).
    if [ "$_n1" = "$_n2" ]; then
        printf '%08x%08x' "$(date +%s)" "$$" | tr -d '\n' | cut -c1-16
    else
        printf '%s%s' "$_n1" "$_n2" | tr -d '\n' | cut -c1-16
    fi
}

# Apply v3 opt-in mode side effects to a plan directory.
#   $1 = plan dir (absolute or relative); dotfiles live directly inside it.
#   $2 = plan file path (task_plan.md) used for auto-attestation resolution.
# No-op when MODE is empty (legacy path stays byte-equivalent to v2.43.0).
# Raise MODE to the project's committed floor before the side effects run
# (issue #238). A project that ships a root .mode has made that setting a
# reviewed part of the repo; a new slug plan must not start below it. Without
# this, `init-session.sh <name>` created a plan with no .mode at all, and the
# project's attestation requirement became a flag the agent chose at plan
# creation time.
#
# inject-plan.sh enforces the same floor at read time, so this is not the
# guard. It exists so the effective policy is VISIBLE in the plan directory
# rather than only inside the resolver, and so the new plan gets the nonce and
# the auto-attestation that autonomous mode needs to inject at all.
#
# An explicit --autonomous/--gated is never lowered: gated stays gated.
inherit_root_mode() {
    _root_mode="${PWD}/.mode"
    [ -f "${_root_mode}" ] || return 0
    [ "$MODE" = "gated" ] && return 0
    if grep -q 'gate' "${_root_mode}" 2>/dev/null; then
        MODE='gated'
        return 0
    fi
    if grep -q 'autonomous' "${_root_mode}" 2>/dev/null; then
        MODE='autonomous'
    fi
    return 0
}

apply_v3_mode() {
    _mode_dir="$1"
    _mode_plan="$2"
    [ -z "$MODE" ] && return 0

    # (a) reset the gate block counter and drop any stale gate ledger so a prior
    #     run's high block count cannot let the next run stop instantly.
    printf '0\n' > "${_mode_dir}/.stop_blocks"
    rm -f "${_mode_dir}/.gate_last_ledger" 2>/dev/null || true

    # (b) write a fresh 16-hex nonce for delimiter framing.
    gen_nonce > "${_mode_dir}/.nonce"

    # write the mode marker. gated implies autonomous, so it carries both tokens.
    if [ "$MODE" = "gated" ]; then
        printf 'autonomous gate\n' > "${_mode_dir}/.mode"
    else
        printf 'autonomous\n' > "${_mode_dir}/.mode"
    fi

    # (c) auto-attest the plan (attestation default-on in v3 modes, security
    #     strand rec 1). attest-plan.sh resolves the same way init-session just
    #     pinned things: in slug mode PLAN_ID points at this plan dir; in legacy
    #     mode it is empty and the script falls back to ./task_plan.md at root.
    #     Run from the project root (CWD here) so both resolutions land.
    _attest="${SCRIPT_DIR}/attest-plan.sh"
    if [ -f "${_attest}" ] && [ -f "${_mode_plan}" ]; then
        PWF_PLAN_ROOT="$PWD" PLAN_ID="${PLAN_ID:-}" sh "${_attest}" >/dev/null 2>&1 || true
    fi
}

write_default_task_plan() {
    cat > "$1" << 'EOF'
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
EOF
}

write_default_findings() {
    cat > "$1" << 'EOF'
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
EOF
}

write_default_progress() {
    local date_value="$1"
    local target="$2"
    cat > "$target" << EOF
# Progress Log

## Session: $date_value

### Current Status
- **Phase:** 1 - Requirements & Discovery
- **Started:** $date_value

### Actions Taken
-

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|

### Errors
| Error | Resolution |
|-------|------------|
EOF
}

write_analytics_progress() {
    local date_value="$1"
    local target="$2"
    cat > "$target" << EOF
# Progress Log

## Session: $date_value

### Current Status
- **Phase:** 1 - Data Discovery
- **Started:** $date_value

### Actions Taken
-

### Query Log
| Query | Result Summary | Interpretation |
|-------|---------------|----------------|

### Errors
| Error | Resolution |
|-------|------------|
EOF
}

create_files_in() {
    local target_dir="$1"
    local plan_path="$target_dir/task_plan.md"
    local findings_path="$target_dir/findings.md"
    local progress_path="$target_dir/progress.md"

    if [ ! -f "$plan_path" ]; then
        if [ "$TEMPLATE" = "analytics" ] && [ -f "$TEMPLATE_DIR/analytics_task_plan.md" ]; then
            cp "$TEMPLATE_DIR/analytics_task_plan.md" "$plan_path"
        else
            write_default_task_plan "$plan_path"
        fi
        echo "Created $plan_path"
    else
        echo "$plan_path already exists, skipping"
    fi

    if [ ! -f "$findings_path" ]; then
        if [ "$TEMPLATE" = "analytics" ] && [ -f "$TEMPLATE_DIR/analytics_findings.md" ]; then
            cp "$TEMPLATE_DIR/analytics_findings.md" "$findings_path"
        else
            write_default_findings "$findings_path"
        fi
        echo "Created $findings_path"
    else
        echo "$findings_path already exists, skipping"
    fi

    if [ ! -f "$progress_path" ]; then
        if [ "$TEMPLATE" = "analytics" ]; then
            write_analytics_progress "$DATE" "$progress_path"
        else
            write_default_progress "$DATE" "$progress_path"
        fi
        echo "Created $progress_path"
    else
        echo "$progress_path already exists, skipping"
    fi
}

if [ "$SLUG_MODE" -eq 1 ]; then
    SLUG="$(slugify "$PROJECT_NAME")"
    if [ -z "$SLUG" ]; then
        SLUG="untitled-$(short_uuid)"
    fi
    BASE_ID="${DATE}-${SLUG}"
    PLAN_ID="$BASE_ID"
    PLAN_ROOT="${PWD}/.planning"
    PLAN_SELECTOR="${SCRIPT_DIR}/set-active-plan.sh"
    if [ ! -f "${PLAN_SELECTOR}" ]; then
        echo "Error: set-active-plan.sh is required to create a named plan safely." >&2
        exit 1
    fi
    mkdir -p "${PLAN_ROOT}"
    # Verify the physical planning root and the existing pointer before
    # creating anything below it. A symlink or junction that escapes the
    # project must not redirect init writes, and a linked or non-regular
    # pointer must be refused before a plan directory exists on disk. The
    # selector's check is constant time; --list would parse every plan.
    if ! sh "${PLAN_SELECTOR}" --verify-root; then
        exit 1
    fi
    counter=2
    while [ -d "${PLAN_ROOT}/${PLAN_ID}" ]; do
        PLAN_ID="${BASE_ID}-${counter}"
        counter=$((counter + 1))
    done
    PLAN_DIR="${PLAN_ROOT}/${PLAN_ID}"
    mkdir -p "$PLAN_DIR"

    echo "Initializing planning files for: ${PROJECT_NAME:-untitled} (template: $TEMPLATE)"
    echo "PLAN_ID=$PLAN_ID"
    create_files_in "$PLAN_DIR"
    # Reuse the selector's contained, atomic pointer replacement. Direct shell
    # redirection would truncate a pre-existing hardlink and could overwrite a
    # different file that shares the same inode.
    if ! sh "${PLAN_SELECTOR}" "${PLAN_ID}" >/dev/null; then
        echo "Error: could not safely update ${PLAN_ROOT}/.active_plan." >&2
        exit 1
    fi
    inherit_root_mode
    apply_v3_mode "$PLAN_DIR" "${PLAN_DIR}/task_plan.md"
    echo ""
    echo "Active plan recorded: ${PLAN_ROOT}/.active_plan"
    echo "Pin this terminal to the plan for parallel sessions:"
    echo "  export PLAN_ID=$PLAN_ID"
    if [ -n "$MODE" ]; then
        echo "Mode: $(cat "${PLAN_DIR}/.mode") (attested, gate counter reset)"
    fi
else
    PROJECT_NAME="${PROJECT_NAME:-project}"
    echo "Initializing planning files for: $PROJECT_NAME (template: $TEMPLATE)"
    create_files_in "$(pwd)"
    apply_v3_mode "$(pwd)" "$(pwd)/task_plan.md"
    echo ""
    echo "Planning files initialized!"
    echo "Files: task_plan.md, findings.md, progress.md"
    if [ -n "$MODE" ]; then
        echo "Mode: $(cat "$(pwd)/.mode") (attested, gate counter reset)"
    fi
fi
