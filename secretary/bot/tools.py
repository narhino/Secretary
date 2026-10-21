"""Tools the Discord secretary can call. Each returns (text, wrote_files)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from .. import config, daylog, fitness, nutrition, reminders, status, tasks

WRITABLE_DIRS = ("profile", "goals", "data", "fitness", "nutrition", "thailand", "journal", "memory", "home")
HIDDEN = (".git", ".env", "data/state")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".csv", ".txt", ".json"}
MAX_READ = 60_000


def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


_S = {"type": "string"}
TOOLS = [
    {"name": "read_file", "description": "Read a file from the secretary repo (memory). Paths are relative "
     "to the repo root, e.g. profile/me.md, goals/goals.md, thailand/immigration.md.",
     "input_schema": _schema({"path": _S}, ["path"])},
    {"name": "list_files", "description": "List files in a repo directory ('' for the root).",
     "input_schema": _schema({"path": _S})},
    {"name": "write_file", "description": "Create or overwrite a whole text file. Only inside profile/, goals/, "
     "data/, fitness/, nutrition/, thailand/, journal/, memory/, home/. Prefer edit_file for small changes.",
     "input_schema": _schema({"path": _S, "content": _S}, ["path", "content"])},
    {"name": "edit_file", "description": "Replace one exact, unique snippet of text in a file with new text.",
     "input_schema": _schema({"path": _S, "old_text": _S, "new_text": _S}, ["path", "old_text", "new_text"])},
    {"name": "append_file", "description": "Append text to the end of a file (e.g. a journal entry).",
     "input_schema": _schema({"path": _S, "text": _S}, ["path", "text"])},
    {"name": "add_reminder", "description": "Schedule a reminder that will ping the user on Discord. Times are "
     "local (the user's timezone). For deadlines give several lead times, e.g. ['14d','7d','2d','0m'].",
     "input_schema": _schema({
         "title": _S,
         "due": {"type": "string", "description": "YYYY-MM-DD. Required unless repeat is daily/weekly:days."},
         "time": {"type": "string", "description": "HH:MM, 24h local time"},
         "repeat": {"type": "string", "description": "daily | weekdays | weekly | weekly:mon,thu | monthly | "
                    "yearly | every 90d. Omit for one-off."},
         "notify_before": {"type": "array", "items": _S, "description": "lead times like 30m, 2h, 7d, 0m"},
         "category": {"type": "string", "description": "immigration, health, fitness, nutrition, finance, "
                      "admin, social, work ..."},
         "notes": _S, "link": _S}, ["title"])},
    {"name": "complete_reminder", "description": "Mark a reminder done. Interval reminders roll forward "
     "automatically; pass next_due to set the next date explicitly (e.g. from a 90-day receipt).",
     "input_schema": _schema({"id": _S, "next_due": _S}, ["id"])},
    {"name": "delete_reminder", "description": "Delete a reminder by id.",
     "input_schema": _schema({"id": _S}, ["id"])},
    {"name": "list_reminders", "description": "List upcoming reminder occurrences with their ids.",
     "input_schema": _schema({"days": {"type": "integer"}, "include_routine": {"type": "boolean"}})},
    {"name": "add_task", "description": "Add a task to the to-do list.",
     "input_schema": _schema({"title": _S, "due": _S,
                              "priority": {"type": "string", "enum": tasks.PRIORITIES},
                              "area": {"type": "string", "description": "thailand, fitness, nutrition, "
                                       "career, finance, personal ..."},
                              "goal": _S, "notes": _S}, ["title"])},
    {"name": "update_task", "description": "Update a task: status (todo, doing, waiting, done, dropped), "
     "priority, due, title, notes, waiting_on.",
     "input_schema": _schema({"id": _S, "status": {"type": "string", "enum": tasks.STATUSES},
                              "priority": {"type": "string", "enum": tasks.PRIORITIES},
                              "due": _S, "title": _S, "notes": _S, "waiting_on": _S}, ["id"])},
    {"name": "list_tasks", "description": "List open tasks, optionally for one area.",
     "input_schema": _schema({"area": _S})},
    {"name": "log_workout", "description": "Log sets for one exercise to the gym log.",
     "input_schema": _schema({
         "exercise": _S,
         "sets": {"type": "array", "items": _schema({"weight_kg": {"type": "number"},
                                                      "reps": {"type": "integer"},
                                                      "rpe": {"type": "number"}}, ["weight_kg", "reps"])},
         "date": {"type": "string", "description": "YYYY-MM-DD, default today"},
         "notes": _S}, ["exercise", "sets"])},
    {"name": "exercise_progress", "description": "Recent sessions, top sets and estimated 1RM for an exercise, "
     "or all personal records when exercise is omitted.",
     "input_schema": _schema({"exercise": _S})},
    {"name": "log_body", "description": "Log body weight (kg), waist (cm) and/or body fat %.",
     "input_schema": _schema({"weight_kg": {"type": "number"}, "waist_cm": {"type": "number"},
                              "bodyfat_pct": {"type": "number"}, "date": _S, "notes": _S})},
    {"name": "log_meal", "description": "Log ONE food or drink item to the nutrition sheet. Use `ref` (an id "
     "from nutrition/foods.yaml) with `qty` when it fits, otherwise give your best estimate of the nutrients. "
     "Call once per item.",
     "input_schema": _schema({
         "food": _S, "ref": _S, "qty": {"type": "number"}, "amount": _S,
         "meal": {"type": "string", "enum": nutrition.MEALS}, "time": {"type": "string", "description": "HH:MM"},
         "kcal": {"type": "number"}, "protein_g": {"type": "number"}, "carbs_g": {"type": "number"},
         "fat_g": {"type": "number"}, "fiber_g": {"type": "number"}, "sugar_g": {"type": "number"},
         "sodium_mg": {"type": "number"},
         "source": {"type": "string", "enum": ["estimate", "photo", "label", "reference"]},
         "date": _S, "notes": _S})},
    {"name": "log_day", "description": "Record how the day went: mood/energy/stress (1-10), sleep_h, trained "
     "(yes/no/rest), training (what), tidy (clean/ok/messy), water_l, priorities (e.g. 2/3), highlight, notes.",
     "input_schema": _schema({
         "date": _S, "mood": {"type": "number"}, "energy": {"type": "number"}, "stress": {"type": "number"},
         "sleep_h": {"type": "number"}, "trained": {"type": "string", "enum": ["yes", "no", "rest"]},
         "training": _S, "tidy": {"type": "string", "enum": ["clean", "ok", "messy"]},
         "water_l": {"type": "number"}, "priorities": _S, "highlight": _S, "notes": _S})},
    {"name": "nutrition_day", "description": "Meals logged on a day with totals vs targets (default today).",
     "input_schema": _schema({"date": _S})},
    {"name": "status_report", "description": "Situation report: today's schedule, due reminders, what is "
     "logged or missing today, training this week, nutrition so far.", "input_schema": _schema({})},
    {"name": "week_report", "description": "This week's numbers for a weekly review: training, goals, "
     "nutrition, mood/sleep/studio, tasks, upcoming events.", "input_schema": _schema({})},
]


class ToolError(Exception):
    pass


def _resolve(rel: str, write: bool = False) -> Path:
    rel = (rel or "").strip().lstrip("/")
    path = (config.ROOT / rel).resolve()
    root = config.ROOT.resolve()
    if path != root and root not in path.parents:
        raise ToolError("path is outside the repo")
    rel_posix = path.relative_to(root).as_posix() if path != root else ""
    if any(rel_posix == h or rel_posix.startswith(h + "/") for h in HIDDEN):
        raise ToolError("that path is private")
    if write:
        if not rel_posix.split("/")[0] in WRITABLE_DIRS:
            raise ToolError(f"can only write inside {', '.join(WRITABLE_DIRS)}")
        if path.suffix not in TEXT_SUFFIXES:
            raise ToolError(f"can only write {', '.join(sorted(TEXT_SUFFIXES))} files")
    return path


def _check_data_file(path: Path) -> None:
    """Refuse writes that would break the structured files."""
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if path == config.REMINDERS_FILE:
            errors = reminders.validate((data or {}).get("reminders") or [], config.tz())
            if errors:
                raise ToolError("; ".join(errors))
        if path == config.TASKS_FILE:
            errors = tasks.validate((data or {}).get("tasks") or [])
            if errors:
                raise ToolError("; ".join(errors))
    elif path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))


def _guarded_write(path: Path, new_text: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    try:
        _check_data_file(path)
    except Exception as exc:  # noqa: BLE001 - restore on any validation failure
        if old is None:
            path.unlink()
        else:
            path.write_text(old, encoding="utf-8")
        raise ToolError(f"write rejected, file left unchanged: {exc}") from exc


def _today() -> date:
    return config.now().date()


def run(name: str, args: dict) -> tuple[str, bool]:
    """Execute a tool. Returns (result text, whether files changed)."""
    try:
        return _run(name, args or {})
    except (ToolError, KeyError, ValueError, TypeError) as exc:
        raise ToolError(str(exc)) from exc


def _run(name: str, a: dict) -> tuple[str, bool]:
    if name == "read_file":
        path = _resolve(a["path"])
        if not path.is_file():
            raise ToolError(f"{a['path']} does not exist")
        text = path.read_text(encoding="utf-8", errors="replace")
        return (text[:MAX_READ] + ("\n…[truncated]" if len(text) > MAX_READ else "")) or "(empty file)", False

    if name == "list_files":
        path = _resolve(a.get("path", ""))
        if not path.is_dir():
            raise ToolError(f"{a.get('path')} is not a directory")
        root = config.ROOT.resolve()
        items = []
        for p in sorted(path.iterdir()):
            rel = p.relative_to(root).as_posix()
            if p.name.startswith(".") or any(rel == h or rel.startswith(h + "/") for h in HIDDEN):
                continue
            items.append(rel + ("/" if p.is_dir() else ""))
        return "\n".join(items) or "(empty)", False

    if name == "write_file":
        path = _resolve(a["path"], write=True)
        _guarded_write(path, a["content"])
        return f"wrote {a['path']}", True

    if name == "edit_file":
        path = _resolve(a["path"], write=True)
        text = path.read_text(encoding="utf-8")
        count = text.count(a["old_text"])
        if count != 1:
            raise ToolError(f"old_text found {count} times; it must match exactly once")
        _guarded_write(path, text.replace(a["old_text"], a["new_text"]))
        return f"edited {a['path']}", True

    if name == "append_file":
        path = _resolve(a["path"], write=True)
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        sep = "" if not old or old.endswith("\n") else "\n"
        _guarded_write(path, old + sep + a["text"].rstrip("\n") + "\n")
        return f"appended to {a['path']}", True

    if name == "add_reminder":
        rem = reminders.add_reminder(a["title"], a.get("due"), a.get("time"), a.get("repeat"),
                                     a.get("notify_before"), a.get("category"), a.get("notes"), a.get("link"))
        return f"added reminder {rem['id']}: {json.dumps(rem, default=str)}", True

    if name == "complete_reminder":
        rem = reminders.complete_reminder(a["id"], a.get("next_due"))
        return f"{rem['id']}: " + ("done" if rem.get("done") else f"next due {rem['due']}"), True

    if name == "delete_reminder":
        reminders.delete_reminder(a["id"])
        return f"deleted {a['id']}", True

    if name == "list_reminders":
        settings = config.load_settings()
        now = config.now(settings)
        items = reminders.upcoming(reminders.load_reminders(), now, int(a.get("days") or 30),
                                   settings["default_time"], bool(a.get("include_routine")))
        lines = [f"{occ:%a %d %b %H:%M} | {rem['id']} | {rem.get('title')}" for occ, rem in items]
        return "\n".join(lines) or "nothing scheduled in that window", False

    if name == "add_task":
        t = tasks.add_task(a["title"], _today(), due=a.get("due"), priority=a.get("priority"),
                           area=a.get("area"), goal=a.get("goal"), notes=a.get("notes"))
        return f"added task {t['id']}: {t['title']}", True

    if name == "update_task":
        fields = {k: v for k, v in a.items() if k != "id"}
        t = tasks.update_task(a["id"], _today(), **fields)
        return f"updated {t['id']}: {json.dumps(t, default=str)}", True

    if name == "list_tasks":
        today = _today()
        lines = [tasks.format_task(t, today) for t in tasks.open_tasks(area=a.get("area"))]
        return "\n".join(lines) or "no open tasks", False

    if name == "log_workout":
        day = reminders.parse_date(a.get("date")) or _today()
        sets = [{"weight_kg": s.get("weight_kg", 0), "reps": s["reps"], "rpe": s.get("rpe")} for s in a["sets"]]
        rows = fitness.log_sets(a["exercise"], sets, day, a.get("notes") or "")
        return f"logged {len(rows)} sets of {rows[0]['exercise']} on {day}\n" + \
            fitness.progress_report(rows[0]["exercise"], 3), True

    if name == "exercise_progress":
        if a.get("exercise"):
            return fitness.progress_report(a["exercise"]), False
        prs = fitness.personal_records()
        return "\n".join(f"{p['exercise']}: {p['set']} (e1RM {p['e1rm']} kg, {p['date']})" for p in prs) \
            or "no workouts logged yet", False

    if name == "log_body":
        day = reminders.parse_date(a.get("date")) or _today()
        fitness.log_body(day, a.get("weight_kg"), a.get("waist_cm"), a.get("bodyfat_pct"), a.get("notes") or "")
        return f"logged body metrics for {day}. Trend: {fitness.body_trend()}", True

    if name == "log_meal":
        day = reminders.parse_date(a.get("date")) or _today()
        nutrients = {k: a.get(k) for k in nutrition.NUTRIENTS}
        row = nutrition.log_meal(day, a.get("food") or "", a.get("meal") or "", a.get("time") or "",
                                 a.get("amount") or "", nutrients, a.get("ref"), float(a.get("qty") or 1),
                                 a.get("source") or "", a.get("notes") or "")
        return f"logged {row['food']} ({row['kcal']} kcal)\n" + nutrition.day_report(day), True

    if name == "log_day":
        day = reminders.parse_date(a.get("date")) or _today()
        fields = {k: v for k, v in a.items() if k != "date"}
        return f"{day}: {daylog.format_day(daylog.update(day, **fields))}", True

    if name == "nutrition_day":
        return nutrition.day_report(reminders.parse_date(a.get("date")) or _today()), False

    if name == "status_report":
        return json.dumps(status.snapshot(), ensure_ascii=False, default=str), False

    if name == "week_report":
        return json.dumps(status.weekly(), ensure_ascii=False, default=str), False

    raise ToolError(f"unknown tool {name}")
