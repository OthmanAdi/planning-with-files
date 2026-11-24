# Performance Notes

## Repeated plan context

Since v3.24.0, Claude Code's plugin and standalone skill hooks suppress an
unchanged PreToolUse view when a usable session identity and private cache are
available. UserPromptSubmit still injects the selected plan and progress once
per prompt. It records the corresponding tool view from the same validated
snapshot, so subsequent matched tool calls do not append it again.

A change within the emitted view refreshes it once. The cache distinguishes
sessions, agents, selected plans and rendering modes. A plain head contains
30 lines; editing a later line does not change that view. `PWF_INJECT=smart`
selects a structured view, which can be larger than the plain head when the
active phase is long. It is not a fixed token budget.

The suppression cache stores hashes rather than plan content under
`${XDG_CACHE_HOME:-$HOME/.cache}/pwf-pretool`. Recovery events invalidate the
session's entry. Missing identity or an unsafe or unavailable cache preserves
repeated injection. Use `PWF_PRETOOL=always` in the host's environment to keep
the per-call behavior. This controls repeated context, not plan selection or
attestation: those checks still run on every call. Autonomous and gated modes
continue to omit PreToolUse context.

This reduces repeated context bytes. It does not remove hook process startup
or promise a fixed token saving for every plan.

## Attestation hash

When plan attestation is enabled, the hooks compare the approved SHA-256 hash
with the current `task_plan.md` before injecting plan content.

### Per-fire hashing

Each hook fire reads the plan once into a private snapshot. When the plan is
attested, the fire hashes that snapshot with `sha256sum` (or `shasum -a 256`)
and checks the attestation against those exact bytes. Everything the fire
injects from the plan is read from the same snapshot, so replacing
`task_plan.md` during the fire cannot pass a different plan through. For the
shell hook this assumes a private snapshot directory that only your user
controls (see Snapshot location below): the hook does not check who owns the
directory, and anyone else who can write to it could replace the snapshots the
fire hashes and injects. No
attestation digest is reused between fires: a whole-second mtime and a cached
digest are not trust signals, because `task_plan.md` can change while keeping
both.

The implementation is the attestation check in `scripts/inject-plan.sh` and its
one-process twin `scripts/inject-plan.py`, which holds the plan snapshot in
memory and hashes it with `hashlib`. On the shell route,
`test_attested_fire_uses_and_cleans_private_snapshot` in
`tests/test_hook_body_v240.py` asserts that an attested fire creates no
`pwf-sha` directory and leaves the snapshot directory empty.

### Snapshot location

The shell hook writes snapshots under the first of these that resolves:

```bash
$XDG_CACHE_HOME/pwf-snapshots/             # when XDG_CACHE_HOME is set
$HOME/.cache/pwf-snapshots/                # otherwise, when HOME is set
${TMPDIR:-/tmp}/pwf-snapshots-${UID:-user}/ # fallback only when neither is set
```

The hook creates the directory under umask 077, attempts `chmod 700` on it, and
refuses it if it is a symlink. Each snapshot is a `mktemp` file that the hook
removes when it exits, so the directory is normally empty between fires and
needs no clearing. If the directory cannot be created or written, or the plan
is larger than 4 MiB, the hook injects nothing. The Python twin applies the same
directory checks before reading the plan.

### Cost

An attested fire hashes the whole plan, up to the 4 MiB limit, every time. On
Windows Git Bash the cost of a fire is dominated by process startup, which is
what `scripts/inject-plan.py` addresses by doing the whole fire in one
interpreter.

### Older `pwf-sha` directories

v2.40.0 added an mtime-keyed digest cache under `${TMPDIR:-/tmp}/pwf-sha/`, and
v3.0.0 moved it to `${XDG_CACHE_HOME:-$HOME/.cache}/pwf-sha/`. Current hooks
neither read nor write that directory. A leftover one in your cache directory
can be deleted:

```bash
rm -rf -- "${XDG_CACHE_HOME:-$HOME/.cache}/pwf-sha"
```

A `/tmp/pwf-sha` left by v2.40 sits in a shared directory. Check it with
`ls -ld /tmp/pwf-sha` and delete it only if it is a directory you own, not a
symlink.
