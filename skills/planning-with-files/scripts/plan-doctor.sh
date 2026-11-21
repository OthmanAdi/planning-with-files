#!/bin/sh
# planning-with-files: plan-doctor — one-pass self-check for the mechanisms
# that fail silently. Run from the project root:
#
#   sh scripts/plan-doctor.sh
#
# Answers:
#   - does plan resolution work here, and which plan wins?
#   - does hook injection actually emit plan context?
#   - is the canonicalizer producing comparable paths? (Windows-native
#     coreutils emit C:\-style output; pwf versions before v3.6.0 went
#     silently dark on such machines)
#   - is the plan attested, and is the attestation file where hooks look?
#   - which install surfaces exist on this machine?
#   - what does one hook fire cost in wall-clock?
#
# Diagnostic only. Writes nothing except inject-plan.sh's own SHA cache.
# Always exits 0.

set -u

_pwf_dir=$0
case "$_pwf_dir" in
    */*|*\\*)
        _pwf_tail=${_pwf_dir##*/}
        case "$_pwf_tail" in
            *\\*) _pwf_dir=${_pwf_dir%\\*} ;;
            *) _pwf_dir=${_pwf_dir%/*} ;;
        esac
        case "$_pwf_dir" in
            '') _pwf_dir=/ ;;
            [A-Za-z]:) _pwf_dir="${_pwf_dir}/" ;;
        esac
        ;;
    *) _pwf_dir=. ;;
esac
SCRIPT_DIR="$(cd "$_pwf_dir" 2>/dev/null && pwd 2>/dev/null)" || SCRIPT_DIR="."
unset _pwf_dir _pwf_tail

ok()   { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; }
info() { printf 'info  %s\n' "$1"; }

echo '=== planning-with-files plan-doctor ==='
info "cwd: ${PWD}"
info "uname: $(uname -s 2>/dev/null || echo unknown)"
[ "${PLANNING_DISABLED:-}" = "1" ] && warn "PLANNING_DISABLED=1 is set — every hook exits immediately in this environment"

# --- [1] canonicalizer probe -------------------------------------------------
CANON="$(realpath . 2>/dev/null)" || CANON=""
[ -z "${CANON}" ] && { CANON="$(readlink -f . 2>/dev/null)" || CANON=""; }
case "${CANON}" in
    '')
        warn "no realpath/readlink canonicalizer answered — containment falls back to a python spawn per check"
        ;;
    *\\*)
        info "canonicalizer emits Windows-style paths (${CANON}) — handled since v3.6.0; OLDER pwf versions resolve nothing on this machine"
        ;;
    *)
        info "canonicalizer: ${CANON}"
        ;;
esac

# --- [2] plan resolution -----------------------------------------------------
RES=""
if [ -f "${SCRIPT_DIR}/resolve-plan-dir.sh" ]; then
    RES="$(sh "${SCRIPT_DIR}/resolve-plan-dir.sh" 2>/dev/null)" || RES=""
    if [ -n "${RES}" ]; then
        ok "resolver: active plan dir = ${RES}"
    elif [ -f task_plan.md ]; then
        ok "resolver: legacy root plan (./task_plan.md)"
    elif [ -d .planning ]; then
        fail "resolver: .planning/ exists but nothing resolves — check .planning/.active_plan content and that plan dirs contain task_plan.md"
    else
        info "resolver: no plan in this directory (run init-session.sh to create one)"
    fi
else
    warn "resolve-plan-dir.sh not found next to plan-doctor — unexpected install layout"
fi

# Explicit format validation surfaces plans that inject as prose but cannot be
# tracked by the native phase/completion helpers. It never rewrites the plan.
FORMAT_PLAN=""
if [ -n "${RES}" ] && [ -f "${RES}/task_plan.md" ]; then
    FORMAT_PLAN="${RES}/task_plan.md"
elif [ -z "${PLAN_ID:-}${PWF_PLAN_ROOT:-}" ] && [ -f task_plan.md ]; then
    FORMAT_PLAN="task_plan.md"
fi
if [ -n "${FORMAT_PLAN}" ] && [ -f "${SCRIPT_DIR}/check-complete.sh" ]; then
    if FORMAT_OUT="$(sh "${SCRIPT_DIR}/check-complete.sh" --validate "${FORMAT_PLAN}" 2>&1)"; then
        ok "plan format: ${FORMAT_OUT}"
    else
        fail "plan format: ${FORMAT_OUT} Existing plan left unchanged; its owner must review the format."
    fi
fi

# Same selector inject-plan.sh uses, so the doctor and the injector agree on
# Python 3.8+. Sourcing returns before that script reads a plan. A stub or a
# doctor-only install defines no select_python; the injection section covers
# a missing injector.
if [ -f "${SCRIPT_DIR}/inject-plan.sh" ]; then
    . "${SCRIPT_DIR}/inject-plan.sh"
fi
if command -v select_python >/dev/null 2>&1; then
    if interpreter="$(select_python)"; then
        ok "interpreter: ${interpreter}"
    else
        fail "interpreter: none found; Claude Code plan injection needs Python 3.8 or newer"
    fi
fi

# --- [3] hook injection ------------------------------------------------------
INJ="${SCRIPT_DIR}/inject-plan.sh"
if [ -f "${INJ}" ]; then
    OUT="$(sh "${INJ}" --context=userprompt 2>/dev/null)" || OUT=""
    if [ -z "${OUT}" ]; then
        if [ -n "${RES}" ] || [ -f task_plan.md ]; then
            fail "injection: a plan resolves but inject-plan.sh emitted NOTHING — hooks are dark. Known silent causes: pre-v3.6.0 with a Windows-native realpath on PATH; PLANNING_DISABLED=1; a plan dir outside the project root; a stale .planning/sessions/ dir with no attached session (silences pretool/precompact fires entirely — the userprompt fire names it); no CPython 3.8+ on PATH."
        else
            ok "injection: silent because no plan exists here (correct behavior)"
        fi
    else
        # Classify on the DATA FRAMING first, never on substrings of the whole
        # blob (issue #236). ${OUT} carries the plan body VERBATIM inside
        # ===BEGIN-PWF-DATA=== fences, so a bare substring test also matches
        # plan prose: a phase line reading "fix the false PLAN TAMPERED
        # warning" made the doctor report a hash mismatch on a correctly
        # attested plan.
        #
        # Every refusal path in inject-plan.sh prints its banner and exits
        # before frame_file runs, so a frame in the output proves injection
        # happened and rules out every refusal. Output WITHOUT a frame is by
        # construction a notice, which is why the banner arms sit under the
        # else side and the default arm warns instead of passing. A banner
        # whose wording drifts then degrades to a generic warning rather than
        # to a silent PASS: that is exactly how the stale
        # "PWF_PLAN_ROOT is not a directory" literal (which was never a
        # substring of what inject-plan.sh emits) reported PASS on a fully
        # dark-hooks state.
        case "${OUT}" in
            *'===BEGIN-PWF-DATA'*)
                BYTES="$(printf '%s' "${OUT}" | wc -c | tr -d '[:space:]')"
                ok "injection: emits plan context (${BYTES} bytes)"
                ;;
            *'[PLAN TAMPERED'*)
                warn "injection: plan is attested but the hash mismatches — run /plan-attest (or scripts/attest-plan.sh) to re-approve the current plan"
                ;;
            *'requires attested plan'*)
                warn "injection: v3 mode without attestation — run attest-plan once to arm injection"
                ;;
            *'Session isolation is armed'*)
                warn "injection: session isolation refuses this session — attach it with PWF_SESSION_ID=<id> plus .planning/sessions/<id>.attached, or delete the .planning/sessions/ dir (stale ones survive earlier Codex use and copied project trees) to turn isolation off"
                ;;
            *'Ambiguous plan'*)
                warn "injection: nested-plan ambiguity — a project directly below this cwd carries its own plan, so hooks refuse to guess. Pin the thread with PWF_PLAN_ROOT=<absolute project root> or PLAN_ID=<slug>"
                ;;
            *'PWF_PLAN_ROOT is not a supported absolute local directory'*)
                warn "injection: PWF_PLAN_ROOT points at something that is not an absolute local directory — fix or unset the pin; a broken pin fails closed and injects nothing"
                ;;
            *'PLAN_ID does not name a plan directory'*)
                warn "injection: PLAN_ID names no plan directory under .planning — fix or unset the pin; a set PLAN_ID is a binding and fails closed rather than selecting another plan"
                ;;
            '[planning-with-files] Plan injection needs Python 3.8 or newer and no usable interpreter was found — nothing injected.')
                fail "injection: no usable Python 3.8 or newer interpreter was found"
                ;;
            '[planning-with-files] Plan injection could not verify the plan path: it needs realpath, readlink -f, or Python 3.8 or newer, and none was usable, so nothing was injected.')
                fail "injection: could not verify the plan path because realpath, readlink -f, and Python 3.8 or newer were all unavailable"
                ;;
            *)
                BYTES="$(printf '%s' "${OUT}" | wc -c | tr -d '[:space:]')"
                warn "injection: inject-plan.sh emitted ${BYTES} bytes but no ===BEGIN-PWF-DATA frame, so no plan context reached the model. This is a refusal notice this doctor does not recognize; read it directly with: sh scripts/inject-plan.sh --context=userprompt"
                ;;
        esac
    fi
else
    warn "inject-plan.sh not found next to plan-doctor — this install route ships no hook payload (see the install matrix in docs/installation.md)"
fi

# --- [4] attestation ---------------------------------------------------------
ATT=""
if [ -n "${RES}" ] && [ -f "${RES}/.attestation" ]; then
    ATT="${RES}/.attestation"
elif [ -f .plan-attestation ]; then
    ATT=".plan-attestation"
fi
if [ -n "${ATT}" ]; then
    info "attestation present: ${ATT}"
else
    info "attestation: none (opt-in in legacy mode; default-on in v3 modes; run /plan-attest after approving the plan)"
fi

# --- [5] install surfaces ----------------------------------------------------
FOUND_SURFACE=0
for s in \
    ".claude/skills/planning-with-files" \
    "${HOME:-}/.claude/skills/planning-with-files" \
    ".agents/skills/planning-with-files" \
    "${HOME:-}/.agents/skills/planning-with-files"
do
    [ -n "${s}" ] && [ -d "${s}" ] && { info "install surface present: ${s}"; FOUND_SURFACE=1; }
done
[ "${FOUND_SURFACE}" = "0" ] && info "no skill-dir install surface in project or home (plugin-route installs live under the plugin cache instead)"
info "route reminder: the plugin route ships commands/ + hooks; npx-skills ships the skill only. Hooks silent after a project-level skill install? Check project trust (hasTrustDialogAccepted) and the install matrix in docs/installation.md."

# --- [6] hook latency --------------------------------------------------------
if [ -f "${INJ}" ]; then
    T0="$(date +%s%N 2>/dev/null)" || T0=""
    sh "${INJ}" --context=userprompt >/dev/null 2>&1
    T1="$(date +%s%N 2>/dev/null)" || T1=""
    case "${T0}${T1}" in
        ''|*[!0-9]*)
            info "hook latency: skipped (no nanosecond clock on this date binary)"
            ;;
        *)
            MS=$(( (T1 - T0) / 1000000 ))
            info "one inject-plan.sh fire: ${MS}ms wall-clock"
            ;;
    esac
fi

echo '=== plan-doctor done ==='
exit 0
