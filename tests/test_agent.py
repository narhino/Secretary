import asyncio

import pytest

anthropic = pytest.importorskip("anthropic")
from anthropic.types.beta import BetaMessage  # noqa: E402

from secretary import tasks  # noqa: E402
from secretary.bot import agent  # noqa: E402


def _message(content, stop_reason):
    return BetaMessage.model_validate({
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    })


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def create(self, **kwargs):
        # Snapshot: the agent keeps appending to the same list after the call.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


class FakeClient:
    def __init__(self, replies):
        self.beta = type("Beta", (), {})()
        self.beta.messages = FakeMessages(replies)


def test_agent_runs_tools_and_keeps_text_history(home, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    sec = agent.Secretary()
    fake = FakeClient([
        _message([{"type": "tool_use", "id": "toolu_1", "name": "add_task",
                   "input": {"title": "Book DLT Smart Queue slot", "priority": "high", "area": "thailand"}}],
                 "tool_use"),
        _message([{"type": "text", "text": "Added it as a high-priority task."}], "end_turn"),
    ])
    sec.client = fake

    reply = asyncio.run(sec.respond("chan", "remind me to book the DLT appointment"))

    assert reply.text == "Added it as a high-priority task."
    assert reply.wrote and reply.tool_calls == ["add_task"]
    assert tasks.load_tasks()[0]["title"] == "Book DLT Smart Queue slot"

    first, second = fake.beta.messages.calls
    assert first["model"] == agent.MODEL
    assert first["fallbacks"] == "default"
    assert any(t.get("type") == "web_search_20260209" for t in first["tools"])
    assert "<context>" in first["messages"][-1]["content"][-1]["text"]
    # Within a turn the transcript is append-only: assistant tool call, then the results.
    assert second["messages"][-1]["content"][0]["type"] == "tool_result"
    assert second["messages"][-1]["content"][0]["tool_use_id"] == "toolu_1"

    history = sec.histories["chan"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert all(isinstance(m["content"], str) for m in history)


def test_tool_errors_are_returned_to_claude(home, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    sec = agent.Secretary()
    fake = FakeClient([
        _message([{"type": "tool_use", "id": "toolu_1", "name": "read_file", "input": {"path": ".env"}}], "tool_use"),
        _message([{"type": "text", "text": "I can't read that file."}], "end_turn"),
    ])
    sec.client = fake
    reply = asyncio.run(sec.respond("chan", "show me .env"))
    result = fake.beta.messages.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and not reply.wrote


def test_bot_module_imports():
    pytest.importorskip("discord")
    from secretary.bot import discord_bot
    assert "!brief" in discord_bot.HELP
