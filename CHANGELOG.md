# Changelog

All notable changes to this project will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) +
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `agent/security.py`: `PathGuard` — restricts file and shell access to allowed directory roots (cwd, /tmp, and configurable extras)
- `FileReadTool`, `FileWriteTool`, `ShellTool` now accept `path_guard` constructor argument; paths outside allowed roots return `ToolResult(success=False)` before execution
- `ShellTool.check_command()`: heuristic absolute-path extraction via `shlex` + redirect regex
- Config: `[security] allowed_paths` list for additional allowed roots
- Tests: `tests/test_security.py` — 30+ cases covering `PathGuard`, tool integration, path traversal, and priority ordering (dangerous pattern > path guard)

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
