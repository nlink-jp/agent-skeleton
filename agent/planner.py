from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import LLMClient
    from .tools.base import Tool

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

    def create_plan(self, user_goal: str) -> dict:
        tool_list = "\n".join(
            f"- {t.name}: {t.description}" for t in self._tools
        )
        messages = [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Available tools:\n{tool_list}\n\nUser goal:\n{user_goal}",
            },
        ]
        response = self._llm.chat(messages)
        return self._parse_plan(response.content or "", user_goal)

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
            except json.JSONDecodeError:
                pass
        # Fallback: single-step plan so execution can still proceed
        return {
            "goal": user_goal,
            "steps": [
                {
                    "step": 1,
                    "description": user_goal,
                    "tool": None,
                    "reason": "Could not parse structured plan; executing goal directly.",
                }
            ],
        }
