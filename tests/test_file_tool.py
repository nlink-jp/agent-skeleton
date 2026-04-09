"""Tests for FileReadTool, FileWriteTool, and DirectoryListTool."""

import pytest

from agent.tools.file_tool import DirectoryListTool, FileReadTool, FileWriteTool


def test_write_and_read(tmp_path):
    path = tmp_path / "hello.txt"
    writer = FileWriteTool()
    result = writer.execute(path=str(path), content="hello world")
    assert result.success
    assert "hello world" in result.output or str(path) in result.output

    reader = FileReadTool()
    result = reader.execute(path=str(path))
    assert result.success
    assert result.output == "hello world"


def test_write_creates_parent_dirs(tmp_path):
    path = tmp_path / "a" / "b" / "c.txt"
    writer = FileWriteTool()
    result = writer.execute(path=str(path), content="nested")
    assert result.success
    assert path.exists()


def test_read_missing_file(tmp_path):
    reader = FileReadTool()
    result = reader.execute(path=str(tmp_path / "nonexistent.txt"))
    assert not result.success
    assert "not found" in result.error.lower() or result.error


def test_write_overwrites(tmp_path):
    path = tmp_path / "file.txt"
    writer = FileWriteTool()
    writer.execute(path=str(path), content="first")
    writer.execute(path=str(path), content="second")

    reader = FileReadTool()
    result = reader.execute(path=str(path))
    assert result.success
    assert result.output == "second"


# ---------------------------------------------------------------------------
# DirectoryListTool
# ---------------------------------------------------------------------------

def test_list_directory(tmp_path):
    (tmp_path / "file.txt").write_text("hi")
    (tmp_path / "subdir").mkdir()
    tool = DirectoryListTool()
    result = tool.execute(path=str(tmp_path))
    assert result.success
    assert "subdir/" in result.output
    assert "file.txt" in result.output


def test_list_dirs_before_files(tmp_path):
    (tmp_path / "z.txt").write_text("z")
    (tmp_path / "adir").mkdir()
    tool = DirectoryListTool()
    result = tool.execute(path=str(tmp_path))
    assert result.success
    lines = result.output.splitlines()
    dir_idx = next(i for i, l in enumerate(lines) if "adir/" in l)
    file_idx = next(i for i, l in enumerate(lines) if "z.txt" in l)
    assert dir_idx < file_idx


def test_list_hidden_excluded_by_default(tmp_path):
    (tmp_path / ".hidden").write_text("x")
    (tmp_path / "visible.txt").write_text("y")
    tool = DirectoryListTool()
    result = tool.execute(path=str(tmp_path))
    assert result.success
    assert ".hidden" not in result.output
    assert "visible.txt" in result.output


def test_list_hidden_included_when_requested(tmp_path):
    (tmp_path / ".hidden").write_text("x")
    tool = DirectoryListTool()
    result = tool.execute(path=str(tmp_path), show_hidden=True)
    assert result.success
    assert ".hidden" in result.output


def test_list_default_path_is_cwd():
    tool = DirectoryListTool()
    result = tool.execute()
    assert result.success


def test_list_missing_path(tmp_path):
    tool = DirectoryListTool()
    result = tool.execute(path=str(tmp_path / "nonexistent"))
    assert not result.success
    assert "not found" in result.error.lower()


def test_list_file_as_path(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    tool = DirectoryListTool()
    result = tool.execute(path=str(f))
    assert not result.success
    assert "not a directory" in result.error.lower()


def test_list_guard_denied(tmp_path):
    from agent.security import PathGuard
    guard = PathGuard(cwd=tmp_path)
    tool = DirectoryListTool(path_guard=guard)
    result = tool.execute(path="/etc")
    assert not result.success
    assert "Access denied" in result.error
