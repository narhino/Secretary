"""Discord front-end: chat with the secretary and receive reminders by DM.

Run with:  python -m secretary.bot
Needs DISCORD_BOT_TOKEN, DISCORD_OWNER_ID and ANTHROPIC_API_KEY (see .env.example).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

import anthropic
import discord
from discord.ext import tasks as dtasks

from .. import brief, config, fitness, gitsync, reminders, scheduler, tasks
from ..notify import chunks

log = logging.getLogger("secretary.bot")

MAX_ATTACHMENT = 8 * 1024 * 1024
ATTACHMENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "application/pdf"}
PULL_EVERY = 300  # seconds

HELP = """**Talk to me normally** — e.g. "remind me to do my 90-day report on 12 Dec",
"bench 80x8, 80x8, 77.5x7", "what's my week look like?", or send a photo of a receipt.

Quick commands (instant, no AI):
`!brief` today's brief · `!upcoming` next 30 days · `!tasks` open tasks
`!prs` personal records · `!reset` clear chat context · `!help`"""


class SecretaryBot(discord.Client):
    def __init__(self, owner_id: int, chat_channel_id: int | None, notify_channel_id: int | None,
                 send_reminders: bool) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.owner_id = owner_id
        self.chat_channel_id = chat_channel_id
        self.notify_channel_id = notify_channel_id
        self.send_reminders = send_reminders
        self.lock = asyncio.Lock()
        self.last_pull = 0.0
        from .agent import Secretary
        self.secretary = Secretary()

    async def setup_hook(self) -> None:
        if self.send_reminders:
            self.reminder_loop.start()

    async def on_ready(self) -> None:
        log.info("logged in as %s (reminders %s)", self.user, "on" if self.send_reminders else "off")

    # ------------------------------------------------------------ chat

    def _addressed(self, message: discord.Message) -> bool:
        if isinstance(message.channel, discord.DMChannel):
            return True
        if self.chat_channel_id and message.channel.id == self.chat_channel_id:
            return True
        return self.user is not None and self.user in message.mentions

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.author.id != self.owner_id or not self._addressed(message):
            return
        text = message.content
        if self.user is not None:
            text = text.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "")
        text = text.strip()
        if text.startswith("!"):
            await self._command(message, text[1:].split()[0].lower() if len(text) > 1 else "help")
            return

        attachments = []
        for att in message.attachments:
            ctype = (att.content_type or "").split(";")[0]
            if ctype in ATTACHMENT_TYPES and att.size <= MAX_ATTACHMENT:
                attachments.append((ctype, await att.read()))
        if not text and not attachments:
            return

        async with message.channel.typing():
            async with self.lock:
                await self._pull(force=True)
                try:
                    reply = await self.secretary.respond(str(message.channel.id), text, attachments)
                except anthropic.APIStatusError as exc:
                    log.exception("Claude API error")
                    await message.reply(f"⚠️ Claude API error ({exc.status_code}). Try again in a minute.")
                    return
                except anthropic.APIConnectionError:
                    await message.reply("⚠️ Couldn't reach Claude. Try again in a minute.")
                    return
                if reply.wrote:
                    await asyncio.to_thread(gitsync.commit_and_push, "secretary: update from Discord")
        await self._send(message.channel, reply.text, reference=message)

    async def _command(self, message: discord.Message, cmd: str) -> None:
        settings = config.load_settings()
        now = config.now(settings)
        if cmd == "brief":
            text = brief.build_brief(now, settings)
        elif cmd == "upcoming":
            items = reminders.upcoming(reminders.load_reminders(), now, 30, settings["default_time"])
            text = "\n".join(f"• {o:%a %d %b %H:%M} — {r.get('title')}" for o, r in items) or "Nothing in 30 days."
        elif cmd == "tasks":
            text = "\n".join(f"• {tasks.format_task(t, now.date())}" for t in tasks.open_tasks()) or "No open tasks 🎉"
        elif cmd == "prs":
            text = "\n".join(f"• {p['exercise']}: {p['set']} (e1RM {p['e1rm']} kg)"
                             for p in fitness.personal_records()) or "No workouts logged yet."
        elif cmd == "reset":
            self.secretary.reset(str(message.channel.id))
            text = "Conversation context cleared (memory files are untouched)."
        else:
            text = HELP
        await self._send(message.channel, text)

    async def _send(self, channel, text: str, reference: discord.Message | None = None) -> None:
        for i, piece in enumerate(chunks(text)):
            await channel.send(piece, reference=reference if i == 0 else None,
                               allowed_mentions=discord.AllowedMentions(users=True, everyone=False, roles=False))

    async def _pull(self, force: bool = False) -> None:
        if force or time.monotonic() - self.last_pull > PULL_EVERY:
            await asyncio.to_thread(gitsync.pull)
            self.last_pull = time.monotonic()

    # ------------------------------------------------------- reminders

    @dtasks.loop(seconds=60)
    async def reminder_loop(self) -> None:
        # Never let one bad tick (network, malformed YAML) stop future reminders.
        try:
            async with self.lock:
                await self._send_due()
        except Exception:  # noqa: BLE001
            log.exception("reminder tick failed")

    async def _send_due(self) -> None:
        await self._pull()
        settings = config.load_settings()
        now = config.now(settings)
        sent = reminders.load_sent()
        due = await asyncio.to_thread(scheduler.collect_due, now, sent, settings)
        if not due:
            return
        target = await self._notify_target()
        checkins = [n for n, _ in due if n.reminder["id"].startswith("__")]
        items = [{"title": n.reminder.get("title"), "when": reminders.describe_when(n.occurrence, now),
                  "notes": n.reminder.get("notes")} for n, _ in due if not n.reminder["id"].startswith("__")]
        kind = checkins[-1].reminder["id"].strip("_") if checkins else "reminders"
        try:
            # Claude writes the message itself, so check-ins and reminders read like a person.
            reply = await self.secretary.compose(str(target.id), kind, items)
            text = reply.text.strip()
            if reply.wrote:
                await asyncio.to_thread(gitsync.commit_and_push, "secretary: update from check-in")
        except Exception:  # noqa: BLE001 - never lose a reminder because Claude was unreachable
            log.exception("compose failed; sending plain reminders")
            text = "\n\n".join(t for n, t in due if not n.reminder["id"].startswith("__") or n is checkins[-1])
        if text and text != "SKIP":
            if self.notify_channel_id:
                text = f"<@{self.owner_id}> {text}"
            await self._send(target, text)
        scheduler.mark_sent(sent, [n for n, _ in due], now)
        reminders.save_sent(sent, now)
        await asyncio.to_thread(gitsync.commit_and_push, "secretary: reminder log")

    @reminder_loop.before_loop
    async def _wait_ready(self) -> None:
        await self.wait_until_ready()

    async def _notify_target(self):
        if self.notify_channel_id:
            return self.get_channel(self.notify_channel_id) or await self.fetch_channel(self.notify_channel_id)
        user = self.get_user(self.owner_id) or await self.fetch_user(self.owner_id)
        return user.dm_channel or await user.create_dm()


def _int_env(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    return int(value) if value else None


def main() -> None:
    config.load_env_file()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("DISCORD_BOT_TOKEN")
    owner = config.owner_id()
    if not token or not owner:
        raise SystemExit("Set DISCORD_BOT_TOKEN and DISCORD_OWNER_ID (see .env.example)")
    bot = SecretaryBot(
        owner_id=int(owner),
        chat_channel_id=_int_env("DISCORD_CHAT_CHANNEL_ID"),
        notify_channel_id=_int_env("DISCORD_NOTIFY_CHANNEL_ID"),
        send_reminders=os.environ.get("SECRETARY_BOT_REMINDERS", "1") != "0",
    )
    bot.run(token, log_handler=None)
