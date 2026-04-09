# Changelog

All notable changes to this project will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) +
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.12] - 2026-04-09

### Fixed
- PathGuard: tighten pseudo-device allowlist — permit only safe devices (`/dev/null`, stdio, `urandom`, `/dev/fd/*`); block devices (`/dev/sda`, `/dev/disk*`) remain denied

## [0.1.11] - 2026-04-09

### Fixed
- PathGuard: allow `/dev/` subtree (pseudo-devices such as `/dev/null`, `/dev/stdin`); previously `2>/dev/null` in shell commands was incorrectly rejected
- Executor: strip raw XML `<tool_call>` markup from text-mode LLM responses; some local LLMs emit these tags when forced to a no-tools call, which polluted `previous_results` for subsequent steps

## [0.1.10] - 2026-04-09

### Added
- Built-in tool `directory_list`: list files and directories at a given path (like `ls`); shows names, types (file/dir), sizes; supports `show_hidden` flag and PathGuard integration

## [0.1.9] - 2026-04-09

### Changed
- CLI: replace `input()` with `prompt_toolkit.prompt()` for user message entry; fixes multibyte (Japanese/CJK) cursor movement and deletion on macOS where Python's `input()` is backed by libedit instead of GNU readline

## [0.1.8] - 2026-04-09

### Fixed
- Planner: pass prior user/assistant turns from memory to `create_plan()`; previously the planner had no conversation context, causing incorrect plans for memory-referencing requests

## [0.1.7] - 2026-04-09

### Fixed
- Executor: exclude old user/assistant conversation turns from tool-call messages; only system messages (agent prompt + compressed summary) are forwarded to each step. Previous turns caused the LLM to hallucinate tool arguments from stale memory instead of current step context.

## [0.1.6] - 2026-04-09

### Changed
- Migrate web search dependency from `duckduckgo-search` to `ddgs` (package renamed in v8); update import in `web_tool.py`

## [0.1.5] - 2026-04-09

### Fixed
- Executor: deduplicate tool_calls by `(name, arguments)` before processing; some models (e.g. Gemma-4) return dozens of identical calls in a single response

## [0.1.4] - 2026-04-09

### Fixed
- CLI: pass prompt string directly to `input()` so readline correctly tracks cursor position; fixes multibyte (Japanese/CJK) backspace on all terminals

## [0.1.3] - 2026-04-09

### Fixed
- CLI: replace `rich.prompt.Prompt.ask()` with `console.print()` + `input()` for user message entry; fixes backspace corruption of multibyte (Japanese/CJK) characters

## [0.1.2] - 2026-04-09

### Fixed
- Executor: call LLM without tools after each tool-execution round to force a text response; prevents infinite tool-call loops on local LLMs (Qwen3 etc.)

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
