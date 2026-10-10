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

## Attestation SHA cache

When plan attestation is enabled, the hooks compare the approved SHA-256 hash
with the current `task_plan.md` before injecting plan content. v2.40.0 added a
small transient cache for that hash calculation.

### Location

The cache lives under the first of these that resolves:

```bash
$XDG_CACHE_HOME/pwf-sha/        # when XDG_CACHE_HOME is set
$HOME/.cache/pwf-sha/           # otherwise, when HOME is set
${TMPDIR:-/tmp}/pwf-sha/        # fallback only when neither is set
```

v2.40.0 introduced the cache under `${TMPDIR:-/tmp}/pwf-sha/`. v3.0.0 moved it to
the user-private path above so a world-writable `/tmp` can no longer be used to
poison the attestation hash. Each cache entry stores the plan file mtime on the
first line and the computed SHA-256 on the second line.

### Keying

The cache key is the first 16 hex characters of the SHA-256 of the active plan
file path (the path string, not the file contents). Each plan location gets its
own entry:

```text
task_plan.md
.planning/<plan-id>/task_plan.md
```

The stored hash is reused only when the current plan file mtime matches the
cached mtime. If the file changes, the hook recomputes `sha256sum` or
`shasum -a 256` and rewrites the cache entry. In gated mode the hook always
recomputes on a hit, so the completion gate never trusts a stale entry.

### When it helps

The cache is most useful when:

- Plan files are large.
- Windows Git Bash process startup makes repeated `sha256sum` calls expensive.
- The same attested plan fires hooks many times in one session.

### When it is break-even

For small plan files, the cache may be roughly break-even. The hook still starts
shell commands, reads the cache entry, and checks the mtime. On those paths,
Bash process startup can dominate the actual hash cost.

### Containers and CI

The cache is per-user and transient. In a container `HOME` is usually set (for
example `/root`), so the cache lives at `$HOME/.cache/pwf-sha/`. Containers, CI
jobs, and sandboxes that do not persist `$HOME` across restarts lose the cache
between runs.

That only affects speed. A cache miss recomputes the SHA-256 from the current
plan file and preserves the same attestation behavior.

### Clear or avoid reuse

Clear the cache:

```bash
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/pwf-sha/"
```

There is no separate SHA-cache toggle, and overriding `TMPDIR` does not move the
cache when `HOME` is set. The cache self-invalidates whenever the plan file mtime
changes, so editing `task_plan.md` already forces a recompute. To force a clean
state explicitly, remove the directory above.
