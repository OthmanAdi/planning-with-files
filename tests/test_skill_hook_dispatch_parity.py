"""Hook-dispatch parity across every hooks-bearing SKILL.md (issue #212).

Through v2.43 the UserPromptSubmit / PreToolUse / PreCompact hook bodies were
giant inline sh scalars embedded in the SKILL.md frontmatter. v3 moved that
logic into scripts/inject-plan.sh and reduced the canonical scalars to thin
self-discovery dispatchers — but only the canonical file and the .agents mirror
were converted. The eleven other hook-bearing variants (six IDE mirrors plus
five language variants) kept the frozen v2.43 inline body, so every fix that
landed in inject-plan.sh after the split silently never reached users who
installed one of those variants. The reporter of #212 installed .codex and got
a "fixed" bug.

The first conversion of those eleven used ``ls a b c | head -1`` for discovery.
Adversarial review found three silent-failure holes in it:

  1. ``ls | head -1`` SORTS its output, so with several copies installed the
     alphabetically-first path won (the .claude marketplace copy) instead of
     the documented priority order. Fixed: a POSIX first-match-wins loop
     (``for c in ...; do [ -f "$c" ] && { SH="$c"; break; }; done``).
  2. Workspace installs (the RECOMMENDED method for CodeBuddy/Factory, the
     only documented method for Cursor) resolve to nothing: no candidate is
     project-local, deliberately (a repo-relative candidate would let any
     cloned repo plant the script the hook executes). Fixed: the opt-in
     ``PWF_SCRIPT_DIR`` escape hatch is the FIRST candidate — the user sets it
     once, pointing at the skill's scripts dir.
  3. Nothing installed = total silence. Fixed: the UserPromptSubmit scalar
     emits exactly one not-found notice; PreToolUse/PreCompact (fire per tool
     call) and Stop (carries no plan body) deliberately stay silent.

This test makes those regressions impossible to reintroduce: every tracked
SKILL.md that declares a hooks: frontmatter block must dispatch its injection
hooks to inject-plan.sh, must not inline the resolution body, must not
reference the insecure /tmp SHA cache, must carry the documented per-host
discovery candidates, and must actually ship (or be scheduled to receive via
scripts/sync-ide-folders.py) the scripts the dispatch resolves to.

Discovery-path security invariant: candidates may live only under $HOME or an
env-var anchor the user/host controls (${CLAUDE_SKILL_DIR}, ${PWF_SCRIPT_DIR},
${CODEBUDDY_PLUGIN_ROOT}). A project-relative candidate such as
./scripts/inject-plan.sh would let any cloned repository plant a script that
the hooks then execute — that class is asserted away here.
"""
from __future__ import annotations

import glob
import importlib.util
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_CONFIG = REPO_ROOT / "scripts" / "sync-ide-folders.py"

# The three injection events and the --context flag each must pass.
INJECT_EVENTS = {
    "UserPromptSubmit": "--context=userprompt",
    "PreToolUse": "--context=pretool",
    "PreCompact": "--context=precompact",
}

# Events whose scalars discover-and-dispatch a script. PostToolUse is a plain
# inline echo with no discovery chain and is out of dispatch scope.
DISPATCH_EVENTS = ("UserPromptSubmit", "PreToolUse", "PreCompact", "Stop")

# Stable markers of the pre-v3 inline resolution body. Any of these inside a
# hook command scalar means the logic is inlined, not dispatched.
INLINE_BODY_MARKERS = ("RESOLVED=", "SLUG_RE=")

# The world-writable SHA cache that moved to $XDG_CACHE_HOME in v3.0.0
# (security rec 2: /tmp poisoning). No shipped scalar may still use it.
INSECURE_SHA_CACHE = "${TMPDIR:-/tmp}/pwf-sha"

# Anchors a discovery candidate is allowed to start from. $HOME and the host
# CLAUDE_SKILL_DIR as before, plus PWF_SCRIPT_DIR (the explicit user override
# for workspace installs) and CODEBUDDY_PLUGIN_ROOT (CodeBuddy's own skill
# root, referenced by .codebuddy's SKILL.md body itself). None of these can be
# planted by a cloned repository, unlike a bare or ./ scripts/ path.
ALLOWED_CANDIDATE_PREFIXES = (
    "$HOME/",
    "${CLAUDE_SKILL_DIR}",
    "${PWF_SCRIPT_DIR}",
    "${CODEBUDDY_PLUGIN_ROOT}",
)

# Scripts every hooks-bearing skill directory must ship so the dispatch cannot
# resolve to nothing or to a liar: inject-plan.sh is the dispatch target, it
# shells its sibling ledger-summary.sh in autonomous/gated mode, and
# ledger-summary.sh shells resolve-plan-dir.sh — without the resolver it falls
# back to plan_dir="." and reports a false "phases: 0/0 complete".
REQUIRED_SIBLING_SCRIPTS = ("inject-plan.sh", "ledger-summary.sh", "resolve-plan-dir.sh")

# One-line marker of the UserPromptSubmit not-found notice.
NOT_FOUND_NOTICE = "hook script not found"

# Hosts whose variants carry the generated first-match-wins loop dispatch
# (plus the five language variants under skills/). The canonical skill and the
# .agents mirror install through Claude Code where CLAUDE_SKILL_DIR is always
# set; they keep the legacy ls-fallback shape and their silent-when-absent
# behavior, pinned by test_hook_body_v240.py.
LOOP_DISPATCH_HOSTS = (
    ".codebuddy",
    ".codex",
    ".cursor",
    ".factory",
    ".mastracode",
    ".opencode",
)

# Expected per-host install-path probes, driven by each host's documented
# install location — NOT by a uniform $HOME/<host>/ rule. That rule enforced
# the wrong path for .opencode, whose documented user-level install is
# ~/.config/opencode/skills (docs/opencode.md), with ~/.opencode/skills kept
# as the conventional fallback. Evidence per host:
#   .codebuddy  docs/codebuddy.md (Method 2) + ${CODEBUDDY_PLUGIN_ROOT} in the
#               variant's own SKILL.md body
#   .codex      docs/codex.md (Method 2: ~/.codex/skills)
#   .cursor     docs/cursor.md documents only a project-local install; the
#               conventional ~/.cursor/skills user dir stays probed
#   .factory    docs/factory.md (Method 2: ~/.factory/skills)
#   .mastracode docs/mastra.md (Method 2: ~/.mastracode/skills)
#   .opencode   docs/opencode.md (global: ~/.config/opencode/skills), plus the
#               ~/.opencode/skills fallback — both required, documented first
HOST_EXPECTED_PROBES = {
    ".codebuddy": (
        "${CODEBUDDY_PLUGIN_ROOT}/scripts/",
        "$HOME/.codebuddy/skills/planning-with-files/scripts/",
    ),
    ".codex": ("$HOME/.codex/skills/planning-with-files/scripts/",),
    ".cursor": ("$HOME/.cursor/skills/planning-with-files/scripts/",),
    ".factory": ("$HOME/.factory/skills/planning-with-files/scripts/",),
    ".mastracode": ("$HOME/.mastracode/skills/planning-with-files/scripts/",),
    ".opencode": (
        "$HOME/.config/opencode/skills/planning-with-files/scripts/",
        "$HOME/.opencode/skills/planning-with-files/scripts/",
    ),
}

# The eleven loop-dispatch variants, asserted present (anti-vacuity).
EXPECTED_LOOP_DISPATCH_FILES = {
    ".codebuddy/skills/planning-with-files/SKILL.md",
    ".codex/skills/planning-with-files/SKILL.md",
    ".cursor/skills/planning-with-files/SKILL.md",
    ".factory/skills/planning-with-files/SKILL.md",
    ".mastracode/skills/planning-with-files/SKILL.md",
    ".opencode/skills/planning-with-files/SKILL.md",
    "skills/i18n/planning-with-files-ar/SKILL.md",
    "skills/i18n/planning-with-files-de/SKILL.md",
    "skills/i18n/planning-with-files-es/SKILL.md",
    "skills/i18n/planning-with-files-zh/SKILL.md",
    "skills/i18n/planning-with-files-zht/SKILL.md",
}

# The first-match-wins discovery loop (single line, POSIX sh).
FIRST_MATCH_LOOP_RE = re.compile(
    r'for c in (?:"[^"]+" )*"[^"]+"; do \[ -f "\$c" \] && '
    r'\{ [A-Z0-9_]+="\$c"; break; \}; done'
)

# Every for-loop candidate list inside a scalar, for first-candidate checks.
LOOP_CANDIDATES_RE = re.compile(r'for c in ("[^"]+"(?: "[^"]+")*); do')


def _tracked_skill_md_files():
    """Every tracked SKILL.md, via git; glob fallback for non-git checkouts."""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", "ls-files", "*SKILL.md"],
            cwd=str(REPO_ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return [REPO_ROOT / line for line in proc.stdout.splitlines() if line]
    except OSError:
        pass
    out = []
    for p in glob.glob(str(REPO_ROOT / "**" / "SKILL.md"), recursive=True):
        parts = Path(p).parts
        if ".git" in parts or "node_modules" in parts:
            continue
        out.append(Path(p))
    return out


def _frontmatter(text):
    if not text.startswith("---"):
        return None
    segments = text.split("---", 2)
    if len(segments) < 3:
        return None
    return segments[1]


def _load_yaml(frontmatter):
    import yaml

    return yaml.safe_load(frontmatter)


def _hooks_bearing_files():
    """(path, parsed-frontmatter) for every tracked SKILL.md declaring hooks."""
    found = []
    for f in _tracked_skill_md_files():
        if not f.is_file():
            continue
        fm_text = _frontmatter(f.read_text(encoding="utf-8"))
        if fm_text is None:
            continue
        data = _load_yaml(fm_text)
        if isinstance(data, dict) and isinstance(data.get("hooks"), dict):
            found.append((f, data))
    return found


def _event_commands(hooks_block, event):
    """All command scalars registered for one hook event."""
    commands = []
    for entry in hooks_block.get(event) or []:
        if not isinstance(entry, dict):
            continue
        for h in entry.get("hooks") or []:
            if isinstance(h, dict) and isinstance(h.get("command"), str):
                commands.append(h["command"])
    return commands


def _all_commands(hooks_block):
    commands = []
    for event in hooks_block:
        commands.extend(_event_commands(hooks_block, event))
    return commands


def _is_loop_dispatch(skill_md):
    """True for the eleven variants that carry the generated loop dispatch."""
    rel = skill_md.relative_to(REPO_ROOT).parts
    if rel[0] in LOOP_DISPATCH_HOSTS:
        return True
    # Language variants live under skills/i18n/ so the Claude Code plugin
    # scan, which reads skills/*/SKILL.md and does not recurse, registers the
    # canonical skill alone. Identify them by directory name, not by depth.
    return rel[0] == "skills" and skill_md.parent.name != "planning-with-files"


def _expected_probes(skill_md):
    """Documented install-path fragments this variant's scalars must probe.

    IDE mirrors get the per-host documented set from HOST_EXPECTED_PROBES;
    language variants install under $HOME/.claude/skills/<variant-name>. The
    canonical skill and the .agents standard mirror have no install dir beyond
    the canonical two-path fallback and return an empty tuple.
    """
    rel = skill_md.relative_to(REPO_ROOT).parts
    if rel[0] in HOST_EXPECTED_PROBES:
        return HOST_EXPECTED_PROBES[rel[0]]
    if rel[0] == "skills" and skill_md.parent.name != "planning-with-files":
        # `npx skills add` installs by skill name, so the install dir keeps its
        # flat $HOME/.claude/skills/<variant-name>/ shape after the i18n move.
        return (f"$HOME/.claude/skills/{skill_md.parent.name}/scripts/",)
    return ()


def _load_sync_config():
    """Import scripts/sync-ide-folders.py for its manifest data (no main())."""
    spec = importlib.util.spec_from_file_location("pwf_sync_ide_folders", SYNC_CONFIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HookDispatchParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import yaml  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PyYAML not installed")
        cls.files = _hooks_bearing_files()

    def _loop_dispatch_files(self):
        return [(f, d) for f, d in self.files if _is_loop_dispatch(f)]

    def test_guard_hooks_bearing_files_found(self):
        # Anti-vacuity guard: the fleet must be discovered, the reporter's
        # route (#212 was filed from a .codex install) must be in it, and all
        # eleven loop-dispatch variants must be present so the loop-shape
        # assertions below cannot pass by matching nothing.
        self.assertTrue(self.files, "no hooks-bearing SKILL.md files discovered")
        paths = {str(f.relative_to(REPO_ROOT)).replace("\\", "/") for f, _ in self.files}
        self.assertIn(
            ".codex/skills/planning-with-files/SKILL.md",
            paths,
            "the .codex variant (the #212 reporter's install) was not discovered",
        )
        missing = EXPECTED_LOOP_DISPATCH_FILES - paths
        self.assertFalse(
            missing,
            f"loop-dispatch variants missing from the discovered fleet: {sorted(missing)}",
        )

    def test_no_inline_resolution_body_in_any_scalar(self):
        # The v2.43 inline body froze eleven variants out of every
        # inject-plan.sh fix. Hooks must dispatch, never inline.
        for f, data in self.files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for cmd in _all_commands(data["hooks"]):
                    for marker in INLINE_BODY_MARKERS:
                        self.assertNotIn(
                            marker,
                            cmd,
                            f"{f}: hook scalar carries the inlined v2.43 "
                            f"resolution body (marker {marker!r}); it must "
                            "dispatch to inject-plan.sh instead",
                        )

    def test_inject_events_dispatch_with_matching_context(self):
        for f, data in self.files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for event, flag in INJECT_EVENTS.items():
                    commands = _event_commands(data["hooks"], event)
                    self.assertTrue(commands, f"{f}: no {event} command scalar")
                    dispatching = [c for c in commands if "inject-plan.sh" in c]
                    self.assertTrue(
                        dispatching,
                        f"{f}: {event} scalar does not reference inject-plan.sh",
                    )
                    for cmd in dispatching:
                        self.assertIn(
                            flag,
                            cmd,
                            f"{f}: {event} scalar must pass {flag}",
                        )

    def test_no_insecure_tmp_sha_cache(self):
        for f, data in self.files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for cmd in _all_commands(data["hooks"]):
                    self.assertNotIn(
                        INSECURE_SHA_CACHE,
                        cmd,
                        f"{f}: scalar still uses the world-writable /tmp SHA "
                        "cache (moved to $XDG_CACHE_HOME in v3.0.0)",
                    )

    def test_inject_scalars_carry_documented_discovery_candidates(self):
        # At least two candidates (CLAUDE_SKILL_DIR plus a $HOME install path),
        # and every documented per-host probe must be present — the canonical
        # two-path fallback never resolves on Codex, Cursor, Factory and the
        # rest, and a uniform $HOME/<host>/ rule enforced the wrong path for
        # .opencode (docs/opencode.md documents ~/.config/opencode/skills).
        for f, data in self.files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                probes = _expected_probes(f)
                for event in INJECT_EVENTS:
                    for cmd in _event_commands(data["hooks"], event):
                        candidates = cmd.count("/scripts/inject-plan.sh")
                        self.assertGreaterEqual(
                            candidates,
                            2,
                            f"{f}: {event} scalar has {candidates} discovery "
                            "candidate(s); need CLAUDE_SKILL_DIR plus at least "
                            "one install-path fallback",
                        )
                        for probe in probes:
                            self.assertIn(
                                probe,
                                cmd,
                                f"{f}: {event} scalar never probes the "
                                f"documented install dir ({probe}) — the "
                                "dispatch cannot resolve on its host",
                            )

    def test_stop_scalar_probes_documented_install_dirs(self):
        # Same host-resolution requirement for the Stop hook: before this fix
        # the Stop scalar looked only at CLAUDE_SKILL_DIR and the two .claude
        # paths, so on Codex/Cursor/Factory it silently did nothing.
        for f, data in self.files:
            probes = _expected_probes(f)
            if not probes:
                continue
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                commands = _event_commands(data["hooks"], "Stop")
                self.assertTrue(commands, f"{f}: no Stop command scalar")
                for cmd in commands:
                    for probe in probes:
                        self.assertIn(
                            probe,
                            cmd,
                            f"{f}: Stop scalar never probes the documented "
                            f"install dir ({probe})",
                        )

    def test_loop_dispatch_uses_first_match_wins_not_ls_head(self):
        # ``ls a b c | head -1`` SORTS, so the marketplace copy beat the
        # host-native one whenever both existed. The eleven converted variants
        # must use the first-match-wins loop and must not carry the ls idiom.
        files = self._loop_dispatch_files()
        self.assertTrue(files, "no loop-dispatch variants discovered")
        for f, data in files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for event in DISPATCH_EVENTS:
                    commands = _event_commands(data["hooks"], event)
                    self.assertTrue(commands, f"{f}: no {event} command scalar")
                    for cmd in commands:
                        self.assertNotIn(
                            "head -1",
                            cmd,
                            f"{f}: {event} scalar still picks candidates via "
                            "'head -1', which sorts instead of honouring "
                            "priority order",
                        )
                        self.assertNotIn(
                            "$(ls",
                            cmd,
                            f"{f}: {event} scalar still uses the ls-discovery "
                            "idiom",
                        )
                        self.assertRegex(
                            cmd,
                            FIRST_MATCH_LOOP_RE,
                            f"{f}: {event} scalar carries no first-match-wins "
                            "discovery loop",
                        )

    def test_pwf_script_dir_is_the_first_candidate(self):
        # The opt-in escape hatch for workspace installs must win over every
        # other candidate, in every discovery loop (Stop carries two).
        for f, data in self._loop_dispatch_files():
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for event in DISPATCH_EVENTS:
                    for cmd in _event_commands(data["hooks"], event):
                        loops = LOOP_CANDIDATES_RE.findall(cmd)
                        self.assertTrue(
                            loops,
                            f"{f}: {event} scalar has no candidate loop to "
                            "inspect",
                        )
                        for candidate_list in loops:
                            first = candidate_list.split('" "')[0].strip('"')
                            self.assertTrue(
                                first.startswith("${PWF_SCRIPT_DIR}/"),
                                f"{f}: {event} scalar's first candidate is "
                                f"{first!r}, not the ${{PWF_SCRIPT_DIR}} "
                                "escape hatch",
                            )

    def test_not_found_notice_on_userpromptsubmit_only(self):
        # Never fail silently: with nothing installed the UserPromptSubmit
        # scalar must say so, exactly once per prompt. PreToolUse/PreCompact
        # fire per tool call and Stop carries no plan body, so a notice there
        # would be spam — the asymmetry is deliberate.
        for f, data in self._loop_dispatch_files():
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                ups = _event_commands(data["hooks"], "UserPromptSubmit")
                self.assertTrue(ups, f"{f}: no UserPromptSubmit command scalar")
                for cmd in ups:
                    self.assertIn(
                        NOT_FOUND_NOTICE,
                        cmd,
                        f"{f}: UserPromptSubmit scalar fails silently when no "
                        "candidate resolves; it must emit the not-found notice",
                    )
                    self.assertIn(
                        "PWF_SCRIPT_DIR",
                        cmd,
                        f"{f}: the not-found notice must tell the user about "
                        "the PWF_SCRIPT_DIR escape hatch",
                    )
                for event in ("PreToolUse", "PreCompact", "Stop"):
                    for cmd in _event_commands(data["hooks"], event):
                        self.assertNotIn(
                            NOT_FOUND_NOTICE,
                            cmd,
                            f"{f}: {event} must stay silent when the script is "
                            "absent (per-tool-call notices are spam)",
                        )
        # The canonical skill and the .agents mirror keep their pinned
        # silent-when-absent behavior (test_hook_body_v240.py); the notice
        # must not spill into their scalars.
        for f, data in self.files:
            if _is_loop_dispatch(f):
                continue
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for cmd in _all_commands(data["hooks"]):
                    self.assertNotIn(NOT_FOUND_NOTICE, cmd)

    def test_sibling_scripts_shipped_or_scheduled_by_sync(self):
        # The dispatch must be able to resolve to something that tells the
        # truth: the skill's own scripts/ dir must ship the dispatch target,
        # its ledger sibling, and the plan-dir resolver (without which
        # ledger-summary.sh reports a false "phases: 0/0 complete").
        #
        # Source of truth is scripts/sync-ide-folders.py: a variant passes if
        # the file is on disk OR the sync manifest schedules it for that
        # variant (the sync run materialises it). This keeps the assertion
        # honest before and after the sync runs while still failing if a
        # variant is neither shipped nor scheduled.
        mod = _load_sync_config()
        self.assertIn(
            "scripts/resolve-plan-dir.sh",
            mod.HOOK_DISPATCH_SCRIPTS,
            "sync config no longer lists resolve-plan-dir.sh as a hook "
            "dispatch script; the seven scripts-light variants would ship a "
            "ledger-summary.sh that lies (plan_dir='.', 0/0 complete)",
        )
        sync_targets = {
            Path(target).as_posix()
            for manifest in mod.IDE_MANIFESTS.values()
            for target in manifest.values()
        }
        for f, _ in self.files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                scripts_dir = f.parent / "scripts"
                for name in REQUIRED_SIBLING_SCRIPTS:
                    if (scripts_dir / name).is_file():
                        continue
                    expected_target = (
                        f.parent.relative_to(REPO_ROOT) / "scripts" / name
                    ).as_posix()
                    self.assertIn(
                        expected_target,
                        sync_targets,
                        f"{f}: sibling scripts/{name} is neither shipped nor "
                        "scheduled by scripts/sync-ide-folders.py — the hook "
                        "dispatch resolves to nothing (or to a lying ledger "
                        "summary) on this variant",
                    )

    def test_no_project_relative_script_candidates(self):
        # Security invariant: a repo-local candidate (./scripts/... or a bare
        # scripts/...) would execute a script planted by any cloned repository.
        # Every token that references a scripts/ path must be anchored at
        # $HOME or one of the allowed env vars (CLAUDE_SKILL_DIR is host-set,
        # PWF_SCRIPT_DIR is user-set, CODEBUDDY_PLUGIN_ROOT is host-set).
        for f, data in self.files:
            with self.subTest(file=str(f.relative_to(REPO_ROOT))):
                for cmd in _all_commands(data["hooks"]):
                    self.assertNotIn(
                        "./scripts/",
                        cmd,
                        f"{f}: scalar carries a project-relative ./scripts/ "
                        "candidate",
                    )
                    for token in re.split(r"[\s;()]+", cmd):
                        if "scripts/" not in token:
                            continue
                        cleaned = token.strip("\"'")
                        self.assertTrue(
                            any(p in cleaned for p in ALLOWED_CANDIDATE_PREFIXES),
                            f"{f}: script path candidate {token!r} is not "
                            "anchored at $HOME or an allowed env var — a "
                            "cloned repo could plant the script it executes",
                        )


if __name__ == "__main__":
    unittest.main()
