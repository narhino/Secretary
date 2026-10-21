"""The conversational secretary: Claude + tools over the repo's memory files."""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field

import anthropic

from .. import config, fitness, reminders, tasks
from . import tools

log = logging.getLogger(__name__)

MODEL = os.environ.get("SECRETARY_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("SECRETARY_EFFORT", "medium")
MAX_STEPS = 16
HISTORY_TURNS = 12  # user+assistant pairs kept per channel
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5,
              "user_location": {"type": "approximate", "country": "TH", "timezone": "Asia/Bangkok"}}

BOT_ADDENDUM = """
# You are talking through Discord right now
- You run as the user's Discord bot. Replies are Discord messages: keep them short and scannable
  (a few lines, bullets, bold for key items). No tables. Under ~1500 characters unless asked for detail.
- You have tools instead of a shell: read_file / write_file / edit_file / append_file for memory files,
  add_reminder / complete_reminder / list_reminders, add_task / update_task / list_tasks,
  log_workout / exercise_progress / log_body, and web_search for current information.
- Files you change are committed and pushed to GitHub automatically after your reply.
- The <context> block in each message is a fresh snapshot (date, today's schedule, open tasks).
  Trust it over anything older in the conversation.
- Images or PDFs the user sends (receipts, visa stamps, meal photos, gym boards) are attached to their
  message. Extract what matters (dates, amounts, macros) and file it.
""".strip()


def _read(rel: str) -> str:
    path = config.ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else f"({rel} not created yet)"


def system_prompt() -> list[dict]:
    """Stable instructions first (cached), then the slower-changing memory files."""
    manual = _read("CLAUDE.md") + "\n\n" + BOT_ADDENDUM
    memory = "\n\n".join(f'<file path="{p}">\n{_read(p)}\n</file>'
                         for p in ("profile/me.md", "goals/goals.md"))
    return [{"type": "text", "text": manual, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "# Core memory (loaded at the start of every message)\n\n" + memory}]


def snapshot() -> str:
    settings = config.load_settings()
    now = config.now(settings)
    rems = reminders.load_reminders()
    lines = [f"Now: {now:%A %d %B %Y, %H:%M} ({settings['timezone']})"]
    todays = reminders.today(rems, now, settings["default_time"])
    lines.append("Today: " + ("; ".join(f"{o:%H:%M} {r.get('title')} [{r['id']}]" for o, r in todays)
                              if todays else "nothing scheduled"))
    soon = reminders.upcoming(rems, now, 30, settings["default_time"])
    if soon:
        lines.append("Next 30 days: " + "; ".join(f"{o:%d %b} {r.get('title')} [{r['id']}]" for o, r in soon[:12]))
    open_ = tasks.open_tasks()
    if open_:
        lines.append("Open tasks: " + "; ".join(tasks.format_task(t, now.date()) for t in open_[:15]))
    last = fitness.last_session_day()
    lines.append(f"Last logged workout: {last or 'none yet'}")
    return "\n".join(lines)


@dataclass
class Reply:
    text: str
    wrote: bool = False
    tool_calls: list[str] = field(default_factory=list)


class Secretary:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic()
        self.histories: dict[str, list[dict]] = defaultdict(list)

    def reset(self, key: str) -> None:
        self.histories.pop(key, None)

    async def respond(self, key: str, text: str, attachments: list[tuple[str, bytes]] | None = None) -> Reply:
        now = config.now()
        content = []
        for media_type, data in attachments or []:
            encoded = base64.standard_b64encode(data).decode()
            kind = "document" if media_type == "application/pdf" else "image"
            content.append({"type": kind, "source": {"type": "base64", "media_type": media_type, "data": encoded}})
        context = await asyncio.to_thread(snapshot)
        content.append({"type": "text", "text": f"<context>\n{context}\n</context>\n\n{text or '(see attachment)'}"})

        system = await asyncio.to_thread(system_prompt)
        messages = list(self.histories[key]) + [{"role": "user", "content": content}]
        reply = Reply("")
        response = None
        for _ in range(MAX_STEPS):
            response = await self.client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=system,
                tools=[*tools.TOOLS, WEB_SEARCH],
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":
                continue
            uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not uses:
                break
            results = []
            for use in uses:
                reply.tool_calls.append(use.name)
                try:
                    out, wrote = await asyncio.to_thread(tools.run, use.name, use.input)
                    reply.wrote |= wrote
                    results.append({"type": "tool_result", "tool_use_id": use.id, "content": out})
                except Exception as exc:  # noqa: BLE001 - every failure goes back to Claude
                    log.info("tool %s failed: %s", use.name, exc)
                    results.append({"type": "tool_result", "tool_use_id": use.id,
                                    "content": f"Error: {exc}", "is_error": True})
            messages.append({"role": "user", "content": results})

        if response is not None and response.stop_reason == "refusal":
            reply.text = "I can't help with that one."
        else:
            reply.text = "\n".join(b.text for b in response.content if b.type == "text").strip() \
                if response is not None else ""
            if not reply.text:
                reply.text = "Done ✅" if reply.wrote else "(no reply)"

        # Keep a text-only history: earlier thinking blocks are never replayed, so trimming is safe.
        note = f" [sent {len(attachments)} attachment(s)]" if attachments else ""
        history = self.histories[key]
        history += [{"role": "user", "content": f"[{now:%a %d %b %H:%M}] {text}{note}"},
                    {"role": "assistant", "content": reply.text}]
        del history[:-2 * HISTORY_TURNS]
        return reply
