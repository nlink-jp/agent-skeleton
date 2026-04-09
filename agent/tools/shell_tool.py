import re
import subprocess

from .base import Tool, ToolResult

# Patterns that are unconditionally refused regardless of user approval.
# These represent commands that could cause irreversible system damage.
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+/", "recursive delete from root"),
    (r"rm\s+-[a-zA-Z]*f[a-zA-Z]*\s+/", "force delete from root"),
    (r":\(\)\s*\{.*\}\s*;", "fork bomb"),
    (r"mkfs\.", "filesystem format"),
    (r"\bdd\b.*\bif=", "disk write via dd"),
    (r">\s*/dev/sd[a-z]", "direct device write"),
    (r"chmod\s+-R\s+[0-7]*7[0-7]*\s+/", "world-writable chmod on root"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "system shutdown/reboot"),
    (r"curl\s+[^\|]+\|\s*(ba)?sh", "pipe curl to shell"),
    (r"wget\s+[^\|]+\|\s*(ba)?sh", "pipe wget to shell"),
    (r"curl\s+[^\|]+\|\s*python", "pipe curl to python"),
]


class ShellTool(Tool):
    @property
    def name(self) -> str:
        return "shell_exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return stdout/stderr. Dangerous commands are refused."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

    def _check_dangerous(self, command: str) -> str | None:
        for pattern, reason in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
                return reason
        return None

    def execute(self, **kwargs) -> ToolResult:
        command: str = kwargs.get("command", "")
        timeout: int = int(kwargs.get("timeout", 30))

        danger = self._check_dangerous(command)
        if danger:
            return ToolResult(
                success=False,
                output="",
                error=f"Refused: command matches dangerous pattern ({danger})",
            )

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = proc.stdout
            if proc.returncode != 0 and proc.stderr:
                output += f"\n[stderr]\n{proc.stderr.strip()}"
            return ToolResult(
                success=proc.returncode == 0,
                output=output,
                error=proc.stderr if proc.returncode != 0 else "",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error=f"Timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
