from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .config import Config, load_config
from .executor import Executor
from .llm import LLMClient
from .memory import Memory
from .planner import Planner
from .tools.base import Tool
from .tools.file_tool import FileReadTool, FileWriteTool
from .tools.shell_tool import ShellTool
from .tools.web_tool import WebSearchTool

AGENT_SYSTEM_PROMPT = """\
You are a capable autonomous agent. You help users accomplish their goals by planning \
and executing tasks step by step using available tools. \
Be concise, accurate, and always explain what you are doing and why.
"""

ApproverFn = Callable[[str, dict, str], bool]


class Agent:
    """High-level orchestrator: plan → (user approval) → execute."""

    def __init__(
        self,
        llm: LLMClient,
        memory: Memory,
        planner: Planner,
        executor: Executor,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._planner = planner
        self._executor = executor

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        approver: ApproverFn,
        config_path: Path | None = None,
    ) -> Agent:
        cfg: Config = load_config(config_path)
        llm = LLMClient(
            base_url=cfg.llm.base_url,
            api_key=cfg.llm.api_key,
            model=cfg.llm.model,
        )
        memory = Memory(
            llm=llm,
            context_limit=cfg.llm.context_limit,
            compress_threshold=cfg.agent.compress_threshold,
            keep_recent_turns=cfg.agent.keep_recent_turns,
        )

        builtin_tools: list[Tool] = [
            FileReadTool(),
            FileWriteTool(),
            ShellTool(),
            WebSearchTool(),
        ]
        mcp_tools = cls._load_mcp_tools(cfg)
        all_tools = builtin_tools + mcp_tools

        planner = Planner(llm=llm, tools=all_tools)
        executor = Executor(
            llm=llm,
            tools=all_tools,
            approver=approver,
            max_iterations=cfg.agent.max_iterations,
        )
        return cls(llm=llm, memory=memory, planner=planner, executor=executor)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, user_goal: str) -> dict:
        """Generate and return a plan for the given goal."""
        return self._planner.create_plan(user_goal)

    def format_plan(self, plan: dict) -> str:
        return self._planner.format_plan(plan)

    def execute(self, user_goal: str, plan: dict) -> str:
        """Execute plan, record in memory, return combined result."""
        history = self._memory.get_messages(AGENT_SYSTEM_PROMPT)
        step_results = self._executor.execute_plan(plan, history)
        combined = "\n".join(step_results)

        self._memory.add("user", user_goal)
        self._memory.add("assistant", combined)
        return combined

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _load_mcp_tools(cfg: Config) -> list[Tool]:
        if not cfg.mcp_servers:
            return []
        try:
            from .mcp.client import MCPManager
            manager = MCPManager()
            return manager.load_all(cfg.mcp_servers)
        except Exception as e:
            print(f"[警告] MCP ツールの読み込みに失敗しました: {e}")
            return []
