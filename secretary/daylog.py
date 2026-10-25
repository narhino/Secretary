"""Daily life log (data/daily.csv): mood, energy, sleep, training, studio, priorities."""
from __future__ import annotations

from datetime import date, timedelta

from . import config, store

FIELDS = ["date", "mood", "energy", "stress", "sleep_h", "trained", "training", "tidy",
          "water_l", "steps", "active_kcal", "distance_km", "priorities", "highlight", "notes"]
COUNTS = {"steps", "active_kcal"}
SCALES = {"mood": (1, 10), "energy": (1, 10), "stress": (1, 10)}
CHOICES = {"trained": {"yes", "no", "rest"}, "tidy": {"clean", "ok", "messy"}}
CORE = ["mood", "energy", "sleep_h", "trained", "tidy"]


def log_file():
    return config.DATA / "daily.csv"


def _check(field: str, value) -> str:
    if value in (None, ""):
        return ""
    if field in SCALES:
        lo, hi = SCALES[field]
        v = float(value)
        if not lo <= v <= hi:
            raise ValueError(f"{field} must be {lo}-{hi}")
        return str(int(v)) if v.is_integer() else str(v)
    if field in ("sleep_h", "water_l", "distance_km"):
        return str(round(float(value), 1))
    if field in COUNTS:
        v = float(value)
        if v < 0:
            raise ValueError(f"{field} can't be negative")
        return str(int(round(v)))
    if field in CHOICES:
        v = str(value).strip().lower()
        if v not in CHOICES[field]:
            raise ValueError(f"{field} must be one of {sorted(CHOICES[field])}")
        return v
    return str(value).strip()


def load() -> list[dict]:
    return store.read_csv(log_file())


def get(day: date) -> dict:
    for row in load():
        if row["date"] == day.isoformat():
            return row
    return {}


def update(day: date, **fields) -> dict:
    """Set fields for a day (other fields keep their values). Text fields append."""
    unknown = set(fields) - set(FIELDS[1:])
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")
    rows = load()
    row = next((r for r in rows if r["date"] == day.isoformat()), None)
    if row is None:
        row = {f: "" for f in FIELDS}
        row["date"] = day.isoformat()
        rows.append(row)
    for key, value in fields.items():
        value = _check(key, value)
        if value == "":
            continue
        if key in ("training", "highlight", "notes") and row.get(key) and value not in row[key]:
            row[key] = f"{row[key]}; {value}"
        else:
            row[key] = value
    rows.sort(key=lambda r: r["date"])
    path = log_file()
    if path.exists():
        path.unlink()
    store.append_csv(path, FIELDS, rows)
    return row


def missing_today(day: date) -> list[str]:
    row = get(day)
    return [f for f in CORE if not row.get(f)]


def recent(end: date, days: int = 7) -> list[dict]:
    start = (end - timedelta(days=days - 1)).isoformat()
    return [r for r in load() if start <= r["date"] <= end.isoformat()]


def week_stats(end: date, days: int = 7) -> dict:
    rows = recent(end, days)

    def avg(field):
        vals = [float(r[field]) for r in rows if r.get(field)]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "days_logged": len(rows),
        "avg_mood": avg("mood"), "avg_energy": avg("energy"), "avg_stress": avg("stress"),
        "avg_sleep_h": avg("sleep_h"),
        "trained_days": sum(1 for r in rows if r.get("trained") == "yes"),
        "avg_steps": avg("steps"),
        "tidy": {k: sum(1 for r in rows if r.get("tidy") == k) for k in ("clean", "ok", "messy")},
        "low_mood_days": [r["date"] for r in rows if r.get("mood") and float(r["mood"]) <= 4],
    }


def format_day(row: dict) -> str:
    if not row:
        return "nothing logged"
    parts = []
    for f in ("mood", "energy", "stress"):
        if row.get(f):
            parts.append(f"{f} {row[f]}/10")
    if row.get("sleep_h"):
        parts.append(f"slept {row['sleep_h']} h")
    if row.get("trained"):
        parts.append(f"trained: {row['trained']}" + (f" ({row['training']})" if row.get("training") else ""))
    if row.get("steps"):
        parts.append(f"{int(float(row['steps'])):,} steps")
    if row.get("tidy"):
        parts.append(f"studio {row['tidy']}")
    if row.get("priorities"):
        parts.append(f"priorities {row['priorities']}")
    if row.get("highlight"):
        parts.append(f"highlight: {row['highlight']}")
    return ", ".join(parts) or "nothing logged"
