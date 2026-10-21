"""One 'tick': find everything due right now.

Claude normally writes every message itself (check-ins and reminders). This module finds what is
due; `backup` mode lets the GitHub Actions safety net send only critical reminders that nobody
delivered after a grace period.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from . import brief, config, reminders

BUILTIN_KINDS = ("morning", "midday", "evening", "weekly")


def builtin_reminders(settings: dict) -> list[dict]:
    """Check-in times from settings, as reminder entries with ids like __morning__."""
    out = []
    checkins = settings.get("checkins") or {}
    for kind in BUILTIN_KINDS:
        value = checkins.get(kind)
        if not value:
            continue
        if kind == "weekly":
            out.append({"id": "__weekly__", "title": "Weekly review", "repeat": f"weekly:{value.get('day', 'sun')}",
                        "time": value.get("time", "19:00")})
        else:
            out.append({"id": f"__{kind}__", "title": f"{kind.capitalize()} check-in", "repeat": "daily",
                        "time": value})
    return out


def is_critical(rem: dict, settings: dict) -> bool:
    cats = (settings.get("delivery") or {}).get("critical_categories") or []
    return bool(rem.get("critical")) or rem.get("category") in cats


def render(n: reminders.Notification, now: datetime, settings: dict) -> str:
    """Plain-text fallback, used only when Claude is not the one writing."""
    rid = n.reminder["id"]
    if rid == "__morning__":
        return brief.build_brief(now, settings)
    if rid == "__evening__":
        return brief.evening_checkin(now)
    if rid == "__weekly__":
        return brief.weekly_review(now)
    if rid == "__midday__":
        return "🍽️ What did you have for lunch? A photo or a quick list is enough and I'll log it."
    return humanize(n, now)


_OPENERS = {
    "far": ["Just so it's on your radar:", "Looking ahead a bit:", "Small heads-up:"],
    "tomorrow": ["Quick heads-up for tomorrow:", "Don't forget tomorrow:", "For tomorrow:"],
    "soon": ["Coming up soon:", "In a little while:", "Heads-up:"],
    "now": ["It's time:", "Now's the moment:", "Right now:"],
}


def humanize(n: reminders.Notification, now: datetime) -> str:
    rem = n.reminder
    days = (n.occurrence.date() - now.date()).days
    bucket = "now" if n.lead == timedelta(0) else "tomorrow" if days == 1 else "soon" if days == 0 else "far"
    options = _OPENERS[bucket]
    opener = options[int(hashlib.sha1(n.key.encode()).hexdigest(), 16) % len(options)]
    line = f"{opener} **{rem.get('title', rem['id'])}**"
    if bucket != "now":
        line += f" — {reminders.describe_when(n.occurrence, now)}"
    parts = [line]
    if rem.get("notes"):
        parts.append(str(rem["notes"]).strip())
    return "\n".join(parts)


def collect_due(now: datetime | None = None, sent: dict | None = None, settings: dict | None = None,
                backup: bool = False) -> list[tuple[reminders.Notification, str]]:
    settings = settings or config.load_settings()
    now = now or config.now(settings)
    sent = reminders.load_sent() if sent is None else sent
    since = now - timedelta(hours=float(settings.get("lookback_hours", 6)))
    if backup:
        grace = timedelta(minutes=float((settings.get("delivery") or {}).get("backup_grace_minutes", 45)))
        rems = [r for r in reminders.load_reminders() if is_critical(r, settings)]
        due = reminders.due_notifications(rems, now - grace, since, sent, settings["default_time"])
        return [(n, humanize(n, now)) for n in due]
    rems = reminders.load_reminders() + builtin_reminders(settings)
    due = reminders.due_notifications(rems, now, since, sent, settings["default_time"])
    # A check-in that is hours late is noise; only keep it within 2h of its time.
    due = [n for n in due if not n.reminder["id"].startswith("__") or now - n.fire_at <= timedelta(hours=2)]
    return [(n, render(n, now, settings)) for n in due]


def mark_sent(sent: dict, notifications, now: datetime) -> None:
    for n in notifications:
        for key in n.covers or [n.key]:
            sent[key] = now.isoformat()
