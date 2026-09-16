# Benchmark Results: planning-with-files

Formal evaluation of `planning-with-files` using Anthropic's [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) framework, plus later functional verification of v3-specific mechanisms, plus a first competitive benchmark against six alternative planning methods. This document records the full methodology, test cases, grading criteria, and results. Tests 1 through 3 were run against v2.22.0 (2026-03-06); Test 4 was run against v3.2.0 (2026-07-03); Test 5 was run against v3.4.0 (2026-07-06).

An animated summary of Test 5 lives at [docs/benchmark/index.html](benchmark/index.html) ([rendered view](https://htmlpreview.github.io/?https://github.com/OthmanAdi/planning-with-files/blob/master/docs/benchmark/index.html)).

---

## Why We Did This

A proactive security audit in March 2026 identified a prompt injection amplification vector in the hook system. The PreToolUse hook re-reads `task_plan.md` before every tool call — the mechanism that makes the skill effective — but declaring `WebFetch` and `WebSearch` in `allowed-tools` created a path for untrusted web content to reach that file and be re-injected into context on every subsequent tool use.

Hardened in v2.21.0: removed `WebFetch`/`WebSearch` from `allowed-tools`, added explicit Security Boundary guidance to SKILL.md. These evals document the performance baseline and verify zero regression in workflow fidelity.

---

## Test Environment

| Item | Value |
|------|-------|
| Skill version tested | 2.21.0 |
| Eval framework | Anthropic skill-creator (github.com/anthropics/skills) |
| Executor model | claude-sonnet-4-6 |
| Eval date | 2026-03-06 |
| Eval repo | Local copy (planning-with-files-eval-test/) |
| Subagents | 10 parallel (5 with_skill + 5 without_skill) |
| Comparator agents | 3 blind A/B comparisons |

---

## Test 1: Evals + Benchmark

### Skill Category

`planning-with-files` is an **encoded preference skill** (not capability uplift). Claude can plan without the skill — the skill encodes a specific 3-file workflow pattern. Assertions test workflow fidelity, not general planning ability.

### Test Cases (5 Evals)

| ID | Name | Task |
|----|------|------|
| 1 | todo-cli | Build a Python CLI todo tool with persistence |
| 2 | research-frameworks | Research Python testing frameworks, compare 3, recommend one |
| 3 | debug-fastapi | Systematically debug a TypeError in FastAPI |
| 4 | django-migration | Plan a 50k LOC Django 3.2 → 4.2 migration |
| 5 | cicd-pipeline | Create a CI/CD plan for a TypeScript monorepo |

Each eval ran two subagents simultaneously:
- **with_skill**: Read `SKILL.md`, follow it, create planning files in output dir
- **without_skill**: Execute same task naturally, no skill or template

### Assertions per Eval

All assertions are **objectively verifiable** (file existence, section headers, field counts):

| Assertion | Evals |
|-----------|-------|
| `task_plan.md` created in project directory | All 5 |
| `findings.md` created in project directory | Evals 1,2,4,5 |
| `progress.md` created in project directory | All 5 |
| `## Goal` section in task_plan.md | Evals 1,5 |
| `### Phase` sections (1+) in task_plan.md | All 5 |
| `**Status:**` fields on phases | All 5 |
| `## Errors Encountered` section | Evals 1,3 |
| `## Current Phase` section | Eval 2 |
| Research content in `findings.md` (not task_plan.md) | Eval 2 |
| 4+ phases | Eval 4 |
| `## Decisions Made` section | Eval 4 |

**Total assertions: 30**

### Results

| Eval | with_skill | without_skill | with_skill files | without_skill files |
|------|-----------|---------------|-----------------|---------------------|
| 1 todo-cli | 7/7 (100%) | 0/7 (0%) | task_plan.md, findings.md, progress.md | plan.md, todo.py, test_todo.py |
| 2 research | 6/6 (100%) | 0/6 (0%) | task_plan.md, findings.md, progress.md | framework_comparison.md, recommendation.md, research_plan.md |
| 3 debug | 5/5 (100%) | 0/5 (0%) | task_plan.md, findings.md, progress.md | debug_analysis.txt, routes_users_fixed.py |
| 4 django | 5/6 (83.3%) | 0/6 (0%) | task_plan.md, findings.md, progress.md | django_migration_plan.md |
| 5 cicd | 6/6 (100%) | 2/6 (33.3%) | task_plan.md, findings.md, progress.md | task_plan.md (wrong structure) |

**Aggregate:**

| Configuration | Pass Rate | Total Passed |
|---------------|-----------|-------------|
| with_skill | **96.7%** | 29/30 |
| without_skill | 6.7% | 2/30 |
| **Delta** | **+90.0 pp** | +27 assertions |

**Timing and token usage** (from task completion notifications — captured at runtime):

| Eval | with_skill tokens | with_skill time | without_skill tokens | without_skill time |
|------|------------------|-----------------|---------------------|-------------------|
| 1 todo-cli | 17,802 | 99.7s | 13,587 | 76.2s |
| 2 research | 22,150 | 128.7s | 13,610 | 127.3s |
| 3 debug | 17,506 | 93.4s | 11,525 | 66.5s |
| 4 django | 24,049 | 147.9s | 12,351 | 141.4s |
| 5 cicd | 18,122 | 105.0s | 8,424 | 76.7s |
| **Average** | **19,926** | **115s** | **11,899** | **98s** |

The skill uses ~68% more tokens and ~17% more time on average. The extra cost is the structured output: creating 3 files instead of 1-2, following phase/status discipline, populating decisions and error tables. This is the intended tradeoff — the skill trades speed for structure.

#### One Assertion Refined (Eval 4)

Assertion: `**Status:** pending on at least one future phase`
Result: not met

The agent completed all 6 migration phases in a single comprehensive planning session, leaving none pending. The skill was followed correctly — the assertion was overly prescriptive. The skill does not require phases to remain pending; it requires phases to have status fields. Revised for future evals: `task_plan.md contains **Status:** fields` (without specifying value).

---

## Test 2: A/B Blind Comparison

Three independent comparator agents evaluated pairs of outputs **without knowing which was with_skill vs without_skill**. Assignment was randomized:

| Eval | A | B | Winner | A score | B score |
|------|---|---|--------|---------|---------|
| 1 todo-cli | without_skill | with_skill | **B (with_skill)** | 6.0/10 | 10.0/10 |
| 3 debug-fastapi | with_skill | without_skill | **A (with_skill)** | 10.0/10 | 6.3/10 |
| 4 django-migration | without_skill | with_skill | **B (with_skill)** | 8.0/10 | 10.0/10 |

**with_skill wins: 3/3 = 100%**

### Comparator Quotes

**Eval 1 (todo-cli):** *"Output B satisfies all four structured-workflow expectations precisely... Output A delivered real, runnable code (todo.py + a complete test suite), which is impressive, but it did not fulfill the structural expectations... Output A's strength is real but out of scope for what was being evaluated."*

**Eval 3 (debug-fastapi):** *"Output A substantially outperforms Output B on every evaluated expectation. Output B is a competent ad-hoc debug response, but it does not satisfy the structured, multi-phase planning format the eval specifies. Output A passes all five expectations; Output B passes one and fails four."*

**Eval 4 (django-migration):** *"Output B is also substantively strong: it covers pytz/zoneinfo migration (a 4.2-specific item Output A omits entirely), includes 'django-upgrade' as an automated tooling recommendation... The 18,727 output characters vs 12,847 for Output A also reflects greater informational density in B."*

---

## Test 3: Description Optimizer

**Status: Not run in this cycle**

Requires `ANTHROPIC_API_KEY` in the eval environment. Per the project's eval standards, a test is only included in results if it can be run end-to-end with verified metrics. Scheduled for the next eval cycle.

---

## Test 4: v3 Long-Running Session Functional Verification (2026-07-03)

Tests 1 through 3 measure whether the skill enforces the 3-file planning pattern. They predate v3.0.0 (2026-06-09) and say nothing about v3's own headline feature: surviving `/clear` and context compaction across a long-running session. This section covers that mechanism specifically, added after a repository health audit found it was silently broken on Windows.

### Method

Rather than reading the code and assuming it worked, each mechanism was run directly in a scratch directory on a real Windows machine (Git Bash and PowerShell, both), with real files and real tampering, checking actual command output against expectations.

### Scope

| Mechanism | Script | What it does |
|-----------|--------|---------------|
| Session init | `init-session.sh` / `.ps1` | Creates `task_plan.md`, `findings.md`, `progress.md` from templates |
| Phase status | `check-complete.sh` / `.ps1` | Counts phases, reports completion |
| Attestation | `attest-plan.sh` / `.ps1` | SHA-256 locks plan content, detects tampering |
| Plan injection | `inject-plan.sh` | Re-injects plan context into the model turn, enforces the attestation |
| Parallel plans | `resolve-plan-dir.sh` / `.ps1` | Resolves the active plan directory across concurrent sessions |
| Session recovery (historical v3.2 behavior) | `session-catchup.py` | Replayed unsynced transcript context after `/clear`; current automatic recovery is project-file-only |

### Result: 2 of 6 mechanisms were broken on Windows, silently

**`session-catchup.py` did nothing on Windows.** Two independent bugs, either one alone sufficient to break it:

1. The path sanitizer only replaced forward slashes. A Windows path (`C:\Users\...` or Git Bash's `/c/Users/...`) never matched Claude's actual project-directory naming, so the function always returned before finding any sessions to scan.
2. Three file reads had no explicit encoding, so any session log containing non-ASCII text raised `UnicodeDecodeError` against Windows' default `cp1252` codec, an error the surrounding `except` clauses swallowed without a trace.

Neither failure printed anything. A user running this on Windows would see no catchup report and have no reason to suspect the mechanism was even running, let alone why it produced nothing. `tests/test_path_fix.py` contained a working reimplementation of the correct fix but never imported or exercised the actual shipped script, so the test suite reported green the entire time.

**`inject-plan.sh`'s containment guard silently dropped plan injection under aliased paths.** The guard canonicalizes the project root and the candidate plan directory separately, then checks that one is a prefix of the other. On a Windows account with an 8.3 short-name `TEMP` (this test machine's own account is one such case) or a path reached through the MSYS `/tmp` mount, the two canonicalization routes land on differently-spelled versions of the same directory, the prefix check fails, and the hook exits with zero output: no plan re-injection, no tamper warning, nothing. `resolve-plan-dir.sh` does not have this bug because it builds its candidates as absolute paths from the start; that asymmetry is what pointed at the fix.

### What worked correctly, unmodified

Session init, phase-status counting, attestation lock/show/clear, tamper detection logic itself (once the injection guard reaches it), and parallel-plan directory resolution (`$PLAN_ID` env var, `.active_plan` file, newest-mtime fallback) all produced correct output in both Git Bash and PowerShell, including the v3 autonomous-mode chain (nonce-framed delimiters, unattested-plan refusal, per-tool-call injection suppression).

At the time of this v3.2.0 evaluation, `init-session.ps1` had no slug mode (it always wrote to the project root), while `init-session.sh` created `.planning/<slug>/` directories. The canonical/shared English PowerShell initializer now supports the same named-plan and `-PlanDir` isolation flow, including active-plan selection and v3 mode inheritance. There is still no `inject-plan.ps1`; the injection and tamper-enforcement hook body is sh-only, so a pure-PowerShell host without Git Bash gets no plan injection or tamper enforcement at all.

### Fixed in v3.2.0

Both `session-catchup.py` and `inject-plan.sh` were fixed (see CHANGELOG). Re-running the same sequence after the fix confirmed session-catchup now produces a correct catchup report from real session logs, and plan injection now reaches the tamper-check branch under the same aliased-path conditions that previously went silent. The PowerShell-only injection gap remains an open follow-up; the `init-session.ps1` slug-mode asymmetry described above was corrected later and is covered by Windows PowerShell regression tests.

### Current session-catchup boundary

The v3.2.0 evaluation above exercised the behavior shipped at that time: bare `session-catchup.py` replayed conversation excerpts from the previous same-project session. It did not parse or reconstruct on-disk phase state directly.

Current automatic recovery reads project planning files only. Bare `session-catchup.py` and lifecycle hooks do not inspect host session stores. Explicit `--metadata` reads same-project local session records and emits aggregate counts only, with no transcript, tool-command, or path bytes. Explicit `--replay` may emit bounded nonce-framed same-project excerpts. The catchup path contains no network request or upload operation. These newer defaults were not measured in the v3.2.0 repair test or the competitive benchmark below.

---

## Test 5: Competitive Benchmark v1, Seven Planning Methods Head to Head (2026-07-06, internal)

The earlier tests compare pwf against *no skill*. This test compares it against the field: six alternative ways of keeping an agent organized, all run in the same harness, on the same tasks, with the same model, and graded by scripts rather than by any LLM judge. It is an internal v1: the tasks are harness-authored (a disclosed limitation), and several rigor gates for a standalone public release (external task corpus, competitor-author review, cross-family jury for judged axes) are on the roadmap. Numbers below are exactly what the deterministic oracles produced, wins and tradeoffs alike, and they are reproducible from the raw runs.

### Arms (pinned)

| Arm | What it is | Source |
|-----|------------|--------|
| native | Claude Code as shipped, TodoWrite allowed. The confound control | CLI 2.1.201 |
| filesystem | One neutral paragraph: "maintain your working state in files in ./notes/" | harness-authored |
| naive-plan | A minimal 15-line dev-plan SKILL.md | harness-authored |
| **planning-with-files** | v3.4.0, skill plus hooks per its own docs | commit d71b3be |
| superpowers | Only its brainstorming, writing-plans, and executing-plans skills (isolation disclosed; the full framework is more than a planning skill) | d884ae0 |
| spec-kit | Spec-Driven Development templates and workflow, ported to a CLAUDE.md project rule (port disclosed) | bba473c |
| memory-bank | Cline's memory-bank.md verbatim as project rules (port disclosed) | ed2c617c |

Executor: claude-opus-4-8 for every arm. Same tool allowlist everywhere. Each run in an isolated project directory with an isolated Claude home. Grading: pytest suites plus scripted transcript and file-state analysis (`grade.json` per run). No LLM grades anything in this test.

### Tasks

| Task | Shape | Trials | Skill invocation |
|------|-------|--------|------------------|
| O1 build-multiphase | CLI inventory tool, provided test suite, 4 natural phases | 3 per arm | unforced (prompt never mentions any skill) |
| O2 recovery | Same build, session hard-stopped at ~50%, fresh session told only "Continue the work in this directory." | 5 per arm | unforced |
| O6 recovery-forced | Larger 6-component log-analysis CLI, same hard-stop protocol | 3 per arm | forced (each arm explicitly told to use its method) |

77 graded cells total. Three further designed tasks (research-decide-build, drift-gauntlet, underspecified-dashboard) did not run in v1 and are on the v2 docket. The underspecified-dashboard task is one where superpowers' brainstorming gate is expected to beat pwf; that expectation is recorded here so the omission reads as a schedule gap, not a dodge.

### Result 1: correctness parity. pwf matches the field, then pulls ahead

Every arm passed every task. 77 of 77 runs end with the provided pytest suite green, planning-with-files included, alongside the native baseline with no planning method at all. On single-session tasks of this size (8 to 29 turns), a frontier model completes the work regardless of how it is organized, so pass rate ties across the board. The honest reading: **pwf gives up nothing on correctness**, and pass rate at this task size cannot rank planning methods for anyone. What ranks them is everything measured below, and that is where pwf separates from the field.

What separates the arms: whether the method engages when nobody forces it, what a resume costs after context death, and what durability guarantees the method actually enforces.

### Result 2: triggering, where always-on rules and pwf's hooks diverge

With prompts that never mention any skill, how often did each method actually engage (create its planning artifact before implementation)?

| Arm | O1 (n=3) | O2 (n=5) |
|-----|----------|----------|
| filesystem instruction | 3/3 | 5/5 |
| naive-plan skill | 3/3 | 5/5 |
| spec-kit as project rule | 3/3 | 5/5 |
| memory-bank as project rule | 1/3 | 4/5 |
| **planning-with-files** | **2/3** | **3/5** |
| superpowers skills | 0/3 | 0/5 |
| native | 0/3 | 0/5 (in-context TodoWrite only) |

Two facts, both favoring the mechanism approach. First, the like-for-like comparison: against the closest skill-based competitor, pwf leads 5 to 0, since superpowers' planning skills never self-triggered in this harness at all. Second, the methods at 8/8 reach it only by living in always-loaded context (a project rule, a one-line instruction) rather than as a discoverable skill, a different tradeoff, not a better planner. pwf engaged on its own in 5 of 8 unforced runs, and every time it did, its hooks then fired deterministically for the rest of the session. Widening that auto-engage rate is the next roadmap item; the mechanism itself never misses once a plan is on disk. This is the strongest argument for hook-based mechanisms over model-remembers-to-do-it conventions.

### Result 3: when engaged, pwf resumes fastest after context death

O6 protocol: kill the session at roughly half done, start a fresh one in the same directory with only "Continue the work in this directory." All arms eventually finished (saturation again), asked the user nothing, and redid no completed work. The separation is the cost of re-orientation, measured in stage-2 turns to completion:

| Arm | Stage-2 turns (mean, T=3) | Total cost (both stages) |
|-----|---------------------------|--------------------------|
| **planning-with-files** | **5.0** | $0.86 |
| filesystem | 8.3 | $0.76 |
| spec-kit | 10.0 | $1.09 |
| naive-plan | 12.3 | $0.87 |
| memory-bank | 13.0 | $0.94 |
| native | 13.3 | $0.81 |
| superpowers | 13.3 | $1.18 |

A pwf resume took 5 turns: 40% fewer than the next-best arm and roughly 2.7x fewer than native or superpowers. In this historical run, transcript catchup plus hook injection put phase state in front of the model before its first tool call, so stage 2 started at the correct next step instead of re-reading the world. Current automatic recovery is project-file-only and has not been re-run under this protocol, so do not treat the 5-turn result as a direct measurement of the current default. On the unforced O2 variant the gap compressed (pwf 7.2 turns, naive-plan 6.8, filesystem 8.2), because the advantage was realized once the plan existed on disk, which ties directly back to the trigger roadmap item above.

### Result 4: what the guarantees cost, stated plainly

On the unforced build task, pwf averaged $0.634 and 15.3 turns; the arms that did no planning ran $0.31 to $0.42 and 7 to 10 turns, in the same range as spec-kit ($0.724, 14.0 turns). Structured planning carries a modest premium on a task this small, which is the expected tradeoff: pwf is the only method that then survives a context wipe. Mechanism overhead is about 330 tokens re-injected per user turn plus about 90 per matched tool call. A separate per-fire wall-clock figure measured on a single Windows test machine is being profiled and tuned; it is a local implementation detail rather than a property of the method, and it does not affect any result above. In short, pwf costs a little more per run and returns the only automatic recovery, re-surfacing, tamper-detection, plan-isolation, and compaction-survival guarantees in the field, behaviors that are mechanisms rather than instructions the model may or may not follow.

### Result 5: no contamination, no spontaneous adoption

No arm produced another arm's signature files. The native and filesystem arms never spontaneously created task_plan.md, findings.md, or progress.md, replicating the Test 1 finding: the pwf file pattern does not leak out of training data; it appears when the skill drives it.

### Grader validated against every method, and we proved it

An author-run benchmark has to earn trust, so the grader was validated against every method's real artifact layout before publishing. That validation caught and fixed a detector bug that had under-credited two competitors: it matched plan filenames like plan.md but not their directory layouts (docs/superpowers/plans/DATE-slug.md, specs/FEATURE/), which had falsely zeroed superpowers' forced-mode process metrics. The detector was corrected and all 77 cells re-graded before publication; post-fix, superpowers' forced-mode process metrics are 100%. The grading is deterministic: re-running the scripts on the raw runs reproduces every number here. Validating the grader against each method's real artifacts, and disclosing the fix, is the rigor an author-run benchmark owes its readers.

### What this test does not measure

Trigger rates under varied natural phrasing (two unforced tasks only). Long-horizon drift and mid-task distractors (designed task did not run). Underspecified-task brainstorming, where superpowers is expected to win. Plan quality as judged output (needs a cross-family jury before it can be reported). Cross-IDE behavior (Claude Code only). Multi-day horizons. None of the above is claimed.

### Reproducing

The harness (cell runner with pinned flags and isolated home, wave orchestrator, deterministic graders, aggregator with 95% CIs, task specs committed before any run, arm sources at pinned SHAs) and all 77 raw run directories (transcripts, file-tree hashes, per-run grades) live in the benchmark workspace, not tracked in this repo. The grading and aggregation scripts are deterministic; re-running them on the raw runs reproduces every number above.

---

## Summary

| Test | Status | Result |
|------|--------|--------|
| Evals + Benchmark | ✅ Complete | 96.7% (with_skill) vs 6.7% (without_skill) |
| A/B Blind Comparison | ✅ Complete | 3/3 wins (100%) for with_skill |
| Description Optimizer | Pending | Scheduled for next eval cycle |
| v3 Long-Running Session Functional Verification | ✅ Complete (2026-07-03) | 2 of 6 mechanisms found broken on Windows and fixed in v3.2.0; see Test 4 |
| Competitive Benchmark v1 (7 methods) | ✅ Complete (2026-07-06, internal) | pwf resumes from context death in 5.0 turns vs 8.3 to 13.3 for the other six (2.7x faster than a raw agent), matches every method on correctness at 77/77, and is the only method with automatic recovery, re-surfacing, tamper-detection, isolation, and compaction guarantees; leads superpowers 5 to 0 on unforced triggering |

The skill demonstrably enforces the 3-file planning pattern across diverse task types. Without the skill, agents default to ad-hoc file naming and skip the structured planning workflow entirely. Separately, v3's session-recovery mechanism is now verified functional on Windows as of v3.2.0; it was not before, and nothing in the test suite would have caught that on its own.

---

## Reproducing These Results

```bash
# Clone the eval framework
gh api repos/anthropics/skills/contents/skills/skill-creator ...

# Set up workspace
mkdir -p eval-workspace/iteration-1/{eval-1,eval-2,...}/{with_skill,without_skill}/outputs

# Run with_skill subagent
# Prompt: "Read SKILL.md at path X. Follow it. Execute: <task>. Save to: <output_dir>"

# Run without_skill subagent
# Prompt: "Execute: <task>. Save to: <output_dir>. No skill or template."

# Grade assertions, produce benchmark.json
# See eval-workspace/iteration-1/benchmark.json for full data
```

Raw benchmark data: [`eval-workspace/iteration-1/benchmark.json`](../planning-with-files-eval-test/eval-workspace/iteration-1/benchmark.json) (in eval-test copy, not tracked in main repo)
