from __future__ import annotations

from typing import Any

from .hooks import post_tool_call, pre_llm_call
from .tools import (
    planning_with_files_check_complete,
    planning_with_files_init,
    planning_with_files_status,
)


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="planning_with_files_init",
        toolset="terminal",
        schema={
            "name": "planning_with_files_init",
            "description": "Create planning-with-files markdown files in the current project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Template name, e.g. default or analytics."},
                    "cwd": {"type": "string", "description": "Target project directory. Defaults to current working directory."},
                },
            },
        },
        handler=lambda args, **kw: planning_with_files_init(
            template=args.get("template", "default"),
            cwd=args.get("cwd", ""),
        ),
        description="Initialize planning-with-files state files.",
    )
    ctx.register_tool(
        name="planning_with_files_status",
        toolset="terminal",
        schema={
            "name": "planning_with_files_status",
            "description": "Summarize current planning file status for the active project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Target project directory. Defaults to current working directory."},
                },
            },
        },
        handler=lambda args, **kw: planning_with_files_status(cwd=args.get("cwd", "")),
        description="Show planning-with-files status summary.",
    )
    ctx.register_tool(
        name="planning_with_files_check_complete",
        toolset="terminal",
        schema={
            "name": "planning_with_files_check_complete",
            "description": "Run the planning-with-files completion check script.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string", "description": "Target project directory. Defaults to current working directory."},
                },
            },
        },
        handler=lambda args, **kw: planning_with_files_check_complete(cwd=args.get("cwd", "")),
        description="Check whether all planning phases are complete.",
    )
    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_tool_call", post_tool_call)
