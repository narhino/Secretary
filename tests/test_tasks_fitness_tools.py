from datetime import date

import pytest

from secretary import cli, config, fitness, tasks
from secretary.bot import tools


def test_tasks_add_update_list(home):
    today = date(2026, 10, 21)
    t1 = tasks.add_task("Get residence certificate", today, due="2026-10-30", priority="high", area="thailand")
    t2 = tasks.add_task("Buy groceries", today, due="2026-10-19")
    assert (t1["id"], t2["id"]) == ("t-0001", "t-0002")
    assert [t["id"] for t in tasks.open_tasks()] == ["t-0002", "t-0001"]
    assert "overdue" in tasks.format_task(t2, today)
    done = tasks.update_task("t-0002", today, status="done")
    assert done["completed"] == "2026-10-21"
    assert [t["id"] for t in tasks.open_tasks()] == ["t-0001"]
    with pytest.raises(ValueError):
        tasks.update_task("t-0001", today, status="finished")


def test_fitness_parse_log_progress(home):
    assert fitness.parse_set("80x8@8.5") == {"weight_kg": 80.0, "reps": 8, "rpe": 8.5}
    assert fitness.parse_set("77.5 × 7") == {"weight_kg": 77.5, "reps": 7, "rpe": None}
    with pytest.raises(ValueError):
        fitness.parse_set("eighty for eight")
    assert round(fitness.e1rm(100, 5), 1) == 116.7
    fitness.log_sets("bench press", [{"weight_kg": 80, "reps": 8}, {"weight_kg": 80, "reps": 7}], date(2026, 10, 14))
    fitness.log_sets("Bench Press", [{"weight_kg": 82.5, "reps": 8}], date(2026, 10, 21))
    fitness.log_sets("Bench Press", [{"weight_kg": 82.5, "reps": 7}], date(2026, 10, 21))
    sessions = fitness.sessions("bench press")
    assert [s["date"] for s in sessions] == ["2026-10-14", "2026-10-21"]
    assert sessions[1]["sets"] == 2 and sessions[1]["top_set"] == "82.5x8"
    assert "e1RM +" in fitness.progress_report("Bench Press")
    assert fitness.personal_records()[0]["set"] == "82.5x8"
    assert fitness.last_session_day() == "2026-10-21"


def test_cli_roundtrip(home, capsys):
    assert cli.main(["remind", "add", "Visa extension", "--due", "2026-11-20", "--before", "14d,0m"]) == 0
    assert cli.main(["task", "add", "Medical certificate", "--priority", "high"]) == 0
    assert cli.main(["log", "Squat", "100x5", "100x5", "--rpe", "8"]) == 0
    assert cli.main(["validate"]) == 0
    assert cli.main(["upcoming", "--days", "60"]) == 0
    out = capsys.readouterr().out
    assert "visa-extension" in out and "ok" in out
    assert cli.main(["remind", "done", "nope"]) == 2


def test_tool_paths_are_sandboxed(home):
    (config.ROOT / ".env").write_text("SECRET=1")
    with pytest.raises(tools.ToolError):
        tools.run("read_file", {"path": ".env"})
    with pytest.raises(tools.ToolError):
        tools.run("read_file", {"path": "../outside.txt"})
    with pytest.raises(tools.ToolError):
        tools.run("write_file", {"path": "secretary/evil.py", "content": "x"})
    with pytest.raises(tools.ToolError):
        tools.run("write_file", {"path": "profile/me.sh", "content": "x"})
    out, wrote = tools.run("write_file", {"path": "journal/2026-10-21.md", "content": "# Day\n"})
    assert wrote and (config.ROOT / "journal/2026-10-21.md").exists()
    tools.run("append_file", {"path": "journal/2026-10-21.md", "text": "- trained legs"})
    assert (config.ROOT / "journal/2026-10-21.md").read_text() == "# Day\n- trained legs\n"


def test_invalid_reminder_write_is_rolled_back(home):
    tools.run("add_reminder", {"title": "Rent", "due": "2026-11-01", "repeat": "monthly"})
    before = config.REMINDERS_FILE.read_text()
    with pytest.raises(tools.ToolError):
        tools.run("write_file", {"path": "data/reminders.yaml",
                                 "content": "reminders:\n- id: x\n  title: X\n  repeat: sometimes\n"})
    assert config.REMINDERS_FILE.read_text() == before
    with pytest.raises(tools.ToolError):
        tools.run("edit_file", {"path": "data/reminders.yaml", "old_text": "nothing-like-this", "new_text": "y"})


def test_tool_reminder_and_workout_flow(home):
    out, wrote = tools.run("add_reminder", {"title": "90-day report", "due": "2026-12-01", "time": "09:00",
                                            "repeat": "every 90d", "notify_before": ["14d", "3d", "0m"],
                                            "category": "immigration"})
    assert wrote and "90-day-report" in out
    listing, _ = tools.run("list_reminders", {"days": 60})
    assert "90-day-report" in listing
    out, _ = tools.run("complete_reminder", {"id": "90-day-report", "next_due": "2027-03-01"})
    assert "2027-03-01" in out
    out, wrote = tools.run("log_workout", {"exercise": "deadlift", "sets": [{"weight_kg": 140, "reps": 5}]})
    assert wrote and "Deadlift" in out
    out, _ = tools.run("exercise_progress", {})
    assert "Deadlift" in out
    out, _ = tools.run("add_task", {"title": "Book DLT appointment", "priority": "high", "area": "thailand"})
    assert "t-0001" in out
    out, _ = tools.run("update_task", {"id": "t-0001", "status": "waiting", "waiting_on": "landlord TM30"})
    assert "waiting" in out


def test_tool_schemas_are_well_formed():
    names = [t["name"] for t in tools.TOOLS]
    assert len(names) == len(set(names))
    for t in tools.TOOLS:
        assert t["input_schema"]["type"] == "object"
        for req in t["input_schema"]["required"]:
            assert req in t["input_schema"]["properties"]


def test_env_file_parsing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("A=one   # comment\nB=\nC='quoted # kept'\n# D=skip\nE=x#y\n")
    for key in "ABCDE":
        monkeypatch.delenv(key, raising=False)
    config.load_env_file(env)
    import os
    assert os.environ["A"] == "one"
    assert "B" not in os.environ and "D" not in os.environ
    assert os.environ["C"] == "quoted # kept"
    assert os.environ["E"] == "x#y"
