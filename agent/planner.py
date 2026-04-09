from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .log import get_logger

if TYPE_CHECKING:
    from .llm import LLMClient
    from .tools.base import Tool

log = get_logger(__name__)

PLAN_SYSTEM_PROMPT = """\
You are a planning agent. Given a user goal and a list of available tools, \
produce a step-by-step execution plan.

Respond with ONLY a JSON object in exactly this format — no markdown fences, no extra text:
{
  "goal": "<concise restatement of the goal>",
  "steps": [
    {
      "step": 1,
      "description": "<what this step does>",
      "tool": "<tool_name or null if no tool is needed>",
      "reason": "<why this step is necessary>"
    }
  ]
}

Rules:
- Use only tools from the provided list.
- Set "tool" to null for steps that require no tool call (e.g. reasoning, summarising).
- Keep each description short and imperative.
"""


class Planner:
    def __init__(self, llm: LLMClient, tools: list[Tool]) -> None:
        self._llm = llm
        self._tools = tools
        log.debug("Planner initialized with %d tool(s): %s", len(tools), [t.name for t in tools])

    def create_plan(self, user_goal: str, history: list[dict] | None = None) -> dict:
        log.info("Planning for goal: %r", user_goal)
        tool_list = "\n".join(
            f"- {t.name}: {t.description}" for t in self._tools
        )
        messages: list[dict] = [{"role": "system", "content": PLAN_SYSTEM_PROMPT}]
        # Include prior user/assistant turns so the planner understands what
        # has already been done or discussed (skip system messages — the
        # planner has its own system prompt).
        if history:
            prior = [m for m in history if m["role"] in ("user", "assistant")]
            if prior:
                log.debug("Planner: including %d prior turn(s) from memory", len(prior))
                messages.extend(prior)
        messages.append({
            "role": "user",
            "content": f"Available tools:\n{tool_list}\n\nUser goal:\n{user_goal}",
        })
        response = self._llm.chat(messages)
        raw = response.content or ""
        log.debug("Raw plan response (%d chars): %s", len(raw), raw[:300])

        plan = self._parse_plan(raw, user_goal)
        steps = plan.get("steps", [])
        log.info(
            "Plan parsed: %d step(s) | tools used: %s",
            len(steps),
            [s.get("tool") for s in steps],
        )
        return plan

    def format_plan(self, plan: dict) -> str:
        lines = [f"目標: {plan.get('goal', '（不明）')}", ""]
        for step in plan.get("steps", []):
            tool = step.get("tool")
            tool_tag = f"[ツール: {tool}]" if tool else "[ツール不要]"
            lines.append(f"  ステップ {step['step']}: {step['description']}")
            lines.append(f"    {tool_tag}  理由: {step.get('reason', '')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_plan(self, raw: str, user_goal: str) -> dict:
        # Extract JSON from response (LLMs sometimes wrap in markdown)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError as e:
                log.warning("JSON parse failed (%s); using fallback plan", e)
        else:
            log.warning("No JSON object found in plan response; using fallback plan")

        # Fallback: single-step plan so execution can still proceed
        return {
            "goal": user_goal,
            "fallback": True,
            "steps": [
                {
                    "step": 1,
                    "description": user_goal,
                    "tool": None,
                    "reason": "Could not parse structured plan; executing goal directly.",
                }
            ],
        }
