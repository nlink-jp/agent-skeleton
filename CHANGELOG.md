# Changelog

All notable changes to this project will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) +
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-04-09

### Fixed
- Add `[build-system]` (hatchling) and explicit `[tool.hatch.build.targets.wheel]` so `uv tool install .` works correctly
- Change entry point from `main:main` to `cli.app:run` to avoid referencing a top-level module outside declared packages

## [0.1.0] - 2026-04-09

### Added
- Core agent loop: plan generation → user approval → step-by-step execution
- Per-tool execution approval dialog (tool name, arguments, reason shown before every call)
- Multi-turn conversation memory with LLM-based context compression (2-tier: verbatim recent + summarised older)
- Built-in tools: `file_read`, `file_write`, `shell_exec`, `web_search`
- Shell tool: dangerous command pattern detection (refuses unconditionally before approval)
- MCP client adapter: stdio and SSE transports, configured via TOML
- Rich-based CLI with plan display and approval prompts
- Core/UI separation: `agent/` package is independently importable
- Configuration via `~/.config/agent-skeleton/config.toml` (TOML, defaults provided)
- `agent/security.py`: `PathGuard` — restricts file and shell tool access to cwd, `/tmp`, and configurable extra roots; blocks `../` traversal
- `FileReadTool`, `FileWriteTool`, `ShellTool` accept an optional `path_guard` parameter; all path checks happen before execution
- `ShellTool.check_command()`: heuristic absolute-path extraction from shell commands (handles redirects and quoted args via `shlex`)
- Config: `[security] allowed_paths` list — extra directory roots users can grant access to
- Tests: `tests/test_security.py` — 30 tests covering PathGuard, path extraction, tool integration, traversal blocking, and dangerous-pattern priority
- Verbose structured logging via `agent/log.py`; level controlled by `AGENT_LOG_LEVEL` env var (default `INFO`)
- Architecture document: `docs/architecture.ja.md`

### Fixed
- Removed `tool_choice="auto"` from LLM requests — incompatible with Qwen3 jinja chat template in LM Studio
- Executor message list no longer prepends a second system prompt before history, eliminating consecutive system-message errors on local LLMs
