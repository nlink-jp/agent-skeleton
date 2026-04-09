# Changelog

All notable changes to this project will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) +
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
