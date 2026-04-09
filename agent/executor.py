from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import LLMClient
    from .tools.base import Tool

# Signature: (tool_name: str, args: dict, reason: str) -> bool
ApproverFn = Callable[[str, dict, str], bool]

STEP_SYSTEM_PROMPT = """\
You are an autonomous execution agent. You will be given a specific step to execute.
Use the provided tool to accomplish the step. Call the tool with appropriate arguments.
"""


class Executor:
    def __init__(
        self,
        llm: LLMClient,
        tools: list[Tool],
        approver: ApproverFn,
        max_iterations: int = 20,
    ) -> None:
        self._llm = llm
        self._tools: dict[str, Tool] = {t.name: t for t in tools}
        self._approver = approver
        self._max_iterations = max_iterations

    def execute_plan(self, plan: dict, history: list[dict]) -> list[str]:
        """Execute all steps in plan. Returns per-step result strings."""
        results: list[str] = []
        for step in plan.get("steps", []):
            result = self._execute_step(step, history, results)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_step(
        self,
        step: dict,
        history: list[dict],
        previous_results: list[str],
    ) -> str:
        n = step["step"]
        description = step["description"]
        tool_name: str | None = step.get("tool")
        reason: str = step.get("reason", "")

        # Steps with no tool: ask LLM for a text response
        if not tool_name:
            context = self._build_context(description, reason, previous_results)
            messages = history + [{"role": "user", "content": context}]
            response = self._llm.chat(messages)
            return f"[ステップ {n}] {response.content or '完了'}"

        tool = self._tools.get(tool_name)
        if tool is None:
            return f"[ステップ {n}] エラー: ツール '{tool_name}' が見つかりません"

        # Ask LLM to determine exact arguments via tool_call
        context = self._build_context(description, reason, previous_results)
        messages = [
            {"role": "system", "content": STEP_SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": context},
        ]

        for _ in range(self._max_iterations):
            response = self._llm.chat(messages, tools=[tool.to_openai_schema()])

            if not response.tool_calls:
                # LLM chose to respond with text (plan complete or no tool needed)
                return f"[ステップ {n}] {response.content or '完了'}"

            # Process tool calls
            assistant_msg = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                # Request user approval before executing
                if not self._approver(fn_name, fn_args, reason):
                    tool_output = "スキップ: ユーザーが実行を拒否しました"
                else:
                    called_tool = self._tools.get(fn_name)
                    if called_tool is None:
                        tool_output = f"エラー: ツール '{fn_name}' が見つかりません"
                    else:
                        result = called_tool.execute(**fn_args)
                        tool_output = result.output if result.success else f"エラー: {result.error}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_output,
                })

        return f"[ステップ {n}] 最大反復回数({self._max_iterations})に達しました"

    def _build_context(
        self,
        description: str,
        reason: str,
        previous_results: list[str],
    ) -> str:
        parts = [f"実行するステップ: {description}", f"理由: {reason}"]
        if previous_results:
            recent = previous_results[-3:]
            parts.append("前のステップの結果:\n" + "\n".join(recent))
        return "\n\n".join(parts)
