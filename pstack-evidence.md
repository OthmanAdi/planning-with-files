# pstack evidence — pwf #344

## Principles applied
- Laziness Protocol: pre-tool scripts become unconditional `{}` (smallest change that matches the documented PreToolUse contract).
- Prove It Works: subprocess schema + opt-out tests assert stdout shapes; manual shell probe for nonempty/empty/missing/disabled.
- Test Behavior, Not Implementation: assert host-visible JSON, not internal script structure.

## Repro → fix
Before: nonempty plan emitted nested `hookSpecificOutput.permissionDecision=allow` + `additionalContext`.
After: all four cases emit `{}` with no nested permission/context fields.
Docs no longer claim pre-tool injects the plan; sessionStart/post-tool remain the context routes.
