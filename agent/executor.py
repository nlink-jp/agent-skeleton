from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from .log import get_logger

if TYPE_CHECKING:
    from .llm import LLMClient
    from .tools.base import Tool

log = get_logger(__name__)

# Signature: (tool_name: str, args: dict, reason: str) -> bool
ApproverFn = Callable[[str, dict, str], bool]


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
        log.debug(
            "Executor initialized: %d tool(s), max_iterations=%d",
            len(self._tools),
            max_iterations,
        )

    def execute_plan(self, plan: dict, history: list[dict]) -> list[str]:
        """Execute all steps in plan. Returns per-step result strings."""
        steps = plan.get("steps", [])
        log.info("Executing plan: %d step(s)", len(steps))
        results: list[str] = []
        for step in steps:
            log.info(
                "--- Step %d/%d: %s [tool=%s]",
                step["step"],
                len(steps),
                step["description"],
                step.get("tool"),
            )
            result = self._execute_step(step, history, results)
            log.info("Step %d result: %s", step["step"], result[:120])
            results.append(result)
        log.info("Plan execution complete: %d step(s) done", len(steps))
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
            log.debug("Step %d: no tool — asking LLM for text response", n)
            context = self._build_context(description, reason, previous_results)
            messages = history + [{"role": "user", "content": context}]
            response = self._llm.chat(messages)
            return f"[ステップ {n}] {response.content or '完了'}"

        tool = self._tools.get(tool_name)
        if tool is None:
            log.error("Step %d: unknown tool '%s'", n, tool_name)
            return f"[ステップ {n}] エラー: ツール '{tool_name}' が見つかりません"

        # Ask LLM to determine exact arguments via tool_call.
        # history[0] is already a system message; prepending another causes
        # consecutive system messages that break some local LLM jinja templates.
        context = self._build_context(description, reason, previous_results)
        messages = [
            *history,
            {"role": "user", "content": context},
        ]
        log.debug("Step %d: sending %d messages to LLM with tool '%s'", n, len(messages), tool_name)

        for iteration in range(self._max_iterations):
            log.debug("Step %d iteration %d/%d", n, iteration + 1, self._max_iterations)
            response = self._llm.chat(messages, tools=[tool.to_openai_schema()])

            if not response.tool_calls:
                # LLM chose to respond with text (step complete or no tool needed)
                log.debug("Step %d: LLM returned text (no tool_call)", n)
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
                    log.warning("Step %d: could not parse tool arguments: %s", n, tc.function.arguments)

                log.info(
                    "Step %d: tool_call '%s' args=%s | reason=%r",
                    n, fn_name, fn_args, reason,
                )

                # Request user approval before executing
                if not self._approver(fn_name, fn_args, reason):
                    log.info("Step %d: tool '%s' skipped by user", n, fn_name)
                    tool_output = "スキップ: ユーザーが実行を拒否しました"
                else:
                    called_tool = self._tools.get(fn_name)
                    if called_tool is None:
                        log.error("Step %d: tool '%s' not found at execution time", n, fn_name)
                        tool_output = f"エラー: ツール '{fn_name}' が見つかりません"
                    else:
                        log.debug("Step %d: executing tool '%s'", n, fn_name)
                        t0 = time.monotonic()
                        result = called_tool.execute(**fn_args)
                        elapsed = time.monotonic() - t0
                        if result.success:
                            preview = result.output[:200].replace("\n", "\\n")
                            log.info(
                                "Step %d: tool '%s' succeeded (%.2fs): %s",
                                n, fn_name, elapsed, preview,
                            )
                            tool_output = result.output
                        else:
                            log.warning(
                                "Step %d: tool '%s' failed (%.2fs): %s",
                                n, fn_name, elapsed, result.error,
                            )
                            tool_output = f"エラー: {result.error}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_output,
                })

        log.warning("Step %d: reached max_iterations (%d)", n, self._max_iterations)
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
