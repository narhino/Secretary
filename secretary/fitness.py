"""Gym log (fitness/workouts.csv) and body metrics (fitness/body.csv)."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from . import config, store

WORKOUT_FIELDS = ["date", "exercise", "set", "weight_kg", "reps", "rpe", "notes"]
BODY_FIELDS = ["date", "weight_kg", "waist_cm", "bodyfat_pct", "notes"]
_SET = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+)\s*(?:@\s*(\d+(?:\.\d+)?))?\s*$", re.I)


def parse_set(text: str) -> dict:
    """'80x8' or '80x8@8' -> {'weight_kg': 80.0, 'reps': 8, 'rpe': 8.0}."""
    m = _SET.match(text)
    if not m:
        raise ValueError(f"bad set {text!r}: use WEIGHTxREPS, e.g. 80x8 or 80x8@8")
    return {"weight_kg": float(m.group(1)), "reps": int(m.group(2)),
            "rpe": float(m.group(3)) if m.group(3) else None}


def e1rm(weight: float, reps: int) -> float:
    """Estimated one-rep max (Epley)."""
    if reps <= 0:
        return 0.0
    return weight if reps == 1 else weight * (1 + reps / 30)


def _num(value) -> str:
    if value in (None, ""):
        return ""
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def normalise_exercise(name: str) -> str:
    return " ".join(w.capitalize() if w.islower() else w for w in name.strip().split())


def log_sets(exercise: str, sets: list[dict], day: date, notes: str = "") -> list[dict]:
    exercise = normalise_exercise(exercise)
    existing = [r for r in store.read_csv(config.WORKOUTS_FILE)
                if r["date"] == day.isoformat() and r["exercise"].lower() == exercise.lower()]
    start = len(existing)
    rows = []
    for i, s in enumerate(sets, start=start + 1):
        rows.append({"date": day.isoformat(), "exercise": exercise, "set": i,
                     "weight_kg": _num(s.get("weight_kg")), "reps": int(s["reps"]),
                     "rpe": _num(s.get("rpe")), "notes": notes if i == start + 1 else ""})
    store.append_csv(config.WORKOUTS_FILE, WORKOUT_FIELDS, rows)
    return rows


def log_body(day: date, weight_kg=None, waist_cm=None, bodyfat_pct=None, notes: str = "") -> dict:
    row = {"date": day.isoformat(), "weight_kg": _num(weight_kg), "waist_cm": _num(waist_cm),
           "bodyfat_pct": _num(bodyfat_pct), "notes": notes}
    store.append_csv(config.BODY_FILE, BODY_FIELDS, [row])
    return row


def sessions(exercise: str) -> list[dict]:
    """Per-day summary for one exercise: top set, best e1RM and volume."""
    by_day = defaultdict(list)
    for r in store.read_csv(config.WORKOUTS_FILE):
        if r["exercise"].lower() == exercise.lower():
            by_day[r["date"]].append(r)
    out = []
    for day in sorted(by_day):
        rows = by_day[day]
        sets = [(float(r["weight_kg"] or 0), int(r["reps"] or 0)) for r in rows]
        top = max(sets, key=lambda s: (s[0], s[1]))
        best = max(e1rm(w, n) for w, n in sets)
        out.append({"date": day, "sets": len(sets), "top_set": f"{_num(top[0])}x{top[1]}",
                    "e1rm": round(best, 1), "volume": round(sum(w * n for w, n in sets))})
    return out


def progress_report(exercise: str, last: int = 6) -> str:
    rows = sessions(exercise)
    if not rows:
        return f"No sets logged for {exercise} yet."
    lines = [f"**{normalise_exercise(exercise)}** — last {min(last, len(rows))} sessions"]
    for r in rows[-last:]:
        lines.append(f"• {r['date']}: top {r['top_set']}, e1RM {r['e1rm']} kg, "
                     f"{r['sets']} sets, volume {r['volume']} kg")
    if len(rows) >= 2:
        delta = rows[-1]["e1rm"] - rows[0]["e1rm"]
        lines.append(f"Since {rows[0]['date']}: e1RM {'+' if delta >= 0 else ''}{round(delta, 1)} kg")
    return "\n".join(lines)


def personal_records() -> list[dict]:
    best: dict[str, dict] = {}
    for r in store.read_csv(config.WORKOUTS_FILE):
        w, n = float(r["weight_kg"] or 0), int(r["reps"] or 0)
        score = e1rm(w, n)
        key = r["exercise"]
        if key not in best or score > best[key]["e1rm"]:
            best[key] = {"exercise": key, "date": r["date"], "set": f"{_num(w)}x{n}", "e1rm": round(score, 1)}
    return sorted(best.values(), key=lambda b: b["exercise"])


def last_session_day() -> str | None:
    rows = store.read_csv(config.WORKOUTS_FILE)
    return max((r["date"] for r in rows), default=None)


def body_trend(last: int = 5) -> str:
    rows = [r for r in store.read_csv(config.BODY_FILE) if r.get("weight_kg")]
    if not rows:
        return "No body-weight entries yet."
    rows = rows[-last:]
    text = ", ".join(f"{r['date'][5:]}: {r['weight_kg']} kg" for r in rows)
    if len(rows) >= 2:
        delta = float(rows[-1]["weight_kg"]) - float(rows[0]["weight_kg"])
        text += f" ({'+' if delta >= 0 else ''}{delta:.1f} kg)"
    return text
