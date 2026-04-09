from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import Tool, ToolResult

if TYPE_CHECKING:
    from ..security import PathGuard


class FileReadTool(Tool):
    def __init__(self, path_guard: PathGuard | None = None) -> None:
        self._guard = path_guard

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a file from the filesystem."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file"},
            },
            "required": ["path"],
        }

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")

        if self._guard:
            err = self._guard.check_path(path)
            if err:
                return ToolResult(success=False, output="", error=err)

        try:
            content = Path(path).read_text(encoding="utf-8")
            return ToolResult(success=True, output=content)
        except FileNotFoundError:
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class DirectoryListTool(Tool):
    def __init__(self, path_guard: PathGuard | None = None) -> None:
        self._guard = path_guard

    @property
    def name(self) -> str:
        return "directory_list"

    @property
    def description(self) -> str:
        return "List files and directories at a given path (like ls). Returns names, types, and sizes."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Defaults to current working directory.",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files (starting with '.'). Default: false.",
                },
            },
            "required": [],
        }

    def execute(self, **kwargs) -> ToolResult:
        raw_path: str = kwargs.get("path", ".") or "."
        show_hidden: bool = bool(kwargs.get("show_hidden", False))

        if self._guard:
            err = self._guard.check_path(raw_path)
            if err:
                return ToolResult(success=False, output="", error=err)

        try:
            p = Path(raw_path).resolve()
            if not p.exists():
                return ToolResult(success=False, output="", error=f"Path not found: {raw_path}")
            if not p.is_dir():
                return ToolResult(success=False, output="", error=f"Not a directory: {raw_path}")

            entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            lines: list[str] = [f"{p}/"]
            for entry in entries:
                if not show_hidden and entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    lines.append(f"  {entry.name}/")
                elif entry.is_file():
                    size = entry.stat().st_size
                    lines.append(f"  {entry.name}  ({size:,} bytes)")
                else:
                    lines.append(f"  {entry.name}  (other)")

            return ToolResult(success=True, output="\n".join(lines))
        except PermissionError:
            return ToolResult(success=False, output="", error=f"Permission denied: {raw_path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileWriteTool(Tool):
    def __init__(self, path_guard: PathGuard | None = None) -> None:
        self._guard = path_guard

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write content to a file, creating parent directories as needed."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        }

    def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        if self._guard:
            err = self._guard.check_path(path)
            if err:
                return ToolResult(success=False, output="", error=err)

        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Wrote {len(content)} chars to {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
