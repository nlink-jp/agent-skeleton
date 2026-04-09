"""Tests for FileReadTool and FileWriteTool."""

import pytest

from agent.tools.file_tool import FileReadTool, FileWriteTool


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
