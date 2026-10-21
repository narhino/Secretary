"""Command line: `python -m secretary <command>`."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import brief, config, daylog, fitness, nutrition, reminders, scheduler, status, store, tasks


def _day(args):
    return reminders.parse_date(args.date) if getattr(args, "date", None) else config.now().date()


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ------------------------------------------------------------ delivery

def cmd_tick(args) -> int:
    settings = config.load_settings()
    now = config.now(settings)
    sent = reminders.load_sent()
    due = scheduler.collect_due(now, sent, settings, backup=args.backup)
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


def cmd_due(args) -> int:
    settings = config.load_settings()
    now = config.now(settings)
    due = scheduler.collect_due(now, reminders.load_sent(), settings)
    items = [{"key": n.key, "covers": n.covers, "id": n.reminder["id"], "title": n.reminder.get("title"),
              "when": reminders.describe_when(n.occurrence, now), "notes": n.reminder.get("notes"),
              "critical": scheduler.is_critical(n.reminder, settings)} for n, _ in due]
    if args.json:
        _print_json(items)
    else:
        for i in items:
            print(f"{i['key']}  {i['title']} — {i['when']}")
        if not items:
            print("nothing due")
    return 0


def cmd_mark_sent(args) -> int:
    now = config.now()
    sent = reminders.load_sent()
    for key in args.keys:
        sent[key] = now.isoformat()
    reminders.save_sent(sent, now)
    print(f"marked {len(args.keys)} as sent")
    return 0


def cmd_checkin_done(args) -> int:
    now = config.now()
    sent = reminders.load_sent()
    sent[f"{status.CHECKIN_PREFIX}{now.date().isoformat()}:{args.kind}"] = now.isoformat()
    # Also retire the matching built-in slot so other runners don't send it again.
    builtin = f"__{args.kind}__@"
    for n, _ in scheduler.collect_due(now, sent):
        if n.key.startswith(builtin):
            scheduler.mark_sent(sent, [n], now)
    reminders.save_sent(sent, now)
    print(f"{args.kind} check-in recorded")
    return 0


# ------------------------------------------------------------ views

def cmd_status(args) -> int:
    snap = status.snapshot()
    if args.json:
        _print_json(snap)
    else:
        for key, value in snap.items():
            print(f"{key}: {json.dumps(value, ensure_ascii=False, default=str)}")
    return 0


def cmd_week(args) -> int:
    w = status.weekly(_day(args))
    if args.json:
        _print_json(w)
    else:
        print(status.format_weekly(w))
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


# ------------------------------------------------------------ edits

def cmd_remind(args) -> int:
    if args.action == "add":
        rem = reminders.add_reminder(args.title, args.due, args.time, args.repeat,
                                     args.before.split(",") if args.before else None,
                                     args.category, args.notes, args.link, critical=args.critical)
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
    day = _day(args)
    sets = [fitness.parse_set(s) for s in args.sets]
    if args.rpe:
        for s in sets:
            s["rpe"] = s["rpe"] or args.rpe
    rows = fitness.log_sets(args.exercise, sets, day, args.notes or "")
    daylog.update(day, trained="yes")
    print(f"logged {len(rows)} set(s) of {rows[0]['exercise']} on {day}")
    return 0


def cmd_progress(args) -> int:
    print(fitness.progress_report(args.exercise, args.last))
    return 0


def cmd_prs(args) -> int:
    for pr in fitness.personal_records():
        print(f"{pr['exercise']:<24} {pr['set']:<10} e1RM {pr['e1rm']} kg ({pr['date']})")
    for g in fitness.goal_progress(config.now().date()):
        print(f"goal {g['name']}: {g['current']} / {g['target']}")
    return 0


def cmd_body(args) -> int:
    day = _day(args)
    fitness.log_body(day, args.weight, args.waist, args.bodyfat, args.notes or "")
    print(f"logged body metrics for {day}. Trend: {fitness.body_trend()}")
    return 0


def cmd_meal(args) -> int:
    day = _day(args)
    if args.action == "add":
        nutrients = {"kcal": args.kcal, "protein_g": args.protein, "carbs_g": args.carbs, "fat_g": args.fat,
                     "fiber_g": args.fiber, "sugar_g": args.sugar, "sodium_mg": args.sodium}
        row = nutrition.log_meal(day, args.food or "", args.meal or "", args.time or "", args.amount or "",
                                 nutrients, args.ref, args.qty, args.source or "", args.notes or "")
        print(f"logged {row['food']}: {row['kcal']} kcal, {row['protein_g'] or 0} g protein")
        print(nutrition.day_report(day).splitlines()[-1])
    elif args.action == "today":
        print(nutrition.day_report(day))
    elif args.action == "foods":
        for f in nutrition.load_foods():
            print(f"{f['id']:<22} {f['name']} ({f['serving']}): {f['kcal']} kcal, {f.get('protein_g', 0)} g protein")
    elif args.action == "rebuild":
        rows = nutrition.rebuild_daily()
        print(f"rebuilt nutrition/daily.csv ({len(rows)} days)")
    return 0


def cmd_day(args) -> int:
    day = _day(args)
    if args.action == "set":
        fields = {k: getattr(args, k) for k in daylog.FIELDS[1:] if getattr(args, k, None) not in (None, "")}
        row = daylog.update(day, **fields)
        print(f"{day}: {daylog.format_day(row)}")
    else:
        for row in daylog.recent(day, args.days):
            print(f"{row['date']}: {daylog.format_day(row)}")
    return 0


def cmd_validate(args) -> int:
    settings = config.load_settings()
    errors = reminders.validate(reminders.load_reminders(), config.tz(settings))
    errors += tasks.validate(tasks.load_tasks())
    for path in (config.WORKOUTS_FILE, config.BODY_FILE, nutrition.meals_file(), daylog.log_file()):
        try:
            store.read_csv(path)
        except Exception as exc:  # noqa: BLE001 - report any parse problem
            errors.append(f"{path.name}: {exc}")
    for path in (config.ROOT / "nutrition" / "foods.yaml", config.ROOT / "nutrition" / "targets.yaml",
                 config.ROOT / "fitness" / "targets.yaml"):
        try:
            store.load_yaml(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
    for e in errors:
        print(f"✗ {e}")
    print("ok" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


# ------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="secretary", description="Personal secretary toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="situation report for a check-in")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("week", help="weekly review numbers")
    s.add_argument("--json", action="store_true")
    s.add_argument("--date", help="last day of the week (default today)")
    s.set_defaults(func=cmd_week)

    sub.add_parser("brief", help="plain brief (facts for Claude)").set_defaults(func=cmd_brief)

    s = sub.add_parser("upcoming", help="list upcoming reminders")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--all", action="store_true", help="include daily/weekly routines")
    s.set_defaults(func=cmd_upcoming)

    s = sub.add_parser("due", help="reminders due now that nobody delivered yet")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_due)

    s = sub.add_parser("mark-sent", help="record reminder keys as delivered")
    s.add_argument("keys", nargs="+")
    s.set_defaults(func=cmd_mark_sent)

    s = sub.add_parser("checkin-done", help="record that a check-in was sent today")
    s.add_argument("kind", choices=list(scheduler.BUILTIN_KINDS) + ["adhoc"])
    s.set_defaults(func=cmd_checkin_done)

    s = sub.add_parser("tick", help="send due reminders (fallback sender)")
    s.add_argument("--send", choices=["print", "webhook"], default="print")
    s.add_argument("--backup", action="store_true", help="safety net: only critical, only after the grace period")
    s.add_argument("--dry-run", action="store_true", help="do not record anything as sent")
    s.set_defaults(func=cmd_tick)

    s = sub.add_parser("remind", help="add / complete / delete reminders")
    rs = s.add_subparsers(dest="action", required=True)
    a = rs.add_parser("add")
    a.add_argument("title")
    a.add_argument("--due", help="YYYY-MM-DD")
    a.add_argument("--time", help="HH:MM (local)")
    a.add_argument("--repeat", help="daily | weekdays | weekly | weekly:mon,thu | monthly | yearly | every 90d")
    a.add_argument("--before", help="lead times, e.g. 14d,7d,1d,0m")
    a.add_argument("--category")
    a.add_argument("--critical", action="store_true", help="the safety net must deliver it if Claude doesn't")
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

    s = sub.add_parser("meal", help="log meals and see daily nutrition")
    ms = s.add_subparsers(dest="action", required=True)
    a = ms.add_parser("add")
    a.add_argument("--ref", help="reference food id from nutrition/foods.yaml")
    a.add_argument("--qty", type=float, default=1.0, help="servings of --ref")
    a.add_argument("--food", help="description (required without --ref)")
    a.add_argument("--amount")
    a.add_argument("--meal", choices=nutrition.MEALS)
    a.add_argument("--time", help="HH:MM")
    for name in ("kcal", "protein", "carbs", "fat", "fiber", "sugar", "sodium"):
        a.add_argument(f"--{name}", type=float)
    a.add_argument("--source", help="estimate | label | reference | photo")
    a.add_argument("--notes")
    a.add_argument("--date")
    t = ms.add_parser("today")
    t.add_argument("--date")
    ms.add_parser("foods")
    ms.add_parser("rebuild")
    s.set_defaults(func=cmd_meal)

    s = sub.add_parser("day", help="daily life log: mood, energy, sleep, training, studio")
    ds = s.add_subparsers(dest="action", required=True)
    a = ds.add_parser("set")
    a.add_argument("--date")
    for name in ("mood", "energy", "stress", "sleep_h", "water_l"):
        a.add_argument(f"--{name.replace('_', '-')}", dest=name, type=float)
    a.add_argument("--trained", choices=sorted(daylog.CHOICES["trained"]))
    a.add_argument("--tidy", choices=sorted(daylog.CHOICES["tidy"]))
    for name in ("training", "priorities", "highlight", "notes"):
        a.add_argument(f"--{name}")
    sh = ds.add_parser("show")
    sh.add_argument("--days", type=int, default=7)
    sh.add_argument("--date")
    s.set_defaults(func=cmd_day)

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

    sub.add_parser("prs", help="personal records and goal progress").set_defaults(func=cmd_prs)

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
