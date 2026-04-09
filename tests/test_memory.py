"""Tests for Memory: token estimation, compression trigger, message structure."""

from unittest.mock import MagicMock

import pytest

from agent.memory import Memory


def make_memory(context_limit=1000, threshold=0.5, keep_recent=2):
    llm = MagicMock()
    llm.chat.return_value = MagicMock(content="Summarised history.")
    return Memory(
        llm=llm,
        context_limit=context_limit,
        compress_threshold=threshold,
        keep_recent_turns=keep_recent,
    )


def test_add_and_get_messages():
    mem = make_memory()
    mem.add("user", "Hello")
    mem.add("assistant", "Hi there")

    messages = mem.get_messages("sys")
    assert messages[0] == {"role": "system", "content": "sys"}
    assert any(m["content"] == "Hello" for m in messages)
    assert any(m["content"] == "Hi there" for m in messages)


def test_token_estimation():
    mem = make_memory()
    mem.add("user", "a" * 400)   # 400 chars → 100 tokens
    assert mem.estimate_tokens() == 100


def test_compression_triggered(monkeypatch):
    # context_limit=100, threshold=0.5 → compress at 50 tokens (200 chars)
    mem = make_memory(context_limit=100, threshold=0.5, keep_recent=2)

    # Add messages that exceed the threshold
    for i in range(6):
        mem.add("user", f"msg{i} " + "x" * 30)

    # Compression should have been called
    assert mem._llm.chat.called
    assert mem.compressed_summary == "Summarised history."
    # Only keep_recent=2 messages should remain in messages list
    assert len(mem.messages) <= 2


def test_get_messages_includes_summary():
    mem = make_memory()
    mem.compressed_summary = "Old summary"
    mem.add("user", "Recent message")

    messages = mem.get_messages("system prompt")
    contents = [m["content"] for m in messages]
    assert any("Old summary" in c for c in contents)
    assert any("Recent message" in c for c in contents)


def test_summary_accumulated_on_second_compression():
    mem = make_memory(context_limit=100, threshold=0.5, keep_recent=1)
    mem._llm.chat.return_value = MagicMock(content="New summary.")

    # First compression
    mem.compressed_summary = "Existing summary."
    for i in range(4):
        mem.add("user", "x" * 60)

    # New summary should incorporate existing summary in the prompt
    call_args = mem._llm.chat.call_args
    history_text = call_args[0][0][1]["content"]  # second message = history
    assert "Existing summary" in history_text
