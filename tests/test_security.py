"""Tests for PathGuard and its integration with file/shell tools."""

import pytest
from pathlib import Path

from agent.security import PathGuard, _extract_abs_paths
from agent.tools.file_tool import FileReadTool, FileWriteTool
from agent.tools.shell_tool import ShellTool


# ---------------------------------------------------------------------------
# PathGuard.is_allowed / check_path
# ---------------------------------------------------------------------------

@pytest.fixture
def guard(tmp_path):
    """PathGuard with cwd=tmp_path and no extras."""
    return PathGuard(cwd=tmp_path)


def test_cwd_is_allowed(guard, tmp_path):
    assert guard.is_allowed(tmp_path)


def test_child_of_cwd_is_allowed(guard, tmp_path):
    assert guard.is_allowed(tmp_path / "subdir" / "file.txt")


def test_tmp_is_allowed(guard):
    assert guard.is_allowed("/tmp")
    assert guard.is_allowed("/tmp/workfile.txt")


def test_pseudo_devices_are_allowed(guard):
    assert guard.is_allowed("/dev/null")
    assert guard.is_allowed("/dev/stdin")
    assert guard.is_allowed("/dev/stdout")
    assert guard.is_allowed("/dev/stderr")
    assert guard.is_allowed("/dev/zero")
    assert guard.is_allowed("/dev/urandom")


def test_block_devices_are_denied(guard):
    assert not guard.is_allowed("/dev/sda")
    assert not guard.is_allowed("/dev/disk0")
    assert not guard.is_allowed("/dev/sda1")


def test_check_command_dev_null_allowed(guard):
    assert guard.check_command("ls -la *.md 2>/dev/null") is None
    assert guard.check_command("cat file.txt > /dev/null") is None


def test_outside_roots_denied(guard):
    assert not guard.is_allowed("/etc/passwd")
    assert not guard.is_allowed("/usr/bin/python")
    assert not guard.is_allowed("/home/user/.ssh/id_rsa")


def test_check_path_returns_none_when_allowed(guard, tmp_path):
    assert guard.check_path(tmp_path / "ok.txt") is None
    assert guard.check_path("/tmp/ok.txt") is None


def test_check_path_returns_error_when_denied(guard):
    err = guard.check_path("/etc/shadow")
    assert err is not None
    assert "Access denied" in err
    assert "/etc/shadow" in err


def test_extra_allowed_root(tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    guard = PathGuard(cwd=tmp_path / "cwd", extra_allowed=[str(extra)])
    assert guard.is_allowed(extra / "file.txt")


def test_parent_traversal_blocked(guard, tmp_path):
    # Resolving ../ should NOT escape the allowed root
    tricky = tmp_path / "sub" / ".." / ".." / "etc" / "passwd"
    assert not guard.is_allowed(tricky)


# ---------------------------------------------------------------------------
# _extract_abs_paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command,expected", [
    ("cat /etc/passwd", ["/etc/passwd"]),
    ("ls /usr/local/bin", ["/usr/local/bin"]),
    ("echo x > /tmp/out.txt", ["/tmp/out.txt"]),
    ("find /home -name '*.py'", ["/home"]),
    ("ls -la", []),
    ("echo hello", []),
    ("python3 /scripts/run.py -o /tmp/result.json", ["/scripts/run.py", "/tmp/result.json"]),
])
def test_extract_abs_paths(command, expected):
    result = _extract_abs_paths(command)
    for p in expected:
        assert p in result


# ---------------------------------------------------------------------------
# PathGuard.check_command
# ---------------------------------------------------------------------------

def test_check_command_allowed(guard, tmp_path):
    cmd = f"ls {tmp_path}"
    assert guard.check_command(cmd) is None


def test_check_command_allowed_tmp(guard):
    assert guard.check_command("echo hello > /tmp/out.txt") is None


def test_check_command_denied(guard):
    err = guard.check_command("cat /etc/passwd")
    assert err is not None
    assert "Access denied" in err


def test_check_command_no_abs_paths(guard):
    assert guard.check_command("ls -la") is None
    assert guard.check_command("echo hello world") is None


def test_check_command_mixed_paths(guard, tmp_path):
    # One allowed, one denied → should fail
    cmd = f"cat {tmp_path}/ok.txt /etc/shadow"
    err = guard.check_command(cmd)
    assert err is not None


# ---------------------------------------------------------------------------
# FileReadTool integration
# ---------------------------------------------------------------------------

def test_file_read_allowed(tmp_path, guard):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    tool = FileReadTool(path_guard=guard)
    result = tool.execute(path=str(f))
    assert result.success
    assert result.output == "hello"


def test_file_read_denied(guard):
    tool = FileReadTool(path_guard=guard)
    result = tool.execute(path="/etc/passwd")
    assert not result.success
    assert "Access denied" in result.error


def test_file_read_no_guard(tmp_path):
    """Without a guard, any path is accepted (tool decides success/failure)."""
    tool = FileReadTool(path_guard=None)
    result = tool.execute(path="/nonexistent_file_xyz")
    assert not result.success
    assert "Access denied" not in result.error  # guard not triggered


# ---------------------------------------------------------------------------
# FileWriteTool integration
# ---------------------------------------------------------------------------

def test_file_write_allowed(tmp_path, guard):
    tool = FileWriteTool(path_guard=guard)
    out = tmp_path / "out.txt"
    result = tool.execute(path=str(out), content="data")
    assert result.success
    assert out.read_text() == "data"


def test_file_write_denied(guard):
    tool = FileWriteTool(path_guard=guard)
    result = tool.execute(path="/etc/crontab", content="malicious")
    assert not result.success
    assert "Access denied" in result.error


def test_file_write_tmp_allowed(guard):
    tool = FileWriteTool(path_guard=guard)
    result = tool.execute(path="/tmp/agent_test_output.txt", content="ok")
    assert result.success


# ---------------------------------------------------------------------------
# ShellTool integration
# ---------------------------------------------------------------------------

def test_shell_allowed_command(guard):
    tool = ShellTool(path_guard=guard)
    result = tool.execute(command="echo hello")
    assert result.success
    assert "hello" in result.output


def test_shell_denied_path_in_command(guard):
    tool = ShellTool(path_guard=guard)
    result = tool.execute(command="cat /etc/passwd")
    assert not result.success
    assert "Access denied" in result.error


def test_shell_allowed_tmp_path(guard):
    tool = ShellTool(path_guard=guard)
    result = tool.execute(command="echo test > /tmp/agent_guard_test.txt && cat /tmp/agent_guard_test.txt")
    assert result.success


def test_shell_dangerous_takes_priority(guard):
    """Dangerous pattern check must fire before path guard."""
    tool = ShellTool(path_guard=guard)
    result = tool.execute(command="rm -rf /tmp/something")
    assert not result.success
    # Should be refused by dangerous pattern, not path guard
    assert "dangerous pattern" in result.error
