# agent-skeleton

Proof-of-concept skeleton for an autonomous agent. Demonstrates the core loop of plan → approve → execute with built-in tools and MCP server support.

## Features

- **Plan-first execution** — generates a step-by-step plan from natural language, shows it to the user for approval before doing anything
- **ReAct execution loop** — after plan approval, the LLM dynamically picks tools based on accumulated results (not locked to the plan); plan tool names are passed as non-binding hints
- **Per-tool approval** — before every tool call, displays the tool name, arguments, and reason; waits for user confirmation
- **Multi-turn memory** — retains conversation history with automatic LLM-based context compression when the context window fills
- **Built-in tools** — `ls`, `file_read`, `file_write`, `shell_exec` (with dangerous command guard), `web_search` (DuckDuckGo)
- **MCP support** — connects to MCP servers (stdio or SSE) at startup; MCP tools appear alongside built-in tools
- **Local LLM normalisation** — strips model-internal markup (GPT-OSS tokens, thinking blocks, hallucinated tool calls for Gemma-4/Qwen3, Mistral template tokens)
- **Core/UI separation** — `agent/` package is independently importable; CLI is a thin wrapper

## Installation

Requires [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/nlink-jp/agent-skeleton
cd agent-skeleton
uv sync
```

## Configuration

Copy the example config and edit:

```bash
mkdir -p ~/.config/agent-skeleton
cp config.example.toml ~/.config/agent-skeleton/config.toml
$EDITOR ~/.config/agent-skeleton/config.toml
```

Minimum required settings:

```toml
[llm]
base_url = "http://localhost:1234/v1"   # your local LLM endpoint
model    = "your-model-name"
```

## Usage

```bash
uv run python main.py
```

The agent will prompt you for a goal, generate a plan, ask for approval, then execute step by step.

## Building (tests)

```bash
uv run pytest
```

## Using `agent/` as a library

```python
from agent import Agent

def my_approver(tool_name: str, args: dict, reason: str) -> bool:
    print(f"Tool: {tool_name}, Reason: {reason}")
    return input("Execute? [y/n] ").lower() == "y"

agent = Agent.from_config(approver=my_approver)
plan = agent.plan("List all Python files in the current directory")
print(agent.format_plan(plan))
result = agent.execute("List all Python files in the current directory", plan)
print(result)
```

## Architecture

```
User input
  → Planner.create_plan()        # LLM generates JSON plan
  → CLI displays plan            # user approves/cancels
  → Executor.execute_react()     # ReAct loop (dynamic tool selection)
      → LLM picks a tool (with all tools + plan hints)
      → approver(tool, args, reason)  # user approves/skips
      → Tool.execute()
      → LLM summarises, decides next action or finishes
  → result stored in Memory
```

Context compression triggers when estimated tokens exceed `context_limit × compress_threshold` (default: 64K × 0.75 = 48K). Older turns are summarised by the LLM; the most recent `keep_recent_turns` turns are kept verbatim.

## Documentation

- [日本語 README](README.ja.md)
- [Architecture](docs/architecture.md) / [アーキテクチャ (ja)](docs/architecture.ja.md)
- [Prompt Injection Demo](docs/demo-prompt-injection.md) / [デモ (ja)](docs/demo-prompt-injection.ja.md)
- [Changelog](CHANGELOG.md)
- [Config example](config.example.toml)
