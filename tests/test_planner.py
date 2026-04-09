"""Tests for Planner.format_plan output."""

from unittest.mock import MagicMock

import pytest

from agent.planner import Planner


def make_planner():
    llm = MagicMock()
    tools = []
    return Planner(llm=llm, tools=tools)


SAMPLE_PLAN = {
    "goal": "List files in /tmp",
    "steps": [
        {
            "step": 1,
            "description": "Run ls on /tmp",
            "tool": "shell_exec",
            "reason": "Need to see what files exist",
        },
        {
            "step": 2,
            "description": "Summarise results",
            "tool": None,
            "reason": "Present findings to user",
        },
    ],
}


def test_format_plan_contains_goal():
    planner = make_planner()
    output = planner.format_plan(SAMPLE_PLAN)
    assert "List files in /tmp" in output


def test_format_plan_shows_tool_name():
    planner = make_planner()
    output = planner.format_plan(SAMPLE_PLAN)
    assert "shell_exec" in output


def test_format_plan_shows_no_tool_step():
    planner = make_planner()
    output = planner.format_plan(SAMPLE_PLAN)
    assert "ツール不要" in output


def test_format_plan_shows_reason():
    planner = make_planner()
    output = planner.format_plan(SAMPLE_PLAN)
    assert "Need to see what files exist" in output
    assert "Present findings to user" in output


def test_format_plan_shows_step_numbers():
    planner = make_planner()
    output = planner.format_plan(SAMPLE_PLAN)
    assert "ステップ 1" in output
    assert "ステップ 2" in output


def test_parse_plan_fallback_on_invalid_json():
    llm = MagicMock()
    llm.chat.return_value = MagicMock(content="not json at all")
    planner = Planner(llm=llm, tools=[])

    plan = planner.create_plan("do something")
    assert plan["goal"] == "do something"
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["tool"] is None
    assert plan.get("fallback") is True


def test_parse_plan_valid_json():
    valid_response = '''{
        "goal": "Test goal",
        "steps": [{"step": 1, "description": "Do it", "tool": "file_read", "reason": "needed"}]
    }'''
    llm = MagicMock()
    llm.chat.return_value = MagicMock(content=valid_response)
    planner = Planner(llm=llm, tools=[])

    plan = planner.create_plan("Test goal")
    assert plan["goal"] == "Test goal"
    assert plan["steps"][0]["tool"] == "file_read"
    assert plan.get("fallback") is None  # no fallback flag on success
