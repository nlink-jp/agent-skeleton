from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .config import Config, load_config
from .executor import Executor
from .llm import LLMClient
from .log import get_logger
from .memory import Memory
from .planner import Planner
from .security import PathGuard
from .tools.base import Tool
from .tools.file_tool import DirectoryListTool, FileReadTool, FileWriteTool
from .tools.shell_tool import ShellTool
from .tools.web_tool import WebSearchTool

log = get_logger(__name__)

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
        log.info(
            "Agent.from_config: model=%s context_limit=%d",
            cfg.llm.model,
            cfg.llm.context_limit,
        )
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

        path_guard = PathGuard(extra_allowed=cfg.security.allowed_paths)

        builtin_tools: list[Tool] = [
            DirectoryListTool(path_guard=path_guard),
            FileReadTool(path_guard=path_guard),
            FileWriteTool(path_guard=path_guard),
            ShellTool(path_guard=path_guard),
            WebSearchTool(),
        ]
        mcp_tools = cls._load_mcp_tools(cfg)
        all_tools = builtin_tools + mcp_tools
        log.info(
            "Tools loaded: %d built-in + %d MCP = %d total",
            len(builtin_tools),
            len(mcp_tools),
            len(all_tools),
        )

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
        log.info("Agent.plan: %r", user_goal)
        history = self._memory.get_messages(AGENT_SYSTEM_PROMPT)
        return self._planner.create_plan(user_goal, history=history)

    def format_plan(self, plan: dict) -> str:
        return self._planner.format_plan(plan)

    def execute(self, user_goal: str, plan: dict) -> str:
        """Execute the goal via ReAct loop, record in memory, return combined result.

        The *plan* argument is retained for display / approval in the CLI but
        execution itself is dynamic: the LLM decides which tool to call next
        after observing all accumulated results, so sub-steps discovered at
        runtime (e.g. inside a procedure document) are handled naturally.
        """
        log.info("Agent.execute: starting plan with %d step(s)", len(plan.get("steps", [])))
        history = self._memory.get_messages(AGENT_SYSTEM_PROMPT)
        log.debug("Agent.execute: history has %d message(s)", len(history))

        step_results = self._executor.execute_react(user_goal, history)
        combined = "\n".join(step_results)

        self._memory.add("user", user_goal)
        self._memory.add("assistant", combined)
        log.info("Agent.execute: done. Memory tokens ≈ %d", self._memory.estimate_tokens())
        return combined

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _load_mcp_tools(cfg: Config) -> list[Tool]:
        if not cfg.mcp_servers:
            log.debug("No MCP servers configured")
            return []
        log.info("Loading MCP tools from %d server(s): %s", len(cfg.mcp_servers), list(cfg.mcp_servers))
        try:
            from .mcp.client import MCPManager
            manager = MCPManager()
            tools = manager.load_all(cfg.mcp_servers)
            log.info("MCP tools loaded: %d tool(s)", len(tools))
            return tools
        except Exception as e:
            log.warning("MCP tool loading failed: %s", e)
            return []
