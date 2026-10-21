import json
from datetime import date

import pytest
import yaml

from secretary import cli, config, daylog, nutrition, status


def _targets(home, **values):
    (home / "nutrition").mkdir(exist_ok=True)
    (home / "nutrition" / "targets.yaml").write_text(yaml.safe_dump(values))


def _foods(home):
    import shutil
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "nutrition" / "foods.yaml"
    (home / "nutrition").mkdir(exist_ok=True)
    shutil.copy(src, home / "nutrition" / "foods.yaml")


def test_meal_logging_and_daily_sheet(home):
    _foods(home)
    _targets(home, kcal=2200, protein_g=160)
    day = date(2026, 10, 21)
    nutrition.log_meal(day, "", "lunch", "12:30", ref="khao-man-gai")
    nutrition.log_meal(day, "", "snack", ref="boiled egg", qty=2)
    nutrition.log_meal(day, "Salmon poke bowl", "dinner", nutrients={"kcal": 650, "protein_g": 35, "carbs_g": 70,
                                                                     "fat_g": 22})
    t = nutrition.totals(nutrition.meals_on(day))
    assert t["kcal"] == 1394.0 and t["protein_g"] == 77.6
    sheet = nutrition.rebuild_daily()
    assert sheet[0]["date"] == "2026-10-21" and sheet[0]["meals_logged"] == 3
    assert sheet[0]["kcal_pct"] == 63 and sheet[0]["on_target"] == "no"
    assert "vs target" in nutrition.day_report(day)
    with pytest.raises(KeyError):
        nutrition.find_food("rice")          # ambiguous: jasmine / riceberry / sticky / mango...
    with pytest.raises(ValueError):
        nutrition.log_meal(day, "mystery", nutrients={})


def test_daylog_upsert_and_validation(home):
    day = date(2026, 10, 21)
    daylog.update(day, mood=7, energy=6, sleep_h=7.25)
    row = daylog.update(day, tidy="messy", training="push day", trained="yes")
    row = daylog.update(day, training="10 min walk")
    assert row["mood"] == "7" and row["sleep_h"] == "7.2" and row["tidy"] == "messy"
    assert row["training"] == "push day; 10 min walk"
    assert daylog.missing_today(day) == []
    assert len(daylog.load()) == 1
    with pytest.raises(ValueError):
        daylog.update(day, mood=11)
    with pytest.raises(ValueError):
        daylog.update(day, tidy="disaster")
    stats = daylog.week_stats(day)
    assert stats["trained_days"] == 1 and stats["tidy"]["messy"] == 1


def test_status_snapshot_and_week(home, capsys):
    _foods(home)
    day = date(2026, 10, 21)
    cli.main(["remind", "add", "Orthodontist", "--due", "2026-10-21", "--time", "15:00",
              "--category", "appointment", "--before", "3h"])
    cli.main(["meal", "add", "--ref", "pad-krapow-gai", "--meal", "lunch"])
    cli.main(["day", "set", "--mood", "6", "--tidy", "ok"])
    cli.main(["log", "Bench Press", "80x8", "80x8"])
    capsys.readouterr()
    snap = status.snapshot()
    assert snap["part_of_day"] == "morning"
    assert snap["today"][0]["title"] == "Orthodontist" and snap["today"][0]["category"] == "appointment"
    assert snap["nutrition_today"]["meals_logged"] == ["lunch"]
    assert "energy" in snap["daylog_missing_today"] and "mood" not in snap["daylog_missing_today"]
    assert snap["training"]["sessions_this_week"] == 1 and snap["daylog_today"]["trained"] == "yes"
    assert cli.main(["status", "--json"]) == 0
    json.loads(capsys.readouterr().out)
    w = status.weekly(day)
    assert w["training"]["sessions"] == 1 and w["nutrition"]["days_logged"] == 1
    assert "Training: 1 sessions" in status.format_weekly(w)


def test_checkin_done_and_due_marking(home, capsys, monkeypatch):
    monkeypatch.setenv("SECRETARY_NOW", "2026-10-21T12:05")
    cli.main(["remind", "add", "Orthodontist", "--due", "2026-10-21", "--time", "15:00", "--before", "3h"])
    capsys.readouterr()
    assert cli.main(["due", "--json"]) == 0
    items = json.loads(capsys.readouterr().out)
    assert [i["id"] for i in items] == ["orthodontist"]
    cli.main(["mark-sent", *items[0]["covers"]])
    cli.main(["checkin-done", "midday"])
    capsys.readouterr()
    cli.main(["due", "--json"])
    assert json.loads(capsys.readouterr().out) == []
    assert status.snapshot()["checkins_already_sent_today"] == ["midday"]


def test_fitness_goals_progress(home):
    from secretary import fitness
    (home / "fitness").mkdir(exist_ok=True)
    (home / "fitness" / "targets.yaml").write_text(yaml.safe_dump({
        "sessions_per_week": 4,
        "goals": [{"name": "Bench 100", "metric": "e1rm", "exercise": "Bench Press", "target": 100, "by": "2026-12-31"},
                  {"name": "75 kg", "metric": "body_weight", "target": 75}]}))
    fitness.log_sets("Bench Press", [{"weight_kg": 80, "reps": 8}], date(2026, 10, 20))
    fitness.log_body(date(2026, 10, 20), 79.5)
    goals = {g["name"]: g for g in fitness.goal_progress(date(2026, 10, 21))}
    assert goals["Bench 100"]["current"] == 101.3 and goals["Bench 100"]["days_left"] == 71
    assert goals["75 kg"]["remaining"] == -4.5
    assert config.load_settings()["checkins"]["evening"] == "21:00"
