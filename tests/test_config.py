"""Tests for config loading and unknown-key detection."""

import logging
from pathlib import Path

import pytest

from agent.config import load_config, AgentConfig, LLMConfig


@pytest.fixture()
def _propagate_agent_logs():
    """Temporarily enable propagation so caplog can capture agent.* logs."""
    logger = logging.getLogger("agent")
    original = logger.propagate
    logger.propagate = True
    yield
    logger.propagate = original


@pytest.mark.usefixtures("_propagate_agent_logs")
def test_unknown_key_warning(tmp_path, caplog):
    """Unknown keys in config should trigger a warning."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""\
[llm]
base_url = "http://localhost:1234/v1"
modl = "gemma-4"

[agent]
compres_threshold = 0.5
""")

    with caplog.at_level(logging.WARNING):
        cfg = load_config(config_file)

    # Typos should be warned about
    assert any("modl" in r.message for r in caplog.records)
    assert any("compres_threshold" in r.message for r in caplog.records)

    # Valid fields should still be loaded
    assert cfg.llm.base_url == "http://localhost:1234/v1"
    # Typo'd fields should NOT be loaded (defaults remain)
    assert cfg.llm.model == "local-model"  # default, not "gemma-4"
    assert cfg.agent.compress_threshold == 0.75  # default


@pytest.mark.usefixtures("_propagate_agent_logs")
def test_unknown_top_level_key_warning(tmp_path, caplog):
    """Unknown top-level keys should trigger a warning."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""\
[llm]
model = "test"

[agnet]
max_iterations = 10
""")

    with caplog.at_level(logging.WARNING):
        cfg = load_config(config_file)

    assert any("agnet" in r.message for r in caplog.records)
    # Agent config should have defaults (typo'd section was ignored)
    assert cfg.agent.max_iterations == 20


@pytest.mark.usefixtures("_propagate_agent_logs")
def test_valid_config_no_warnings(tmp_path, caplog):
    """Valid config should produce no warnings."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""\
[llm]
model = "gemma-4"
context_limit = 131072

[agent]
compress_threshold = 0.8
max_tool_output_chars = 50000
""")

    with caplog.at_level(logging.WARNING):
        cfg = load_config(config_file)

    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_records) == 0
    assert cfg.llm.model == "gemma-4"
    assert cfg.agent.max_tool_output_chars == 50000
