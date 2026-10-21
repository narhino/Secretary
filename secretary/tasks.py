"""Task list stored in data/tasks.yaml."""
from __future__ import annotations

from datetime import date

from . import config, store
from .reminders import parse_date

STATUSES = ["todo", "doing", "waiting", "done", "dropped"]
PRIORITIES = ["high", "med", "low"]
OPEN = {"todo", "doing", "waiting"}
FIELDS = ["title", "status", "priority", "area", "due", "goal", "notes", "waiting_on"]


def load_tasks() -> list[dict]:
    data = store.load_yaml(config.TASKS_FILE, {}) or {}
    return list(data.get("tasks") or [])


def save_tasks(tasks: list[dict]) -> None:
    header = store.yaml_header(config.TASKS_FILE)
    store.save_yaml(config.TASKS_FILE, {"tasks": tasks}, header)


def _next_id(tasks: list[dict]) -> str:
    nums = [int(t["id"][2:]) for t in tasks if str(t.get("id", "")).startswith("t-")
            and str(t["id"][2:]).isdigit()]
    return f"t-{(max(nums) if nums else 0) + 1:04d}"


def _clean(fields: dict) -> dict:
    out = {}
    for key, value in fields.items():
        if key not in FIELDS or value in (None, ""):
            continue
        if key == "status" and value not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if key == "priority" and value not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        if key == "due":
            value = store.iso(parse_date(value))
        out[key] = value
    return out


def add_task(title: str, today: date, **fields) -> dict:
    tasks = load_tasks()
    task = {"id": _next_id(tasks), "title": title, "status": "todo", "priority": "med"}
    task.update(_clean(fields))
    task["created"] = today.isoformat()
    tasks.append(task)
    save_tasks(tasks)
    return task


def update_task(tid: str, today: date, **fields) -> dict:
    tasks = load_tasks()
    for task in tasks:
        if task.get("id") == tid:
            task.update(_clean(fields))
            if task.get("status") == "done":
                task.setdefault("completed", today.isoformat())
            else:
                task.pop("completed", None)
            save_tasks(tasks)
            return task
    raise KeyError(f"no task with id {tid!r}")


def open_tasks(tasks: list[dict] | None = None, area: str | None = None) -> list[dict]:
    tasks = load_tasks() if tasks is None else tasks
    out = [t for t in tasks if t.get("status", "todo") in OPEN
           and (area is None or t.get("area") == area)]
    rank = {p: i for i, p in enumerate(PRIORITIES)}
    out.sort(key=lambda t: (str(t.get("due") or "9999"), rank.get(t.get("priority", "med"), 1)))
    return out


def format_task(task: dict, today: date | None = None) -> str:
    bits = [f"`{task['id']}`", task["title"]]
    if task.get("priority") == "high":
        bits.insert(1, "🔥")
    due = parse_date(task.get("due"))
    if due:
        if today and due < today:
            bits.append(f"(overdue since {due:%d %b})")
        elif today and due == today:
            bits.append("(due today)")
        else:
            bits.append(f"(due {due:%a %d %b})")
    if task.get("status") in ("doing", "waiting"):
        bits.append(f"[{task['status']}{': ' + task['waiting_on'] if task.get('waiting_on') else ''}]")
    return " ".join(bits)


def validate(tasks: list[dict]) -> list[str]:
    errors, seen = [], set()
    for i, task in enumerate(tasks):
        tid = task.get("id")
        if not tid:
            errors.append(f"task #{i + 1} has no id")
            continue
        if tid in seen:
            errors.append(f"duplicate task id {tid}")
        seen.add(tid)
        if not task.get("title"):
            errors.append(f"{tid}: missing title")
        if task.get("status", "todo") not in STATUSES:
            errors.append(f"{tid}: bad status {task.get('status')!r}")
        if task.get("priority", "med") not in PRIORITIES:
            errors.append(f"{tid}: bad priority {task.get('priority')!r}")
        try:
            parse_date(task.get("due"))
        except ValueError as exc:
            errors.append(f"{tid}: {exc}")
    return errors
