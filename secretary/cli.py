"""Command line: `python -m secretary <command>`."""
from __future__ import annotations

import argparse
import os
import sys

from . import brief, config, fitness, reminders, scheduler, store, tasks


def cmd_tick(args) -> int:
    settings = config.load_settings()
    now = config.now(settings)
    sent = reminders.load_sent()
    due = scheduler.collect_due(now, sent, settings)
    if not due:
        print("nothing due")
        return 0
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if args.send == "webhook" and not url:
        print("DISCORD_WEBHOOK_URL is not set", file=sys.stderr)
        return 1
    mention = config.owner_id(settings) if settings["discord"].get("mention_owner") else ""
    for n, text in due:
        if args.send == "webhook":
            from .notify import send_webhook
            send_webhook(url, text, mention)
        else:
            print(f"--- {n.key}\n{text}\n")
        scheduler.mark_sent(sent, [n], now)
    if not args.dry_run:
        reminders.save_sent(sent, now)
    print(f"sent {len(due)} notification(s)")
    return 0


def cmd_brief(args) -> int:
    settings = config.load_settings()
    print(brief.build_brief(config.now(settings), settings))
    return 0


def cmd_upcoming(args) -> int:
    settings = config.load_settings()
    now = config.now(settings)
    items = reminders.upcoming(reminders.load_reminders(), now, args.days, settings["default_time"],
                               include_routine=args.all)
    for occ, rem in items:
        print(f"{occ:%a %d %b %H:%M}  {rem['id']:<28} {rem.get('title')}")
    if not items:
        print(f"nothing in the next {args.days} days")
    return 0


def cmd_remind(args) -> int:
    if args.action == "add":
        rem = reminders.add_reminder(args.title, args.due, args.time, args.repeat,
                                     args.before.split(",") if args.before else None,
                                     args.category, args.notes, args.link)
        print(f"added {rem['id']}")
    elif args.action == "done":
        rem = reminders.complete_reminder(args.id, args.next_due)
        print(f"{rem['id']}: " + ("done" if rem.get("done") else f"next due {rem['due']}"))
    elif args.action == "delete":
        reminders.delete_reminder(args.id)
        print(f"deleted {args.id}")
    return 0


def cmd_task(args) -> int:
    today = config.now().date()
    if args.action == "add":
        t = tasks.add_task(args.title, today, due=args.due, priority=args.priority, area=args.area,
                           notes=args.notes)
        print(f"added {t['id']}: {t['title']}")
    elif args.action == "done":
        t = tasks.update_task(args.id, today, status="done")
        print(f"done {t['id']}: {t['title']}")
    elif args.action == "list":
        for t in tasks.open_tasks(area=args.area):
            print(tasks.format_task(t, today))
    return 0


def cmd_log(args) -> int:
    day = reminders.parse_date(args.date) if args.date else config.now().date()
    sets = [fitness.parse_set(s) for s in args.sets]
    if args.rpe:
        for s in sets:
            s["rpe"] = s["rpe"] or args.rpe
    rows = fitness.log_sets(args.exercise, sets, day, args.notes or "")
    print(f"logged {len(rows)} set(s) of {rows[0]['exercise']} on {day}")
    return 0


def cmd_progress(args) -> int:
    print(fitness.progress_report(args.exercise, args.last))
    return 0


def cmd_prs(args) -> int:
    for pr in fitness.personal_records():
        print(f"{pr['exercise']:<24} {pr['set']:<10} e1RM {pr['e1rm']} kg ({pr['date']})")
    return 0


def cmd_body(args) -> int:
    day = reminders.parse_date(args.date) if args.date else config.now().date()
    fitness.log_body(day, args.weight, args.waist, args.bodyfat, args.notes or "")
    print(f"logged body metrics for {day}. Trend: {fitness.body_trend()}")
    return 0


def cmd_validate(args) -> int:
    settings = config.load_settings()
    errors = reminders.validate(reminders.load_reminders(), config.tz(settings))
    errors += tasks.validate(tasks.load_tasks())
    for path in (config.WORKOUTS_FILE, config.BODY_FILE):
        try:
            store.read_csv(path)
        except Exception as exc:  # noqa: BLE001 - report any parse problem
            errors.append(f"{path.name}: {exc}")
    for e in errors:
        print(f"✗ {e}")
    print("ok" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="secretary", description="Personal secretary toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("tick", help="send reminders that are due now")
    s.add_argument("--send", choices=["print", "webhook"], default="print")
    s.add_argument("--dry-run", action="store_true", help="do not record anything as sent")
    s.set_defaults(func=cmd_tick)

    sub.add_parser("brief", help="print today's brief").set_defaults(func=cmd_brief)

    s = sub.add_parser("upcoming", help="list upcoming reminders")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--all", action="store_true", help="include daily/weekly routines")
    s.set_defaults(func=cmd_upcoming)

    s = sub.add_parser("remind", help="add / complete / delete reminders")
    rs = s.add_subparsers(dest="action", required=True)
    a = rs.add_parser("add")
    a.add_argument("title")
    a.add_argument("--due", help="YYYY-MM-DD")
    a.add_argument("--time", help="HH:MM (local)")
    a.add_argument("--repeat", help="daily | weekdays | weekly | weekly:mon,thu | monthly | yearly | every 90d")
    a.add_argument("--before", help="lead times, e.g. 14d,7d,1d,0m")
    a.add_argument("--category")
    a.add_argument("--notes")
    a.add_argument("--link")
    d = rs.add_parser("done")
    d.add_argument("id")
    d.add_argument("--next-due", help="explicit next due date (e.g. from a 90-day receipt)")
    rs.add_parser("delete").add_argument("id")
    s.set_defaults(func=cmd_remind)

    s = sub.add_parser("task", help="add / complete / list tasks")
    ts = s.add_subparsers(dest="action", required=True)
    a = ts.add_parser("add")
    a.add_argument("title")
    a.add_argument("--due")
    a.add_argument("--priority", choices=tasks.PRIORITIES)
    a.add_argument("--area")
    a.add_argument("--notes")
    ts.add_parser("done").add_argument("id")
    ls = ts.add_parser("list")
    ls.add_argument("--area")
    s.set_defaults(func=cmd_task)

    s = sub.add_parser("log", help="log gym sets, e.g. log 'Bench Press' 80x8 80x8 77.5x7@9")
    s.add_argument("exercise")
    s.add_argument("sets", nargs="+")
    s.add_argument("--rpe", type=float)
    s.add_argument("--date")
    s.add_argument("--notes")
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("progress", help="progress for one exercise")
    s.add_argument("exercise")
    s.add_argument("--last", type=int, default=6)
    s.set_defaults(func=cmd_progress)

    sub.add_parser("prs", help="personal records").set_defaults(func=cmd_prs)

    s = sub.add_parser("body", help="log body weight / waist / body fat")
    s.add_argument("--weight", type=float)
    s.add_argument("--waist", type=float)
    s.add_argument("--bodyfat", type=float)
    s.add_argument("--date")
    s.add_argument("--notes")
    s.set_defaults(func=cmd_body)

    sub.add_parser("validate", help="check data files").set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    config.load_env_file()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
