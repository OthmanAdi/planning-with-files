"""The npm README must be the root README pinned to the packaged release."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build-npm-readme.py"
PACKAGE_ROOT = REPO_ROOT / ".pi" / "skills" / "planning-with-files"

BLOB = "https://github.com/OthmanAdi/planning-with-files/blob/"
TREE = "https://github.com/OthmanAdi/planning-with-files/tree/"
RAW = "https://raw.githubusercontent.com/OthmanAdi/planning-with-files/"

SOURCE_FIXTURE = """\
<img src="media/banner.webp" alt="banner">
<a href="docs/evals.md"><img src="https://img.shields.io/badge/x-1-green" alt="x"></a>

Install with the [installation guide](docs/installation.md) or the
[Hermes guide](docs/hermes.md#named-plans). Browse [docs/](docs/) or
![chart](media/chart.svg). Credit lives in [contributors](./CONTRIBUTORS.md).

See [v2.0.0 notes](https://github.com/OthmanAdi/planning-with-files/releases/tag/v2.0.0),
the [v3.24.3 guide](https://github.com/OthmanAdi/planning-with-files/blob/v3.24.3/docs/hermes.md),
the [Manus write-up](https://manus.im/blog/context-engineering), [top](#top) and
[mail](mailto:someone@example.com).

```markdown
[kept](docs/quickstart.md)
```

npm users: `npm install planning-with-files`.
"""


def load_builder():
    spec = importlib.util.spec_from_file_location("pwf_build_npm_readme", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return load_builder()


def test_committed_npm_readme_matches_package_version(builder) -> None:
    version = json.loads((PACKAGE_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    current = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
    expected = builder.render((REPO_ROOT / "README.md").read_text(encoding="utf-8"), version)
    problems = builder.stale_report(current, expected, version)
    assert not problems, (
        ".pi/skills/planning-with-files/README.md is stale for package version "
        f"{version}:\n  " + "\n  ".join(problems) + "\nRun: python scripts/build-npm-readme.py"
    )


def test_relative_links_pin_to_package_version(builder) -> None:
    out = builder.render(SOURCE_FIXTURE, "3.28.1")
    assert f'src="{RAW}v3.28.1/media/banner.webp"' in out
    assert f"![chart]({RAW}v3.28.1/media/chart.svg)" in out
    assert f'href="{BLOB}v3.28.1/docs/evals.md"' in out
    assert f"({BLOB}v3.28.1/docs/installation.md)" in out
    assert f"({BLOB}v3.28.1/docs/hermes.md#named-plans)" in out
    assert f"({TREE}v3.28.1/docs/)" in out
    assert f"({BLOB}v3.28.1/./CONTRIBUTORS.md)" in out


def test_package_version_change_moves_every_pin(builder) -> None:
    old = builder.render(SOURCE_FIXTURE, "3.28.1")
    new = builder.render(SOURCE_FIXTURE, "3.29.0")
    assert new == old.replace("/v3.28.1/", "/v3.29.0/")
    assert "/v3.28.1/" not in new


def test_absolute_links_anchors_and_code_blocks_are_preserved(builder) -> None:
    out = builder.render(SOURCE_FIXTURE, "3.29.0")
    for kept in (
        "https://img.shields.io/badge/x-1-green",
        "https://github.com/OthmanAdi/planning-with-files/releases/tag/v2.0.0",
        "https://github.com/OthmanAdi/planning-with-files/blob/v3.24.3/docs/hermes.md",
        "https://manus.im/blog/context-engineering",
        "[top](#top)",
        "[mail](mailto:someone@example.com)",
        "[kept](docs/quickstart.md)",
        "npm users: `npm install planning-with-files`.",
    ):
        assert kept in out


def test_render_is_idempotent(builder) -> None:
    once = builder.render(SOURCE_FIXTURE, "3.28.1")
    assert builder.render(once, "3.28.1") == once


def test_stale_report_names_old_pins_and_changed_prose(builder) -> None:
    released = builder.render(SOURCE_FIXTURE, "3.24.3")
    edited_source = SOURCE_FIXTURE.replace("Install with", "Install the plugin with")
    problems = builder.stale_report(released, builder.render(edited_source, "3.28.1"), "3.28.1")
    assert any("not pinned to v3.28.1" in p and "docs/hermes.md (v3.24.3)" in p for p in problems)
    assert any("differ from README.md beyond link pins" in p for p in problems)
    assert builder.stale_report(released, released, "3.24.3") == []


def test_version_only_change_is_reported_without_prose_drift(builder) -> None:
    problems = builder.stale_report(
        builder.render(SOURCE_FIXTURE, "3.24.3"), builder.render(SOURCE_FIXTURE, "3.28.1"), "3.28.1"
    )
    assert len(problems) == 1 and "not pinned to v3.28.1" in problems[0]


@pytest.mark.parametrize("fixture_version", ["0.1.2", "99.8.7"])
def test_check_mode_is_read_only_and_fails_when_stale(
    builder, tmp_path, monkeypatch, capsys, fixture_version
) -> None:
    (tmp_path / "README.md").write_text(SOURCE_FIXTURE, encoding="utf-8")
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    (package_dir / "package.json").write_text(
        json.dumps({"version": fixture_version}) + "\n", encoding="utf-8"
    )
    target = package_dir / "README.md"
    stale = builder.render(SOURCE_FIXTURE, "3.24.3")
    target.write_text(stale, encoding="utf-8")
    monkeypatch.setattr(builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(builder, "SOURCE", tmp_path / "README.md")
    monkeypatch.setattr(builder, "TARGET", target)
    monkeypatch.setattr(builder, "PACKAGE_JSON", package_dir / "package.json")

    assert builder.main(["--check"]) == 1
    assert f"not pinned to v{fixture_version}" in capsys.readouterr().out
    assert target.read_text(encoding="utf-8") == stale

    assert builder.main([]) == 0
    assert target.read_text(encoding="utf-8") == builder.render(SOURCE_FIXTURE, fixture_version)
    assert builder.main(["--check"]) == 0
    assert builder.main([]) == 0
    assert "already current" in capsys.readouterr().out


def test_npm_pack_ships_the_generated_readme(builder) -> None:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        pytest.skip("npm is unavailable")
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [npm, "pack", "--pack-destination", temp_dir],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        assert result.returncode == 0, f"npm pack failed:\n{result.stdout}\n{result.stderr}"
        tarballs = list(Path(temp_dir).glob("*.tgz"))
        assert len(tarballs) == 1, result.stdout
        with tarfile.open(tarballs[0]) as archive:
            packed = archive.extractfile("package/README.md")
            assert packed is not None
            shipped = packed.read()
    assert shipped == (PACKAGE_ROOT / "README.md").read_bytes()
