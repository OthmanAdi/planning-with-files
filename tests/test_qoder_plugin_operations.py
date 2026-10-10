import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".qoder-plugin" / "plugin.json"
HOOKS = ROOT / "hooks" / "qoder-hooks.json"


def test_qoder_manifest_exposes_canonical_skill_and_hooks():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["name"] == "planning-with-files"
    assert manifest["skills"] == "./skills/planning-with-files/"
    assert manifest["hooks"] == "./hooks/qoder-hooks.json"
    assert manifest["commands"] == []


def test_qoder_hooks_use_qoder_plugin_root_and_supported_events():
    hooks = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {
        "SessionStart", "UserPromptSubmit", "PreToolUse",
        "PermissionRequest", "PostToolUse", "PreCompact", "Stop",
    }
    for groups in hooks.values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["type"] == "command"
                assert hook["shell"] == "bash"
                assert hook["command"] == '. "${QODER_PLUGIN_ROOT}/.qoder-plugin/run-hook.sh"'
                assert "args" not in hook


def test_qoder_session_start_recovers_all_fresh_context_sources():
    hooks = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]
    sources = hooks["SessionStart"][0]["matcher"].split("|")
    assert set(sources) == {"startup", "resume", "clear", "compact", "new"}
