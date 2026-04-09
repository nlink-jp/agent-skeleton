"""Tests for LLM content normalisation."""

import pytest

from agent.llm import _normalise_content


# ---------------------------------------------------------------------------
# Gemma-4 hallucinated tool-call tokens
# ---------------------------------------------------------------------------


def test_normalise_strips_gemma4_tool_call():
    """Gemma-4 outputs <|tool_call>...<tool_call|> in text mode."""
    raw = (
        'ファイルを確認します。'
        '<|tool_call>call:read_file{path:<|"|>test.md<|"|>}<tool_call|>'
    )
    result = _normalise_content(raw)
    assert "tool_call" not in result.text
    assert "read_file" not in result.text
    assert "ファイルを確認します。" in result.text
    assert result.tool_call_stripped is True


def test_normalise_strips_gemma4_tool_call_multiline():
    raw = (
        "前のステップ完了\n"
        "<|tool_call>\n"
        'call:file_read{"path": "test.md"}\n'
        "<tool_call|>\n"
        "次のステップへ"
    )
    result = _normalise_content(raw)
    assert "tool_call" not in result.text
    assert "file_read" not in result.text
    assert "前のステップ完了" in result.text
    assert "次のステップへ" in result.text
    assert result.tool_call_stripped is True


# ---------------------------------------------------------------------------
# Qwen3 / standard <tool_call> format (regression)
# ---------------------------------------------------------------------------


def test_normalise_strips_qwen3_tool_call():
    """Qwen3-style <tool_call>...</tool_call> must still be stripped."""
    raw = "結果を返します。<tool_call>read_file(path='a.txt')</tool_call>"
    result = _normalise_content(raw)
    assert "tool_call" not in result.text
    assert "read_file" not in result.text
    assert "結果を返します。" in result.text
    assert result.tool_call_stripped is True


# ---------------------------------------------------------------------------
# GPT-OSS special tokens (regression)
# ---------------------------------------------------------------------------


def test_normalise_strips_gpt_oss_tokens():
    raw = "正常なテキスト<|endoftext|>これは除去される"
    result = _normalise_content(raw)
    assert "正常なテキスト" in result.text
    assert "endoftext" not in result.text
    assert "これは除去される" not in result.text
    assert result.tool_call_stripped is False


# ---------------------------------------------------------------------------
# Clean text is unchanged
# ---------------------------------------------------------------------------


def test_normalise_clean_text_unchanged():
    raw = "これは普通のレスポンスです。"
    result = _normalise_content(raw)
    assert result.text == raw
    assert result.tool_call_stripped is False
