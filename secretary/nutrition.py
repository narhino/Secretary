"""Meal log (nutrition/meals.csv) and the per-day totals sheet (nutrition/daily.csv)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from . import config, store

NUTRIENTS = ["kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"]
MEAL_FIELDS = ["date", "time", "meal", "food", "amount", *NUTRIENTS, "source", "notes"]
DAILY_FIELDS = ["date", "meals_logged", *NUTRIENTS, "target_kcal", "target_protein_g",
                "kcal_pct", "protein_pct", "on_target"]
MEALS = ["breakfast", "lunch", "dinner", "snack", "drink", "pre-workout", "post-workout"]


def meals_file():
    return config.ROOT / "nutrition" / "meals.csv"


def daily_file():
    return config.ROOT / "nutrition" / "daily.csv"


def load_foods() -> list[dict]:
    data = store.load_yaml(config.ROOT / "nutrition" / "foods.yaml", {}) or {}
    return list(data.get("foods") or [])


def find_food(query: str) -> dict:
    q = query.strip().lower()
    foods = load_foods()
    for f in foods:
        names = [f["id"], f["name"].lower(), *[a.lower() for a in f.get("aliases", [])]]
        if q in names:
            return f
    hits = [f for f in foods if q in f["id"] or q in f["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise KeyError(f"{query!r} matches several foods: {', '.join(h['id'] for h in hits)}")
    raise KeyError(f"no reference food {query!r}; give the nutrients instead")


def load_targets() -> dict:
    return store.load_yaml(config.ROOT / "nutrition" / "targets.yaml", {}) or {}


def _num(value):
    if value in (None, ""):
        return ""
    value = round(float(value), 1)
    return int(value) if value.is_integer() else value


def log_meal(day: date, food: str, meal: str = "", time: str = "", amount: str = "",
             nutrients: dict | None = None, ref: str | None = None, qty: float = 1.0,
             source: str = "", notes: str = "") -> dict:
    """Append one food. With `ref`, nutrients come from foods.yaml x qty (explicit ones win)."""
    values = {}
    if ref:
        f = find_food(ref)
        values = {k: (f.get(k) or 0) * qty for k in NUTRIENTS if f.get(k) is not None}
        food = food or f["name"]
        amount = amount or (f["serving"] if qty == 1 else f"{_num(qty)} x {f['serving']}")
        source = source or "reference"
    values.update({k: v for k, v in (nutrients or {}).items() if k in NUTRIENTS and v not in (None, "")})
    if "kcal" not in values:
        raise ValueError("need at least kcal (estimate it) or a reference food")
    if meal and meal not in MEALS:
        raise ValueError(f"meal must be one of {MEALS}")
    row = {"date": day.isoformat(), "time": time, "meal": meal, "food": food, "amount": amount,
           **{k: _num(values.get(k)) for k in NUTRIENTS}, "source": source or "estimate", "notes": notes}
    store.append_csv(meals_file(), MEAL_FIELDS, [row])
    rebuild_daily()
    return row


def meals_on(day: date) -> list[dict]:
    return [r for r in store.read_csv(meals_file()) if r["date"] == day.isoformat()]


def totals(rows: list[dict]) -> dict:
    out = {k: 0.0 for k in NUTRIENTS}
    for r in rows:
        for k in NUTRIENTS:
            if r.get(k) not in (None, ""):
                out[k] += float(r[k])
    return {k: round(v, 1) for k, v in out.items()}


def on_target(day_totals: dict, targets: dict) -> bool | None:
    kcal_t, prot_t = targets.get("kcal"), targets.get("protein_g")
    if not kcal_t or not prot_t:
        return None
    return abs(day_totals["kcal"] - kcal_t) <= 0.1 * kcal_t and day_totals["protein_g"] >= 0.9 * prot_t


def rebuild_daily() -> list[dict]:
    """Regenerate nutrition/daily.csv: one row per day with totals vs targets."""
    by_day = defaultdict(list)
    for r in store.read_csv(meals_file()):
        by_day[r["date"]].append(r)
    targets = load_targets()
    rows = []
    for day in sorted(by_day):
        t = totals(by_day[day])
        hit = on_target(t, targets)
        rows.append({
            "date": day, "meals_logged": len(by_day[day]), **{k: _num(v) for k, v in t.items()},
            "target_kcal": targets.get("kcal") or "", "target_protein_g": targets.get("protein_g") or "",
            "kcal_pct": round(100 * t["kcal"] / targets["kcal"]) if targets.get("kcal") else "",
            "protein_pct": round(100 * t["protein_g"] / targets["protein_g"]) if targets.get("protein_g") else "",
            "on_target": "" if hit is None else ("yes" if hit else "no"),
        })
    path = daily_file()
    if path.exists():
        path.unlink()
    store.append_csv(path, DAILY_FIELDS, rows)
    return rows


def day_report(day: date) -> str:
    rows = meals_on(day)
    if not rows:
        return f"No meals logged for {day}."
    t = totals(rows)
    targets = load_targets()
    lines = [f"{day:%a %d %b}: {len(rows)} item(s)"]
    for r in rows:
        lines.append(f"• {r['time'] or r['meal'] or '-'}: {r['food']} — {r['kcal']} kcal, {r['protein_g'] or 0} g protein")
    summary = f"Total {t['kcal']:.0f} kcal · P {t['protein_g']:.0f} g · C {t['carbs_g']:.0f} g · F {t['fat_g']:.0f} g"
    if t["fiber_g"]:
        summary += f" · fibre {t['fiber_g']:.0f} g"
    lines.append(summary)
    if targets.get("kcal") and targets.get("protein_g"):
        lines.append(f"vs target: {t['kcal'] - targets['kcal']:+.0f} kcal, "
                     f"{t['protein_g'] - targets['protein_g']:+.0f} g protein")
    return "\n".join(lines)


def week_stats(end: date, days: int = 7) -> dict:
    start = end - timedelta(days=days - 1)
    rows = [r for r in store.read_csv(daily_file()) if start.isoformat() <= r["date"] <= end.isoformat()]
    if not rows:
        return {"days_logged": 0}
    n = len(rows)
    avg = {k: round(sum(float(r[k] or 0) for r in rows) / n, 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}
    return {"days_logged": n, "avg": avg,
            "days_on_target": sum(1 for r in rows if r["on_target"] == "yes"),
            "targets_set": bool(load_targets().get("kcal"))}
