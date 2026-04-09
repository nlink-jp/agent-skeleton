# AGENTS.md — agent-skeleton

## Project summary

Proof-of-concept skeleton for an autonomous agent that:
1. Receives a natural-language goal from the user
2. Generates a step-by-step plan using available tools
3. Presents the plan to the user for approval
4. Executes each step, requesting per-tool approval before every call
5. Maintains multi-turn memory with LLM-based context compression

Module path: `github.com/nlink-jp/agent-skeleton` (Python, uv)

## Build / run commands

```bash
uv sync                        # install dependencies
uv run python main.py          # start interactive CLI
uv run pytest                  # run all tests
uv run pytest tests/test_shell_tool.py -v   # specific test file
```

## Key directory structure

```
agent-skeleton/
├── main.py                    ← entry point
├── agent/                     ← core package (import as `from agent import Agent`)
│   ├── agent.py               ← Agent class, from_config, plan, execute
│   ├── config.py              ← TOML config loading, dataclasses
│   ├── llm.py                 ← OpenAI-compatible LLM client
│   ├── memory.py              ← 2-tier memory + compression
│   ├── planner.py             ← JSON plan generation + formatting
│   ├── executor.py            ← step execution, per-tool approval loop
│   ├── tools/
│   │   ├── base.py            ← Tool ABC, ToolResult
│   │   ├── file_tool.py       ← DirectoryListTool(ls), FileReadTool, FileWriteTool
│   │   ├── shell_tool.py      ← ShellTool + dangerous pattern guard
│   │   └── web_tool.py        ← WebSearchTool (DuckDuckGo)
│   └── mcp/
│       └── client.py          ← MCPManager, MCPTool (stdio + SSE)
├── cli/
│   └── app.py                 ← Rich CLI, approval dialogs
└── tests/
    ├── test_executor.py       ← ReAct loop, tool_hints, injection detection
    ├── test_file_tool.py
    ├── test_llm.py            ← Content normalisation (Gemma-4/Qwen3/GPT-OSS)
    ├── test_memory.py
    ├── test_planner.py
    ├── test_security.py       ← PathGuard (30 tests)
    └── test_shell_tool.py
```

## Environment variables / config

No environment variables required. Configuration via:
`~/.config/agent-skeleton/config.toml` (see `config.example.toml`)

Key settings:
- `llm.base_url` — OpenAI-compatible endpoint (default: `http://localhost:1234/v1`)
- `llm.context_limit` — effective token limit (default: 65536)
- `agent.compress_threshold` — compression trigger fraction (default: 0.75)
- `mcp.servers.*` — MCP server definitions (stdio or sse)

## Gotchas

- **MCP reconnects per call**: each `MCPTool.execute()` opens a fresh connection. Efficient for POC; replace with persistent sessions for production use.
- **Token estimation**: uses `chars // 4` approximation. Sufficient for triggering compression; not exact.
- **Shell safety**: `ShellTool` refuses dangerous commands unconditionally (before the user approval step). The approval callback is never called for refused commands.
- **Planner JSON fallback**: if the LLM returns malformed JSON, `Planner._parse_plan()` falls back to a single-step plan so execution can still proceed.
- **Gemma-4 normalisation**: Gemma-4 outputs `<|tool_call>...<tool_call|>` (pipe-delimited) in text mode instead of using OpenAI function calling. The normaliser strips these; `tool_call_stripped` flag distinguishes this from prompt injection.
- **Core/CLI separation**: `agent/` has no dependency on `cli/`. Import direction is strictly `cli → agent`.
