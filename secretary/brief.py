"""Plain-text summaries: facts for Claude, and the fallback text if Claude can't write a message."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from . import config, fitness, reminders, tasks


def this_week_focus() -> list[str]:
    """Bullets under the '## This week' heading of goals/goals.md."""
    if not config.GOALS_FILE.exists():
        return []
    text = config.GOALS_FILE.read_text(encoding="utf-8")
    m = re.search(r"^##+\s*This week.*?$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    if not m:
        return []
    bullets = [re.sub(r"^\s*[-*]\s*(\[[ xX]\]\s*)?", "", line).strip()
               for line in m.group(1).splitlines() if re.match(r"^\s*[-*]\s+", line)]
    return [b for b in bullets if b and not b.startswith("_")]


def build_brief(now: datetime, settings: dict | None = None) -> str:
    settings = settings or config.load_settings()
    default_time = settings["default_time"]
    rems = reminders.load_reminders()
    all_tasks = tasks.load_tasks()
    today = now.date()

    lines = [f"☀️ **Good morning — {now:%A %d %B}**"]

    todays = [(occ, rem) for occ, rem in reminders.today(rems, now, default_time)
              if not str(rem.get("id", "")).startswith("__")]
    lines.append("\n📅 **Today**")
    if todays:
        lines += [f"• {occ:%H:%M} {rem.get('title')}" for occ, rem in todays]
    else:
        lines.append("• Nothing scheduled.")

    open_ = tasks.open_tasks(all_tasks)
    overdue = [t for t in open_ if t.get("due") and reminders.parse_date(t["due"]) < today]
    due_today = [t for t in open_ if t.get("due") and reminders.parse_date(t["due"]) == today]
    if overdue:
        lines.append("\n⚠️ **Overdue**")
        lines += [f"• {tasks.format_task(t, today)}" for t in overdue[:8]]
    focus = due_today + [t for t in open_ if t.get("priority") == "high" and t not in due_today
                         and t not in overdue]
    if focus:
        lines.append("\n✅ **Do today**")
        lines += [f"• {tasks.format_task(t, today)}" for t in focus[:6]]

    soon = [(occ, rem) for occ, rem in reminders.upcoming(rems, now + timedelta(days=1), 13, default_time)
            if occ.date() > today]
    if soon:
        lines.append("\n⏳ **Coming up (14 days)**")
        lines += [f"• {rem.get('title')} — {reminders.describe_when(occ, now)}" for occ, rem in soon[:8]]

    week = this_week_focus()
    if week:
        lines.append("\n🎯 **This week's focus**")
        lines += [f"• {b}" for b in week[:4]]

    last = fitness.last_session_day()
    if last:
        gap = (today - datetime.fromisoformat(last).date()).days
        if gap >= 3:
            lines.append(f"\n🏋️ Last logged workout was {gap} days ago ({last}). Let's get back in.")

    lines.append("\nReply with anything you want me to add, move or log.")
    return "\n".join(lines)


def evening_checkin(now: datetime) -> str:
    return (f"🌙 **Evening check-in — {now:%a %d %b}**\n"
            "1. What got done today? (I'll tick off tasks)\n"
            "2. Did you train / hit your protein? Send me the sets.\n"
            "3. Anything new to remember or schedule?\n"
            "4. Top priority for tomorrow?")


def weekly_review(now: datetime) -> str:
    rems = reminders.load_reminders()
    settings = config.load_settings()
    soon = reminders.upcoming(rems, now, 14, settings["default_time"])
    done = [t for t in tasks.load_tasks() if t.get("status") == "done" and t.get("completed")
            and (now.date() - reminders.parse_date(t["completed"])).days < 7]
    lines = [f"🗓️ **Weekly review — week {now:%V}**"]
    if done:
        lines.append(f"Wins this week ({len(done)} tasks done): " + "; ".join(t["title"] for t in done[:6]))
    lines.append(f"Body weight trend: {fitness.body_trend()}")
    if soon:
        lines.append("Next 2 weeks: " + "; ".join(f"{r.get('title')} ({o:%d %b})" for o, r in soon[:6]))
    lines += ["",
              "Let's do 10 minutes:",
              "1. Biggest win and biggest miss this week?",
              "2. Training: sessions done vs planned? Any PRs?",
              "3. Nutrition: how many days on target? Meal prep for next week planned?",
              "4. Thailand admin: anything pending (visa, 90-day, license, bills)?",
              "5. The 3 things that matter most next week?",
              "Answer here and I'll update your goals and plan."]
    return "\n".join(lines)
