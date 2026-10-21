"""Situation reports Claude reads before writing a check-in or the weekly review.

These are facts for Claude, not messages for the user: Claude turns them into natural words.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import config, daylog, fitness, nutrition, reminders, scheduler, tasks

CHECKIN_PREFIX = "checkin:"


def part_of_day(now: datetime) -> str:
    h = now.hour
    if 5 <= h < 11:
        return "morning"
    if 11 <= h < 16:
        return "midday"
    if 16 <= h < 23:
        return "evening"
    return "night"


def checkins_sent(sent: dict, day: date) -> list[str]:
    prefix = f"{CHECKIN_PREFIX}{day.isoformat()}:"
    return sorted(k[len(prefix):] for k in sent if k.startswith(prefix))


def _event(occ: datetime, rem: dict) -> dict:
    return {"at": occ.strftime("%Y-%m-%d %H:%M"), "id": rem["id"], "title": rem.get("title"),
            "category": rem.get("category"), "critical": bool(rem.get("critical")),
            "notes": rem.get("notes")}


def snapshot(now: datetime | None = None) -> dict:
    settings = config.load_settings()
    now = now or config.now(settings)
    today = now.date()
    default_time = settings["default_time"]
    rems = reminders.load_reminders()
    sent = reminders.load_sent()

    due = [n for n, _ in scheduler.collect_due(now, sent, settings) if not n.reminder["id"].startswith("__")]
    todays = [(o, r) for o, r in reminders.today(rems, now, default_time)]
    gym_today = [r.get("title") for _, r in todays if r.get("category") == "fitness"]
    open_ = tasks.open_tasks()
    targets = nutrition.load_targets()
    meals_today = nutrition.meals_on(today)
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    last_workout = fitness.last_session_day()

    return {
        "now": now.strftime("%A %d %B %Y %H:%M"),
        "part_of_day": part_of_day(now),
        "checkins_already_sent_today": checkins_sent(sent, today),
        "due_reminders": [{"key": n.key, "covers": n.covers, **_event(n.occurrence, n.reminder),
                           "lead": reminders.format_duration(n.lead)} for n in due],
        "today": [_event(o, r) for o, r in todays],
        "next_7_days": [_event(o, r) for o, r in reminders.upcoming(rems, now + timedelta(days=1), 7, default_time)],
        "tasks": {
            "overdue": [tasks.format_task(t, today) for t in open_
                        if t.get("due") and reminders.parse_date(t["due"]) < today],
            "due_today": [tasks.format_task(t, today) for t in open_
                          if t.get("due") and reminders.parse_date(t["due"]) == today],
            "high_priority": [tasks.format_task(t, today) for t in open_ if t.get("priority") == "high"][:6],
            "open_count": len(open_),
        },
        "nutrition_today": {
            "items_logged": len(meals_today),
            "meals_logged": sorted({m["meal"] for m in meals_today if m.get("meal")}),
            "totals": nutrition.totals(meals_today),
            "targets": {k: targets.get(k) for k in ("kcal", "protein_g", "carbs_g", "fat_g")},
        },
        "daylog_today": daylog.get(today),
        "daylog_missing_today": daylog.missing_today(today),
        "yesterday": {"daylog": daylog.format_day(daylog.get(yesterday)),
                      "nutrition": nutrition.totals(nutrition.meals_on(yesterday))},
        "training": {
            "gym_planned_today": gym_today,
            "last_workout": last_workout,
            "days_since_last_workout": (today - date.fromisoformat(last_workout)).days if last_workout else None,
            "sessions_this_week": len(fitness.session_days(week_start, today)),
            "sessions_target": fitness.load_targets().get("sessions_per_week"),
        },
    }


def weekly(end: date | None = None) -> dict:
    settings = config.load_settings()
    now = config.now(settings)
    end = end or now.date()
    start = end - timedelta(days=6)
    all_tasks = tasks.load_tasks()
    done = [t["title"] for t in all_tasks if t.get("status") == "done" and t.get("completed")
            and start.isoformat() <= str(t["completed"]) <= end.isoformat()]
    rems = reminders.load_reminders()
    horizon = datetime.combine(end + timedelta(days=1), time(0), now.tzinfo)
    return {
        "week": f"{start} to {end}",
        "training": {
            "sessions": len(fitness.session_days(start, end)),
            "target_per_week": fitness.load_targets().get("sessions_per_week"),
            "goals": fitness.goal_progress(end),
            "prs": [p for p in fitness.personal_records() if start.isoformat() <= p["date"] <= end.isoformat()],
            "body_weight": fitness.body_trend(),
        },
        "nutrition": nutrition.week_stats(end),
        "life": daylog.week_stats(end),
        "tasks": {"done": done,
                  "overdue": [t["title"] for t in tasks.open_tasks(all_tasks)
                              if t.get("due") and reminders.parse_date(t["due"]) < end]},
        "next_14_days": [_event(o, r) for o, r in reminders.upcoming(rems, horizon, 14, settings["default_time"])],
    }


def format_weekly(w: dict) -> str:
    tr, nu, life = w["training"], w["nutrition"], w["life"]
    lines = [f"Week {w['week']}",
             f"Training: {tr['sessions']} sessions" + (f" / target {tr['target_per_week']}" if tr["target_per_week"] else ""),
             f"Body weight: {tr['body_weight']}"]
    for g in tr["goals"]:
        lines.append(f"  goal {g['name']}: {g['current']} → {g['target']}"
                     + (f" ({g['days_left']} days left)" if g["days_left"] is not None else ""))
    if tr["prs"]:
        lines.append("PRs: " + ", ".join(f"{p['exercise']} {p['set']}" for p in tr["prs"]))
    if nu.get("days_logged"):
        lines.append(f"Nutrition: {nu['days_logged']} days logged, avg {nu['avg']['kcal']} kcal / "
                     f"{nu['avg']['protein_g']} g protein, on target {nu['days_on_target']} days")
    else:
        lines.append("Nutrition: nothing logged")
    lines.append(f"Life: mood {life['avg_mood']}, energy {life['avg_energy']}, stress {life['avg_stress']}, "
                 f"sleep {life['avg_sleep_h']} h, trained {life['trained_days']} days, studio {life['tidy']}")
    lines.append(f"Tasks done: {len(w['tasks']['done'])}; overdue: {len(w['tasks']['overdue'])}")
    if w["next_14_days"]:
        lines.append("Next 14 days: " + "; ".join(f"{e['at'][5:16]} {e['title']}" for e in w["next_14_days"]))
    return "\n".join(lines)
