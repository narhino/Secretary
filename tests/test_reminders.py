from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import yaml

from secretary import reminders as R
from secretary import scheduler

BKK = ZoneInfo("Asia/Bangkok")


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=BKK)


def test_parse_duration():
    assert R.parse_duration("30m") == timedelta(minutes=30)
    assert R.parse_duration("2h") == timedelta(hours=2)
    assert R.parse_duration("7d") == timedelta(days=7)
    assert R.parse_duration("1w") == timedelta(weeks=1)
    assert R.parse_duration(0) == timedelta(0)
    assert R.format_duration(timedelta(days=14)) == "2w"
    assert R.format_duration(timedelta(0)) == "0m"
    with pytest.raises(ValueError):
        R.parse_duration("soon")


def test_unquoted_yaml_time_is_read_as_minutes():
    rem = yaml.safe_load("id: x\ntitle: X\ntime: 18:30\ndue: 2026-10-22\n")
    assert R.reminder_time(rem, "09:00").strftime("%H:%M") == "18:30"


def test_time_inside_due_string():
    rem = {"id": "x", "title": "X", "due": "2026-10-22 14:15"}
    assert R.occurrences(rem, at("2026-10-22T00:00"), at("2026-10-23T00:00"), BKK) == [at("2026-10-22T14:15")]


def test_one_off_with_leads_fires_each_lead_once():
    rem = {"id": "ninety", "title": "90-day report", "due": "2026-11-10", "time": "09:00",
           "notify_before": ["7d", "1d", "0m"]}
    sent = {}
    fired = []
    t = at("2026-11-02T08:00")
    while t <= at("2026-11-11T00:00"):
        due = R.due_notifications([rem], t, t - timedelta(hours=6), sent)
        for n in due:
            fired.append((n.fire_at, n.lead))
            scheduler.mark_sent(sent, [n], t)
        t += timedelta(minutes=30)
    assert [lead for _, lead in fired] == [timedelta(days=7), timedelta(days=1), timedelta(0)]
    assert fired[0][0] == at("2026-11-03T09:00")


def test_missed_leads_collapse_into_latest():
    rem = {"id": "a", "title": "A", "due": "2026-11-10", "time": "09:00", "notify_before": ["2h", "1h", "0m"]}
    sent = {}
    now = at("2026-11-10T09:05")
    due = R.due_notifications([rem], now, now - timedelta(hours=6), sent)
    assert len(due) == 1 and due[0].lead == timedelta(0) and len(due[0].covers) == 3
    scheduler.mark_sent(sent, due, now)
    assert R.due_notifications([rem], now + timedelta(minutes=1), now - timedelta(hours=6), sent) == []


def test_weekly_repeat_days():
    rem = {"id": "gym", "title": "Gym", "repeat": "weekly:mon,thu", "time": "18:00"}
    occ = R.occurrences(rem, at("2026-10-19T00:00"), at("2026-10-26T23:59"), BKK)
    assert [o.strftime("%a %d") for o in occ] == ["Mon 19", "Thu 22", "Mon 26"]
    rem2 = {"id": "gym2", "title": "Gym", "repeat": {"weekly": ["tue", "sat"]}, "time": "07:00"}
    assert len(R.occurrences(rem2, at("2026-10-19T00:00"), at("2026-10-25T23:59"), BKK)) == 2


def test_every_days_from_anchor():
    rem = {"id": "r", "title": "R", "due": "2026-10-01", "repeat": "every 90d", "time": "09:00"}
    occ = R.occurrences(rem, at("2026-10-02T00:00"), at("2027-04-30T00:00"), BKK)
    assert [o.date().isoformat() for o in occ] == ["2026-12-30", "2027-03-30"]


def test_monthly_clamps_to_month_end():
    rem = {"id": "rent", "title": "Rent", "due": "2026-01-31", "repeat": "monthly"}
    occ = R.occurrences(rem, at("2026-02-01T00:00"), at("2026-04-30T23:59"), BKK)
    assert [o.date().isoformat() for o in occ] == ["2026-02-28", "2026-03-31", "2026-04-30"]


def test_until_and_done_stop_repeats():
    rem = {"id": "d", "title": "D", "repeat": "daily", "due": "2026-10-20", "until": "2026-10-22"}
    assert len(R.occurrences(rem, at("2026-10-01T00:00"), at("2026-10-30T00:00"), BKK)) == 3
    rem["done"] = True
    assert R.occurrences(rem, at("2026-10-01T00:00"), at("2026-10-30T00:00"), BKK) == []


def test_validate_reports_problems():
    errors = R.validate([{"id": "a", "title": "A"},
                         {"id": "a", "title": "B", "due": "2026-10-10"},
                         {"id": "c", "title": "C", "repeat": "fortnightly"},
                         {"title": "no id"}], BKK)
    joined = " | ".join(errors)
    assert "one-off reminder needs a due date" in joined
    assert "duplicate reminder id a" in joined
    assert "unknown repeat" in joined
    assert "has no id" in joined


def test_add_complete_and_roll_forward(home):
    rem = R.add_reminder("90-day report", "2026-11-10", "09:00", "every 90d", ["14d", "7d", "0m"], "immigration")
    assert rem["id"] == "90-day-report"
    again = R.add_reminder("90-day report", "2026-12-01")
    assert again["id"] == "90-day-report-2"
    rolled = R.complete_reminder("90-day-report")
    assert rolled["due"] == "2027-02-08" and not rolled.get("done")
    explicit = R.complete_reminder("90-day-report", next_due="2027-02-05")
    assert explicit["due"] == "2027-02-05"
    assert R.complete_reminder("90-day-report-2")["done"] is True
    with pytest.raises(ValueError):
        R.add_reminder("bad", repeat="sometimes")


def test_describe_when():
    now = at("2026-10-21T08:00")
    assert R.describe_when(at("2026-10-21T18:00"), now) == "today at 18:00"
    assert R.describe_when(at("2026-10-22T09:00"), now) == "tomorrow at 09:00"
    assert R.describe_when(at("2026-10-28T09:00"), now).startswith("in 7 days")
    assert R.describe_when(at("2026-10-18T09:00"), now).startswith("overdue by 3 days")


def test_builtin_checkins_are_due_and_rendered(home):
    from secretary import config
    settings = config.load_settings()
    now = at("2026-10-21T08:01")
    due = scheduler.collect_due(now, {}, settings)
    texts = {n.reminder["id"]: t for n, t in due}
    assert "__morning__" in texts and "Good morning" in texts["__morning__"]
    # Hours later the stale check-in is not sent.
    assert scheduler.collect_due(at("2026-10-21T11:00"), {}, settings) == []
    # Sunday evening brings the weekly review.
    sunday = scheduler.collect_due(at("2026-10-25T19:01"), {}, settings)
    assert "__weekly__" in [n.reminder["id"] for n, _ in sunday]


def test_backup_only_sends_critical_after_grace(home):
    from secretary import config
    R.add_reminder("Orthodontist", "2026-10-21", "15:00", None, ["3h", "0m"], "appointment")
    R.add_reminder("Buy shampoo", "2026-10-21", "12:00", category="home")
    settings = config.load_settings()
    # 12:10: the 3h-before ping is only 10 minutes late, so the safety net waits for Claude.
    assert scheduler.collect_due(at("2026-10-21T12:10"), {}, settings, backup=True) == []
    late = scheduler.collect_due(at("2026-10-21T12:50"), {}, settings, backup=True)
    assert [n.reminder["id"] for n, _ in late] == ["orthodontist"]
    text = late[0][1]
    assert "Orthodontist" in text and "today at 15:00" in text and "⏰" not in text
    # Once Claude has marked it sent, the safety net stays quiet.
    sent = {k: "2026-10-21T12:01:00+07:00" for n, _ in late for k in n.covers}
    assert scheduler.collect_due(at("2026-10-21T12:50"), sent, settings, backup=True) == []
