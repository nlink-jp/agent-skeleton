"""Path-based access control for agent tools.

PathGuard enforces that file and shell operations stay within a set of
allowed directory roots.  It is not a strict sandbox — a shell command can
still access arbitrary paths via environment variables or indirect means —
but it provides a meaningful conceptual barrier and catches the common cases
where the LLM simply passes an out-of-scope absolute path.

Allowed roots (evaluated at instantiation time):
  1. Current working directory (and any subdirectory)
  2. /tmp (and any subdirectory)
  3. Any additional paths listed in config [security] allowed_paths
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from .log import get_logger

log = get_logger(__name__)

# Matches absolute paths that appear after redirect operators (>> / > / 2>).
# Supplements shlex tokenization which does not strip operator characters.
_REDIRECT_RE = re.compile(r"(?:>>?|2>)\s*(/[^\s'\"<>|&;`]+)")


def _is_relative_to(path: Path, root: Path) -> bool:
    """Return True if path is equal to root or a descendant of root."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _extract_abs_paths(command: str) -> list[str]:
    """Heuristically extract absolute paths from a shell command string.

    Uses shlex for main tokenisation (handles quotes) and a supplementary
    regex to catch paths after redirect operators.
    """
    found: list[str] = []

    # shlex.split handles quoted strings; operators like | ; & are kept as tokens
    try:
        tokens = shlex.split(command)
        for token in tokens:
            # Strip leading redirect operators that shlex may leave attached
            cleaned = token.lstrip("<>2")
            if cleaned.startswith("/"):
                found.append(cleaned)
    except ValueError:
        # Fallback: simple whitespace split (e.g. unterminated quotes)
        for token in command.split():
            if token.startswith("/"):
                found.append(token)

    # Supplementary: capture redirect targets (e.g. "echo x > /tmp/out.txt")
    for m in _REDIRECT_RE.finditer(command):
        p = m.group(1)
        if p not in found:
            found.append(p)

    return found


class PathGuard:
    """Restricts path access to a configurable set of allowed roots.

    Usage::

        guard = PathGuard(extra_allowed=["/data/project"])
        err = guard.check_path("/etc/passwd")   # returns error string
        err = guard.check_path("/tmp/work.txt") # returns None (allowed)
        err = guard.check_command("cat /etc/shadow")  # returns error string
    """

    def __init__(
        self,
        extra_allowed: list[str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        base_cwd = (cwd or Path.cwd()).resolve()
        self._roots: list[Path] = [
            base_cwd,
            Path("/tmp").resolve(),
        ]
        for raw in (extra_allowed or []):
            resolved = Path(raw).resolve()
            self._roots.append(resolved)

        log.info(
            "PathGuard: allowed roots = [%s]",
            ", ".join(str(r) for r in self._roots),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, path: str | Path) -> bool:
        """Return True if the resolved path falls under any allowed root."""
        try:
            resolved = Path(path).resolve()
        except Exception:
            return False
        return any(
            resolved == root or _is_relative_to(resolved, root)
            for root in self._roots
        )

    def check_path(self, path: str | Path) -> str | None:
        """Return an error string if path is outside allowed roots, else None."""
        if self.is_allowed(path):
            log.debug("PathGuard.check_path: allowed — %s", path)
            return None
        msg = (
            f"Access denied: '{path}' is outside the allowed paths. "
            f"Allowed roots: {[str(r) for r in self._roots]}"
        )
        log.warning("PathGuard: %s", msg)
        return msg

    def check_command(self, command: str) -> str | None:
        """Heuristically check absolute paths found in a shell command.

        Returns an error string for the first disallowed path, or None.
        This is best-effort: paths constructed dynamically at runtime cannot
        be detected here.
        """
        paths = _extract_abs_paths(command)
        log.debug("PathGuard.check_command: extracted paths %s from %r", paths, command[:80])
        for p in paths:
            err = self.check_path(p)
            if err:
                return err
        return None

    @property
    def allowed_roots(self) -> list[Path]:
        return list(self._roots)
