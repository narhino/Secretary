"""Reminder engine.

Reads data/reminders.yaml and works out which notifications are due. Each
reminder has an occurrence time (one-off `due`, or a `repeat` rule) and a list
of lead times in `notify_before` (e.g. [7d, 1d, 0m]); every lead time is one
notification. Sent notifications are recorded in data/state/sent.json so that
the Discord bot and the GitHub Actions runner never send the same one twice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config, store

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DURATION = re.compile(r"^\s*(\d+)\s*([mhdw]?)\s*$")
SENT_RETENTION = timedelta(days=60)
ROUTINE_KINDS = {"daily", "weekly"}


# ---------------------------------------------------------------- parsing

def parse_duration(value) -> timedelta:
    """'30m', '2h', '7d', '1w' (or a bare number of minutes) -> timedelta."""
    if value in (None, ""):
        return timedelta(0)
    if isinstance(value, (int, float)):
        return timedelta(minutes=value)
    m = _DURATION.match(str(value).lower())
    if not m:
        raise ValueError(f"bad duration {value!r}: use e.g. 30m, 2h, 7d, 1w")
    n, unit = int(m.group(1)), m.group(2) or "m"
    return {"m": timedelta(minutes=n), "h": timedelta(hours=n),
            "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]


def format_duration(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    for unit, size in (("w", 7 * 24 * 60), ("d", 24 * 60), ("h", 60)):
        if minutes and minutes % size == 0:
            return f"{minutes // size}{unit}"
    return f"{minutes}m"


def parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


def parse_time(value, default: str = "09:00") -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, int):  # YAML 1.1 reads 09:00 unquoted as minutes
        return time(value // 60 % 24, value % 60)
    text = str(value or default).strip()
    hours, minutes = text.split(":")[:2]
    return time(int(hours), int(minutes))


def reminder_time(rem: dict, default: str) -> time:
    """Time of day: explicit `time`, else a time inside `due`, else the default."""
    if rem.get("time") not in (None, ""):
        return parse_time(rem["time"])
    due = rem.get("due")
    if isinstance(due, datetime):
        return due.time().replace(second=0, microsecond=0)
    if isinstance(due, str) and len(due.strip()) > 10:
        return parse_time(due.strip()[11:16])
    return parse_time(default)


def parse_repeat(rem: dict) -> tuple[str | None, object]:
    """Normalise `repeat` into (kind, parameter)."""
    rep = rem.get("repeat")
    anchor = parse_date(rem.get("due"))
    if rep in (None, "", False, "none"):
        return None, None
    if isinstance(rep, str):
        rep = rep.strip().lower()
        if rep == "daily":
            return "daily", None
        if rep == "weekdays":
            return "weekly", [0, 1, 2, 3, 4]
        if rep == "weekly":
            if not anchor:
                raise ValueError(f"{rem.get('id')}: 'weekly' needs a due date or a list of days")
            return "weekly", [anchor.weekday()]
        if rep.startswith("weekly:"):
            return "weekly", _weekdays(rep.split(":", 1)[1].split(","))
        if rep == "monthly":
            if not anchor:
                raise ValueError(f"{rem.get('id')}: 'monthly' needs a due date")
            return "monthly", anchor.day
        if rep == "yearly":
            if not anchor:
                raise ValueError(f"{rem.get('id')}: 'yearly' needs a due date")
            return "yearly", (anchor.month, anchor.day)
        m = re.match(r"^every\s*(\d+)\s*d(ays?)?$", rep)
        if m:
            return _every(rem, int(m.group(1)))
        raise ValueError(f"{rem.get('id')}: unknown repeat {rep!r}")
    if isinstance(rep, dict) and len(rep) == 1:
        kind, param = next(iter(rep.items()))
        if kind == "weekly":
            days = param if isinstance(param, list) else str(param).split(",")
            return "weekly", _weekdays(days)
        if kind == "monthly":
            return "monthly", int(param)
        if kind == "every_days":
            return _every(rem, int(param))
    raise ValueError(f"{rem.get('id')}: unknown repeat {rep!r}")


def _every(rem: dict, days: int):
    if days < 1 or not parse_date(rem.get("due")):
        raise ValueError(f"{rem.get('id')}: every_days needs a due date and a positive interval")
    return "every_days", days


def _weekdays(names) -> list[int]:
    out = []
    for name in names:
        key = str(name).strip().lower()[:3]
        if key not in WEEKDAYS:
            raise ValueError(f"unknown weekday {name!r}")
        out.append(WEEKDAYS.index(key))
    return sorted(set(out))


# ------------------------------------------------------------ occurrences

def _last_day(year: int, month: int) -> int:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def _days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def occurrences(rem: dict, start: datetime, end: datetime, zone: ZoneInfo,
                default_time: str = "09:00") -> list[datetime]:
    """All occurrence datetimes of `rem` with start <= t <= end."""
    if rem.get("done"):
        return []
    at = reminder_time(rem, default_time)
    anchor = parse_date(rem.get("due"))
    until = parse_date(rem.get("until"))
    kind, param = parse_repeat(rem)

    if kind is None:
        if not anchor:
            return []
        t = datetime.combine(anchor, at, zone)
        return [t] if start <= t <= end else []

    first = max(start.date(), anchor) if anchor else start.date()
    last = min(end.date(), until) if until else end.date()
    if kind == "every_days":
        gap = (first - anchor).days
        k = -(-gap // param) if gap > 0 else 0
        days = []
        d = anchor + timedelta(days=k * param)
        while d <= last:
            days.append(d)
            d += timedelta(days=param)
    else:
        days = [d for d in _days(first, last) if _matches(kind, param, d)]
    out = []
    for d in days:
        t = datetime.combine(d, at, zone)
        if start <= t <= end:
            out.append(t)
    return out


def _matches(kind: str, param, d: date) -> bool:
    if kind == "daily":
        return True
    if kind == "weekly":
        return d.weekday() in param
    if kind == "monthly":
        return d.day == min(param, _last_day(d.year, d.month))
    if kind == "yearly":
        month, day = param
        return d.month == month and d.day == min(day, _last_day(d.year, month))
    return False


def next_occurrence(rem: dict, after: datetime, zone: ZoneInfo, default_time: str = "09:00",
                    horizon_days: int = 800) -> datetime | None:
    found = occurrences(rem, after, after + timedelta(days=horizon_days), zone, default_time)
    return found[0] if found else None


# ---------------------------------------------------------- notifications

@dataclass
class Notification:
    key: str
    reminder: dict
    occurrence: datetime
    lead: timedelta
    fire_at: datetime
    covers: list[str] = field(default_factory=list)


def notification_key(rem: dict, occ: datetime, lead: timedelta) -> str:
    return f"{rem['id']}@{occ.strftime('%Y-%m-%dT%H:%M')}#{format_duration(lead)}"


def leads_of(rem: dict) -> list[timedelta]:
    raw = rem.get("notify_before")
    if raw in (None, "", []):
        raw = ["0m"]
    if not isinstance(raw, list):
        raw = str(raw).split(",")
    return sorted({parse_duration(x) for x in raw})


def due_notifications(reminders: list[dict], now: datetime, since: datetime, sent: dict,
                      default_time: str = "09:00") -> list[Notification]:
    """Notifications whose fire time is in (since, now] and that were not sent.

    If several lead times of the same occurrence were missed (e.g. the runner
    was offline), only the latest one is returned; it `covers` the older ones
    so they are marked as sent too.
    """
    zone = now.tzinfo
    out = []
    for rem in reminders:
        if rem.get("done") or not rem.get("id"):
            continue
        leads = leads_of(rem)
        for occ in occurrences(rem, since, now + max(leads), zone, default_time):
            pending = []
            for lead in leads:
                fire = occ - lead
                key = notification_key(rem, occ, lead)
                if since < fire <= now and key not in sent:
                    pending.append((fire, lead, key))
            if pending:
                pending.sort()
                fire, lead, key = pending[-1]
                out.append(Notification(key, rem, occ, lead, fire, [k for _, _, k in pending]))
    out.sort(key=lambda n: n.fire_at)
    return out


def describe_when(occ: datetime, now: datetime) -> str:
    days = (occ.date() - now.date()).days
    clock = occ.strftime("%H:%M")
    if days == 0:
        return f"today at {clock}" if occ >= now - timedelta(minutes=1) else f"was due today at {clock}"
    if days == 1:
        return f"tomorrow at {clock}"
    if days == -1:
        return f"was due yesterday at {clock}"
    if days < 0:
        return f"overdue by {-days} days (was {occ:%a %d %b})"
    if days < 14:
        return f"in {days} days ({occ:%a %d %b}, {clock})"
    return f"in {days} days ({occ:%a %d %b %Y})"


def format_notification(n: Notification, now: datetime) -> str:
    rem = n.reminder
    emoji = rem.get("emoji") or ("⏰" if n.lead == timedelta(0) else "📌")
    lines = [f"{emoji} **{rem.get('title', rem['id'])}** — {describe_when(n.occurrence, now)}"]
    if rem.get("notes"):
        lines.append(str(rem["notes"]).strip())
    if rem.get("link"):
        lines.append(f"📎 {rem['link']}")
    return "\n".join(lines)


# ------------------------------------------------------------ persistence

def load_reminders() -> list[dict]:
    data = store.load_yaml(config.REMINDERS_FILE, {}) or {}
    return list(data.get("reminders") or [])


def save_reminders(reminders: list[dict]) -> None:
    header = store.yaml_header(config.REMINDERS_FILE)
    store.save_yaml(config.REMINDERS_FILE, {"reminders": reminders}, header)


def load_sent() -> dict:
    return store.load_json(config.SENT_FILE, {}) or {}


def save_sent(sent: dict, now: datetime) -> None:
    cutoff = now - SENT_RETENTION
    kept = {k: v for k, v in sent.items() if datetime.fromisoformat(v) >= cutoff}
    store.save_json(config.SENT_FILE, kept)


def validate(reminders: list[dict], zone: ZoneInfo) -> list[str]:
    errors, seen = [], set()
    probe = datetime(2026, 1, 1, tzinfo=zone)
    for i, rem in enumerate(reminders):
        rid = rem.get("id")
        if not rid:
            errors.append(f"reminder #{i + 1} has no id")
            continue
        if rid in seen:
            errors.append(f"duplicate reminder id {rid}")
        seen.add(rid)
        if not rem.get("title"):
            errors.append(f"{rid}: missing title")
        try:
            leads_of(rem)
            reminder_time(rem, "09:00")
            parse_date(rem.get("due"))
            kind, _ = parse_repeat(rem)
            if kind is None and not rem.get("due"):
                errors.append(f"{rid}: one-off reminder needs a due date")
            occurrences(rem, probe, probe + timedelta(days=3), zone)
        except (ValueError, TypeError) as exc:
            errors.append(f"{rid}: {exc}")
    return errors


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "reminder"


def add_reminder(title: str, due=None, time_: str | None = None, repeat=None,
                 notify_before=None, category: str | None = None, notes: str | None = None,
                 link: str | None = None, rid: str | None = None) -> dict:
    reminders = load_reminders()
    ids = {r.get("id") for r in reminders}
    rid = rid or slugify(title)
    base, n = rid, 2
    while rid in ids:
        rid, n = f"{base}-{n}", n + 1
    rem = {"id": rid, "title": title}
    if due:
        rem["due"] = store.iso(parse_date(due))
    if time_:
        rem["time"] = parse_time(time_).strftime("%H:%M")
    if repeat:
        rem["repeat"] = repeat
    if notify_before:
        rem["notify_before"] = [format_duration(parse_duration(x)) for x in notify_before]
    for key, value in (("category", category), ("notes", notes), ("link", link)):
        if value:
            rem[key] = value
    errors = validate([rem], config.tz())
    if errors:
        raise ValueError("; ".join(errors))
    reminders.append(rem)
    save_reminders(reminders)
    return rem


def find(reminders: list[dict], rid: str) -> dict:
    for rem in reminders:
        if rem.get("id") == rid:
            return rem
    raise KeyError(f"no reminder with id {rid!r}")


def complete_reminder(rid: str, next_due=None) -> dict:
    """Mark done. Interval reminders (every_days / monthly / yearly) roll forward instead."""
    reminders = load_reminders()
    rem = find(reminders, rid)
    kind, param = parse_repeat(rem)
    if next_due:
        rem["due"] = store.iso(parse_date(next_due))
        rem.pop("done", None)
    elif kind == "every_days":
        rem["due"] = store.iso(parse_date(rem["due"]) + timedelta(days=param))
    elif kind in ("monthly", "yearly"):
        zone = config.tz()
        current = datetime.combine(parse_date(rem["due"]), time(0), zone)
        nxt = next_occurrence(rem, current + timedelta(days=1), zone)
        rem["due"] = store.iso(nxt.date())
    else:
        rem["done"] = True
    save_reminders(reminders)
    return rem


def delete_reminder(rid: str) -> dict:
    reminders = load_reminders()
    rem = find(reminders, rid)
    reminders.remove(rem)
    save_reminders(reminders)
    return rem


def upcoming(reminders: list[dict], now: datetime, days: int = 14, default_time: str = "09:00",
             include_routine: bool = False) -> list[tuple[datetime, dict]]:
    """Next occurrence of each reminder within `days`, soonest first.

    Routine reminders (daily / weekly) are skipped unless include_routine.
    """
    zone = now.tzinfo
    start = datetime.combine(now.date(), time(0), zone)
    out = []
    for rem in reminders:
        if rem.get("done"):
            continue
        kind, _ = parse_repeat(rem)
        if kind in ROUTINE_KINDS and not include_routine:
            continue
        occ = occurrences(rem, start, now + timedelta(days=days), zone, default_time)
        if occ:
            out.append((occ[0], rem))
    out.sort(key=lambda pair: pair[0])
    return out


def today(reminders: list[dict], now: datetime, default_time: str = "09:00") -> list[tuple[datetime, dict]]:
    zone = now.tzinfo
    start = datetime.combine(now.date(), time(0), zone)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    out = [(occ, rem) for rem in reminders
           for occ in occurrences(rem, start, end, zone, default_time)]
    out.sort(key=lambda pair: pair[0])
    return out
