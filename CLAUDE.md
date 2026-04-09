# CLAUDE.md — agent-skeleton

**Organization rules (mandatory): https://github.com/nlink-jp/.github/blob/main/CONVENTIONS.md**

## Non-negotiable rules

- **Tests are mandatory** — write them with the implementation. A feature is not complete without tests.
- **Design for testability** — pure functions, injected dependencies, no untestable globals.
- **Docs in sync** — update `README.md` and `README.ja.md` in the same commit as behaviour changes.
- **Small, typed commits** — `feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`, `security:`

## This project

Proof-of-concept skeleton for an autonomous agent:
- `agent/` — core package (importable independently of CLI)
- `cli/` — Rich-based interactive CLI that wraps the core
- Tools: `file_read`, `file_write`, `shell_exec`, `web_search` (built-in) + MCP (configured)

## Architecture invariants

- **Core/UI separation**: never import `cli/` from `agent/`. The dependency is one-way.
- **Approver is injected**: `Executor` never prompts the user directly; it calls `approver(tool_name, args, reason) -> bool`.
- **Tool interface**: all tools (built-in and MCP) implement `agent.tools.base.Tool`. Never add tool-specific logic to `Executor` or `Agent`.
- **Memory compression**: triggered when estimated tokens exceed `context_limit × compress_threshold`. Keep the 2-tier design (verbatim recent + LLM summary).

## Running

```bash
uv sync
uv run python main.py          # interactive CLI
uv run pytest                  # tests
```

## Config

`~/.config/agent-skeleton/config.toml` — see `config.example.toml` for all options.
