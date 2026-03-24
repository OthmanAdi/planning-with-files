#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path

FILES = ["task_plan.md", "findings.md", "progress.md"]


def export_state(output: Path):
    root = Path.cwd()
    payload = {
        "component": "planning-with-files",
        "exported_at": datetime.now().isoformat(),
        "files": {},
    }
    for name in FILES:
        p = root / name
        payload["files"][name] = p.read_text(encoding="utf-8") if p.exists() else None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def import_state(input_path: Path):
    root = Path.cwd()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    for name, content in payload.get("files", {}).items():
        if name in FILES and content is not None:
            (root / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="planning-with-files stack contract helper")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--output", required=True)
    im = sub.add_parser("import")
    im.add_argument("--input", required=True)
    args = parser.parse_args()
    if args.cmd == "export":
        export_state(Path(args.output))
    else:
        import_state(Path(args.input))
