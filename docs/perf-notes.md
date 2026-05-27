# Performance Notes

## Attestation SHA cache

When plan attestation is enabled, the hooks compare the approved SHA-256 hash
with the current `task_plan.md` before injecting plan content. v2.40.0 added a
small transient cache for that hash calculation.

### Location

The cache lives under:

```bash
${TMPDIR:-/tmp}/pwf-sha/
```

Each cache entry stores the plan file mtime on the first line and the computed
SHA-256 on the second line.

### Keying

The cache key is derived from the active plan file path:

```text
task_plan.md
.planning/<plan-id>/task_plan.md
```

The stored hash is reused only when the current plan file mtime matches the
cached mtime. If the file changes, the hook recomputes `sha256sum` or
`shasum -a 256` and updates the cache entry.

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

The cache is per-system and transient. Containers, CI jobs, and sandboxes often
use a non-persistent `/tmp`, so `${TMPDIR:-/tmp}/pwf-sha/` disappears across
restarts.

That only affects speed. A cache miss recomputes the SHA-256 from the current
plan file and preserves the same attestation behavior.

### Clear or avoid reuse

Clear the cache:

```bash
rm -rf "${TMPDIR:-/tmp}/pwf-sha/"
```

There is no separate SHA-cache toggle. To avoid reuse for a single shell
session, run the agent with a fresh `TMPDIR`:

```bash
TMPDIR="$(mktemp -d)" claude
```
