#!/usr/bin/env python3
"""Grade a file-only recovery work directory.

Stay outside the work directory. This grader reads that directory's
counts.py and, except on the baseline arm, its task_plan.md. It does
not open host session stores.

    python3 grade.py --self-check
    python3 grade.py WORKDIR [--arm file-only|baseline|replay] [--receipt PATH]

The first output line is pass, fail, or inconclusive. Exit status is
0, 1, or 2 for those three outcomes. --self-check exits 0 when the
committed checkpoint is not done and complete/ passes.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent
CHECKPOINT = ROOT / "checkpoint"
COMPLETE = ROOT / "complete"

HALFWAY_PHASE = "Phase 3"
HALFWAY_NEXT_STEP = (
    "Implement line_count and unique_words in counts.py. "
    "word_count is already done."
)
ARMS = ("file-only", "baseline", "replay")
FORBIDDEN_FLAGS = ("--metadata", "--replay")
# "Hello Hello" repeats one word, so unique_words is not len(text.split()).
SAMPLES = ("", "Hello hello", "Hello Hello", "a\nb")
FUNCTIONS = ("word_count", "line_count", "unique_words")

# Directory layouts this grader must not open. Matching is on the
# resolved path. The workdir's own counts.py and task_plan.md are the
# only project files read.
_SESSION_MARKERS = (
    "/.claude/projects/",
    "/.claude/sessions/",
    "/.codex/sessions/",
    "/.cursor/projects/",
    "/.cursor/agent-transcripts/",
    "/agent-transcripts/",
    "/.local/share/opencode/",
    "/.dsh/sessions/",
    "/.config/opencode/",
)


def is_session_store(path: Path) -> bool:
    text = path.resolve().as_posix()
    if not text.endswith("/"):
        text += "/"
    return any(marker in text for marker in _SESSION_MARKERS)


def expected(name: str, text: str) -> int:
    if text == "":
        return 0
    if name == "word_count":
        return len(text.split())
    if name == "line_count":
        return len(text.splitlines())
    if name == "unique_words":
        return len(set(text.split()))
    raise RuntimeError("unknown function: %s" % name)


def section_body(text: str, heading: str) -> str:
    needle = "## " + heading
    collecting = False
    body: list[str] = []
    for line in text.splitlines():
        if line.strip() == needle or (
            collecting and line.startswith("## ")
        ):
            if collecting:
                break
            collecting = line.strip() == needle
            continue
        if collecting:
            body.append(line)
    return "\n".join(body).strip()


def phase_status(text: str, number: int) -> str:
    prefix = "### Phase %d:" % number
    in_phase = False
    for line in text.splitlines():
        if line.startswith("### Phase "):
            if in_phase:
                break
            in_phase = line.startswith(prefix)
            continue
        if in_phase and "**Status:**" in line:
            return line.split("**Status:**", 1)[1].strip()
    return ""


def _phase_number(token: str) -> Optional[int]:
    parts = token.split(None, 1)
    if not parts or parts[0] != "Phase" or len(parts) == 1:
        return None
    digits: list[str] = []
    for char in parts[1]:
        if not char.isdigit():
            break
        digits.append(char)
    if not digits:
        return None
    return int("".join(digits))


def phase_moved_on(current: str) -> bool:
    """True when Current Phase names a phase after Phase 3."""
    if not current.strip():
        return False
    token = current.strip().splitlines()[0].strip()
    number = _phase_number(token)
    return number is not None and number > 3


def parse_receipt(text: str) -> dict:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        key = cells[0].strip().lower()
        if key in ("", "field") or set(key) <= {"-"}:
            continue
        fields[key] = cells[1].strip()
    return fields


def forbidden_flags(flags: str) -> list[str]:
    found = []
    for token in flags.split():
        for flag in FORBIDDEN_FLAGS:
            if token == flag or token.startswith(flag + "="):
                found.append(flag)
    return found


def counts_in_file_only_tally(result: dict) -> bool:
    """File-only pass and fail are the file-only numbers.

    Baseline, replay, and inconclusive trials stay in the report and
    are not added to that tally.
    """
    return result["arm"] == "file-only" and result["outcome"] in ("pass", "fail")


class _Reader:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def read_text(self, path: Path) -> str:
        resolved = path.resolve()
        if is_session_store(resolved):
            raise RuntimeError("refusing session store path")
        self.paths.append(resolved)
        return resolved.read_text(encoding="utf-8")


def _contained_file(workdir: Path, name: str) -> Optional[Path]:
    root = workdir.resolve()
    if is_session_store(root):
        return None
    candidate = workdir / name
    if not candidate.is_file():
        return None
    resolved = candidate.resolve()
    if resolved.parent != root or resolved.name != name:
        return None
    if is_session_store(resolved):
        return None
    return resolved


def _load_counts(source: str, path: Path) -> tuple[Optional[object], str]:
    namespace: dict = {"__name__": "pwf_recovery_counts", "__file__": str(path)}
    try:
        exec(compile(source, str(path), "exec"), namespace)
    except Exception as exc:
        return None, "counts.py could not be loaded (%s)" % type(exc).__name__
    return namespace, ""


def _check_functions(namespace: dict) -> dict[str, str]:
    status = {}
    for name in FUNCTIONS:
        fn = namespace.get(name)
        if not callable(fn):
            status[name] = "fail"
            continue
        ok = True
        for sample in SAMPLES:
            try:
                got = fn(sample)
            except Exception:
                ok = False
                break
            if got != expected(name, sample):
                ok = False
                break
        status[name] = "pass" if ok else "fail"
    return status


def _blank(arm: str) -> dict:
    return {
        "outcome": "inconclusive",
        "arm": arm,
        "objective": "missing",
        "word_count": "missing",
        "line_count": "missing",
        "unique_words": "missing",
        "current_phase": "",
        "next_step": "",
        "phase_3": "",
        "flags": "",
        "reason": "",
        "reads": [],
    }


def _grade_loaded(
    workdir: Path,
    result: dict,
    reader: _Reader,
    receipt_outcome: str,
) -> dict:
    flags = result["flags"]
    arm = result["arm"]

    try:
        root = workdir.resolve()
    except OSError:
        result["reason"] = "workdir missing"
        result["reads"] = list(reader.paths)
        return result

    if not workdir.exists():
        result["reason"] = "workdir missing"
        result["reads"] = list(reader.paths)
        return result

    if is_session_store(root):
        result["reason"] = "refusing session store path"
        result["reads"] = list(reader.paths)
        return result

    if receipt_outcome == "aborted":
        result["reason"] = "aborted trial"
        result["reads"] = list(reader.paths)
        return result

    if arm == "file-only" and forbidden_flags(flags):
        result["reason"] = "file-only receipt records --metadata or --replay"
        result["reads"] = list(reader.paths)
        return result

    counts_path = _contained_file(workdir, "counts.py")
    plan_path = None if arm == "baseline" else _contained_file(workdir, "task_plan.md")

    if counts_path is None:
        result["reason"] = "counts.py missing"
        result["reads"] = list(reader.paths)
        return result

    try:
        source = reader.read_text(counts_path)
    except RuntimeError:
        result["reason"] = "refusing session store path"
        result["reads"] = list(reader.paths)
        return result

    namespace, load_error = _load_counts(source, counts_path)
    if namespace is None:
        result["reason"] = load_error
        result["reads"] = list(reader.paths)
        return result

    function_status = _check_functions(namespace)
    result.update(function_status)
    objective_ok = all(function_status[name] == "pass" for name in FUNCTIONS)
    result["objective"] = "pass" if objective_ok else "fail"

    if arm == "baseline":
        result["outcome"] = "pass" if objective_ok else "fail"
        result["reason"] = "" if objective_ok else "objective not met"
        result["reads"] = list(reader.paths)
        return result

    if plan_path is None:
        result["reason"] = "task_plan.md missing"
        result["objective"] = "pass" if objective_ok else "fail"
        result["reads"] = list(reader.paths)
        return result

    try:
        plan = reader.read_text(plan_path)
    except RuntimeError:
        result["reason"] = "refusing session store path"
        result["reads"] = list(reader.paths)
        return result

    result["current_phase"] = section_body(plan, "Current Phase")
    result["next_step"] = section_body(plan, "Next Step")
    result["phase_3"] = phase_status(plan, 3)

    if not result["current_phase"] or not result["phase_3"]:
        result["reason"] = "task_plan.md is missing phase fields"
        result["reads"] = list(reader.paths)
        return result

    if not objective_ok:
        result["outcome"] = "fail"
        result["reason"] = "objective not met"
    elif result["phase_3"] != "complete":
        result["outcome"] = "fail"
        result["reason"] = "phase 3 is not complete"
    elif not phase_moved_on(result["current_phase"]):
        result["outcome"] = "fail"
        result["reason"] = "current phase has not moved on"
    else:
        result["outcome"] = "pass"
        result["reason"] = ""

    result["reads"] = list(reader.paths)
    return result


def grade(
    workdir: Path,
    arm: Optional[str] = None,
    receipt: Optional[Path] = None,
) -> dict:
    """Grade one work directory.

    Receipt text is loaded here so a session-store path is refused
    before any project file is opened.
    """
    reader = _Reader()
    receipt_text = None
    if receipt is not None:
        if is_session_store(receipt):
            result = _blank(arm or "file-only")
            result["reason"] = "refusing session store path"
            return result
        try:
            receipt_text = reader.read_text(receipt)
        except (OSError, RuntimeError):
            result = _blank(arm or "file-only")
            result["reason"] = "receipt unreadable"
            result["reads"] = list(reader.paths)
            return result

    fields = parse_receipt(receipt_text) if receipt_text is not None else {}
    receipt_arm = fields.get("arm", "").strip()
    flags = fields.get("flags", "")
    receipt_outcome = fields.get("outcome", "").strip().lower()

    chosen = arm or receipt_arm or "file-only"
    result = _blank(chosen if chosen in ARMS else "file-only")
    result["flags"] = flags
    if chosen not in ARMS:
        result["reason"] = "unknown arm"
        result["reads"] = list(reader.paths)
        return result
    if arm and receipt_arm and arm != receipt_arm:
        result["arm"] = arm
        result["reason"] = "arm mismatch"
        result["reads"] = list(reader.paths)
        return result
    result["arm"] = chosen
    return _grade_loaded(workdir, result, reader, receipt_outcome)


def format_report(result: dict) -> str:
    lines = [
        result["outcome"],
        "arm: %s" % result["arm"],
        "file_only_tally: %s" % ("yes" if counts_in_file_only_tally(result) else "no"),
        "objective: %s" % result["objective"],
    ]
    if result["current_phase"]:
        lines.append("current_phase: %s" % result["current_phase"])
    if result["next_step"]:
        lines.append("next_step: %s" % result["next_step"])
    if result["phase_3"]:
        lines.append("phase_3: %s" % result["phase_3"])
    if result["flags"]:
        lines.append("flags: %s" % result["flags"])
    if result["reason"]:
        lines.append("reason: %s" % result["reason"])
    return "\n".join(lines) + "\n"


def _receipt(rows: dict[str, str]) -> str:
    ordered = (
        "Skill commit or release",
        "Host",
        "Model",
        "OS",
        "Flags",
        "Arm",
        "Stage-2 turns",
        "Outcome",
    )
    lines = [
        "# File-only recovery receipt",
        "",
        "| Field | Value |",
        "|-------|-------|",
    ]
    for key in ordered:
        lines.append("| %s | %s |" % (key, rows.get(key, "")))
    lines.append("")
    return "\n".join(lines)


def _write_receipt(directory: Path, name: str, rows: dict[str, str]) -> Path:
    path = directory / name
    path.write_text(_receipt(rows), encoding="utf-8")
    return path


def _base_rows(arm: str, flags: str = "", outcome: str = "pass") -> dict[str, str]:
    return {
        "Skill commit or release": "fixture-self-check",
        "Host": "none",
        "Model": "none",
        "OS": "none",
        "Flags": flags,
        "Arm": arm,
        "Stage-2 turns": "0",
        "Outcome": outcome,
    }


def _expect(errors: list[str], label: str, condition: bool, detail: str) -> None:
    if not condition:
        errors.append("%s: %s" % (label, detail))


def _check_edges(errors: list[str]) -> None:
    _expect(errors, "edge", expected("word_count", "") == 0, "empty word_count")
    _expect(errors, "edge", expected("line_count", "") == 0, "empty line_count")
    _expect(errors, "edge", expected("unique_words", "") == 0, "empty unique_words")
    _expect(
        errors,
        "edge",
        expected("word_count", "Hello hello") == 2,
        "Hello hello word_count",
    )
    _expect(
        errors,
        "edge",
        expected("unique_words", "Hello hello") == 2,
        "Hello hello unique_words",
    )
    _expect(
        errors,
        "edge",
        expected("line_count", "Hello hello") == 1,
        "Hello hello line_count",
    )
    _expect(
        errors,
        "edge",
        expected("word_count", "Hello Hello") == 2,
        "Hello Hello word_count",
    )
    _expect(
        errors,
        "edge",
        expected("unique_words", "Hello Hello") == 1,
        "Hello Hello unique_words",
    )
    _expect(
        errors,
        "samples",
        any(
            expected("unique_words", sample) != expected("word_count", sample)
            for sample in SAMPLES
        ),
        "unique_words matches word_count on every sample",
    )
    _expect(errors, "phase", not phase_moved_on("Phase 1"), "Phase 1")
    _expect(errors, "phase", not phase_moved_on("Phase 2"), "Phase 2")
    _expect(errors, "phase", not phase_moved_on("Phase 3"), "Phase 3")
    _expect(errors, "phase", not phase_moved_on("Phase 3: Implementation"), "Phase 3 detail")
    _expect(errors, "phase", phase_moved_on("Phase 4"), "Phase 4")
    _expect(errors, "phase", phase_moved_on("Phase 5"), "Phase 5")


def _printed_outcome(report: str) -> str:
    return report.splitlines()[0]


def self_check() -> int:
    errors: list[str] = []
    reports: list[tuple[str, dict, str]] = []
    _check_edges(errors)

    checkpoint = grade(CHECKPOINT)
    reports.append(("checkpoint", checkpoint, format_report(checkpoint)))
    _expect(errors, "checkpoint", checkpoint["outcome"] == "fail", "expected fail (not done)")
    _expect(errors, "checkpoint", checkpoint["arm"] == "file-only", checkpoint["arm"])
    _expect(errors, "checkpoint", checkpoint["current_phase"] == HALFWAY_PHASE, checkpoint["current_phase"])
    _expect(errors, "checkpoint", checkpoint["next_step"] == HALFWAY_NEXT_STEP, checkpoint["next_step"])
    _expect(errors, "checkpoint", checkpoint["phase_3"] == "in_progress", checkpoint["phase_3"])
    _expect(errors, "checkpoint", checkpoint["word_count"] == "pass", checkpoint["word_count"])
    _expect(errors, "checkpoint", checkpoint["line_count"] == "fail", checkpoint["line_count"])
    _expect(errors, "checkpoint", checkpoint["unique_words"] == "fail", checkpoint["unique_words"])
    _expect(errors, "checkpoint", counts_in_file_only_tally(checkpoint), "a file-only fail stays in the tally")

    complete = grade(COMPLETE)
    reports.append(("complete", complete, format_report(complete)))
    _expect(errors, "complete", complete["outcome"] == "pass", complete["outcome"])
    _expect(errors, "complete", complete["objective"] == "pass", complete["objective"])
    _expect(errors, "complete", complete["phase_3"] == "complete", complete["phase_3"])
    _expect(errors, "complete", phase_moved_on(complete["current_phase"]), complete["current_phase"])
    _expect(errors, "complete", complete["current_phase"] != HALFWAY_PHASE, complete["current_phase"])
    _expect(errors, "complete", all(complete[name] == "pass" for name in FUNCTIONS), "oracle")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        happy = root / "happy"
        shutil.copytree(COMPLETE, happy)
        happy_receipt = _write_receipt(root, "receipt-file-only.md", _base_rows("file-only"))
        happy_result = grade(happy, receipt=happy_receipt)
        reports.append(("file-only-happy", happy_result, format_report(happy_result)))
        _expect(errors, "file-only-happy", happy_result["outcome"] == "pass", happy_result["outcome"])
        _expect(errors, "file-only-happy", happy_result["arm"] == "file-only", happy_result["arm"])
        _expect(errors, "file-only-happy", happy_result["phase_3"] == "complete", happy_result["phase_3"])
        _expect(
            errors,
            "file-only-happy",
            "--metadata" not in happy_result["flags"] and "--replay" not in happy_result["flags"],
            happy_result["flags"],
        )
        _expect(errors, "file-only-happy", counts_in_file_only_tally(happy_result), "tally")

        baseline = root / "baseline"
        baseline.mkdir()
        shutil.copy(ROOT / "TASK.md", baseline / "TASK.md")
        shutil.copy(CHECKPOINT / "counts.py", baseline / "counts.py")
        baseline_result = grade(baseline, arm="baseline")
        reports.append(("baseline", baseline_result, format_report(baseline_result)))
        _expect(errors, "baseline", baseline_result["outcome"] == "fail", baseline_result["outcome"])
        _expect(errors, "baseline", baseline_result["arm"] == "baseline", baseline_result["arm"])
        _expect(errors, "baseline", not counts_in_file_only_tally(baseline_result), "folded into file-only")
        _expect(errors, "baseline", not (baseline / "task_plan.md").exists(), "task_plan.md present")
        _expect(errors, "baseline", not (baseline / "findings.md").exists(), "findings.md present")
        _expect(errors, "baseline", not (baseline / "progress.md").exists(), "progress.md present")
        baseline_reads = [path.name for path in baseline_result["reads"]]
        _expect(errors, "baseline", baseline_reads == ["counts.py"], str(baseline_reads))

        missing_counts = root / "missing-counts"
        missing_counts.mkdir()
        shutil.copy(CHECKPOINT / "task_plan.md", missing_counts / "task_plan.md")
        missing_counts_result = grade(missing_counts)
        reports.append(("missing-counts", missing_counts_result, format_report(missing_counts_result)))
        _expect(
            errors,
            "missing-counts",
            missing_counts_result["outcome"] == "inconclusive",
            missing_counts_result["outcome"],
        )
        _expect(errors, "missing-counts", not counts_in_file_only_tally(missing_counts_result), "tally")

        missing_plan = root / "missing-plan"
        missing_plan.mkdir()
        shutil.copy(COMPLETE / "counts.py", missing_plan / "counts.py")
        missing_plan_result = grade(missing_plan, arm="file-only")
        reports.append(("missing-plan", missing_plan_result, format_report(missing_plan_result)))
        _expect(
            errors,
            "missing-plan",
            missing_plan_result["outcome"] == "inconclusive",
            missing_plan_result["reason"],
        )
        _expect(errors, "missing-plan", missing_plan_result["reason"] == "task_plan.md missing", missing_plan_result["reason"])

        aborted_receipt = _write_receipt(
            root, "receipt-aborted.md", _base_rows("file-only", outcome="aborted")
        )
        aborted = grade(happy, receipt=aborted_receipt)
        reports.append(("aborted", aborted, format_report(aborted)))
        _expect(errors, "aborted", aborted["outcome"] == "inconclusive", aborted["outcome"])
        _expect(errors, "aborted", aborted["reason"] == "aborted trial", aborted["reason"])
        _expect(errors, "aborted", not counts_in_file_only_tally(aborted), "tally")

        metadata_receipt = _write_receipt(
            root, "receipt-metadata.md", _base_rows("file-only", flags="--metadata")
        )
        metadata = grade(happy, receipt=metadata_receipt)
        reports.append(("file-only-metadata", metadata, format_report(metadata)))
        _expect(errors, "file-only-metadata", metadata["outcome"] == "inconclusive", metadata["outcome"])
        _expect(errors, "file-only-metadata", not counts_in_file_only_tally(metadata), "tally")

        replay_flag_receipt = _write_receipt(
            root, "receipt-file-only-replay.md", _base_rows("file-only", flags="--replay")
        )
        replay_flag = grade(happy, receipt=replay_flag_receipt)
        reports.append(("file-only-replay-flag", replay_flag, format_report(replay_flag)))
        _expect(errors, "file-only-replay-flag", replay_flag["outcome"] == "inconclusive", replay_flag["outcome"])
        _expect(errors, "file-only-replay-flag", not counts_in_file_only_tally(replay_flag), "tally")

        replay_dir = root / "replay"
        shutil.copytree(COMPLETE, replay_dir)
        replay_receipt = _write_receipt(
            root, "receipt-replay.md", _base_rows("replay", flags="--replay")
        )
        replay = grade(replay_dir, receipt=replay_receipt)
        reports.append(("replay", replay, format_report(replay)))
        _expect(errors, "replay", replay["outcome"] == "pass", replay["outcome"])
        _expect(errors, "replay", replay["arm"] == "replay", replay["arm"])
        _expect(errors, "replay", not counts_in_file_only_tally(replay), "folded into file-only")

        store = root / ".claude" / "projects" / "demo"
        store.mkdir(parents=True)
        (store / "counts.py").write_text("def word_count(text):\n    return 0\n", encoding="utf-8")
        (store / "task_plan.md").write_text("# plan\n", encoding="utf-8")
        stored = grade(store)
        reports.append(("session-store", stored, format_report(stored)))
        _expect(errors, "session-store", stored["outcome"] == "inconclusive", stored["outcome"])
        _expect(errors, "session-store", stored["reason"] == "refusing session store path", stored["reason"])
        _expect(errors, "session-store", stored["reads"] == [], str(stored["reads"]))

    for _label, result, report in reports:
        _expect(errors, "report", _printed_outcome(report) == result["outcome"], report.splitlines()[0])
        for path in result["reads"]:
            _expect(errors, "reads", not is_session_store(path), str(path))
            _expect(
                errors,
                "reads",
                path.name in ("counts.py", "task_plan.md") or path.name.startswith("receipt-"),
                path.name,
            )

    file_only = [label for label, result, _report in reports if counts_in_file_only_tally(result)]
    _expect(errors, "tally", "baseline" not in file_only, str(file_only))
    _expect(errors, "tally", "replay" not in file_only, str(file_only))
    _expect(errors, "tally", "aborted" not in file_only, str(file_only))
    _expect(errors, "tally", "checkpoint" in file_only and "complete" in file_only, str(file_only))

    out = sys.stdout
    out.write("checkpoint: fail (not done)\n" if checkpoint["outcome"] == "fail" else "checkpoint: %s\n" % checkpoint["outcome"])
    out.write("complete: %s\n" % complete["outcome"])
    for label, _result, report in reports:
        out.write("\ntrial: %s\n" % label)
        out.write(report)
    if errors:
        out.write("\nself-check: fail\n")
        for item in errors:
            out.write("%s\n" % item)
        return 1
    out.write("\nself-check: pass\n")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Grade a file-only recovery work directory.")
    parser.add_argument("workdir", nargs="?", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)

    if args.self_check:
        if args.workdir is not None or args.arm or args.receipt:
            parser.error("--self-check does not take a workdir, arm, or receipt")
        return self_check()
    if args.workdir is None:
        parser.error("a workdir is required")

    result = grade(args.workdir, arm=args.arm, receipt=args.receipt)
    sys.stdout.write(format_report(result))
    return {"pass": 0, "fail": 1, "inconclusive": 2}[result["outcome"]]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
