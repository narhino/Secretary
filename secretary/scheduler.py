"""One 'tick': find everything due right now and turn it into messages."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import brief, config, reminders


def builtin_reminders(settings: dict) -> list[dict]:
    """Morning brief, evening check-in and weekly review, as reminder entries."""
    out = []
    mb = settings.get("morning_brief") or {}
    if mb.get("enabled"):
        out.append({"id": "__brief__", "title": "Morning brief", "repeat": "daily", "time": mb.get("time", "07:30")})
    ev = settings.get("evening_checkin") or {}
    if ev.get("enabled"):
        out.append({"id": "__evening__", "title": "Evening check-in", "repeat": "daily", "time": ev.get("time", "21:30")})
    wr = settings.get("weekly_review") or {}
    if wr.get("enabled"):
        out.append({"id": "__weekly__", "title": "Weekly review", "repeat": f"weekly:{wr.get('day', 'sun')}",
                    "time": wr.get("time", "19:00")})
    return out


def render(n: reminders.Notification, now: datetime, settings: dict) -> str:
    rid = n.reminder["id"]
    if rid == "__brief__":
        return brief.build_brief(now, settings)
    if rid == "__evening__":
        return brief.evening_checkin(now)
    if rid == "__weekly__":
        return brief.weekly_review(now)
    return reminders.format_notification(n, now)


def collect_due(now: datetime | None = None, sent: dict | None = None,
                settings: dict | None = None) -> list[tuple[reminders.Notification, str]]:
    settings = settings or config.load_settings()
    now = now or config.now(settings)
    sent = reminders.load_sent() if sent is None else sent
    since = now - timedelta(hours=float(settings.get("lookback_hours", 6)))
    rems = reminders.load_reminders() + builtin_reminders(settings)
    due = reminders.due_notifications(rems, now, since, sent, settings["default_time"])
    # A brief that is hours late is noise; only send it within 2h of its time.
    due = [n for n in due if not n.reminder["id"].startswith("__") or now - n.fire_at <= timedelta(hours=2)]
    return [(n, render(n, now, settings)) for n in due]


def mark_sent(sent: dict, notifications, now: datetime) -> None:
    for n in notifications:
        for key in n.covers or [n.key]:
            sent[key] = now.isoformat()
