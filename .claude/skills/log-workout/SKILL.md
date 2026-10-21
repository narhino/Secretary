---
name: log-workout
description: Log a gym session from free text (e.g. "bench 80x8 80x8 77.5x7, rows 60x10x3") and give progress feedback. Use whenever the user reports sets, reps, weights or a workout.
---

# Log a workout

1. Parse each exercise into sets of WEIGHTxREPS[@RPE]. Expand shorthand such as `60x10x3` (3 sets of
   10 at 60 kg) or `bodyweight` (weight 0). Use canonical names ("Bench Press", "Barbell Row",
   "Squat") that match past entries in `fitness/workouts.csv`.
2. Log with `python -m secretary log "<Exercise>" 80x8 80x8 77.5x7@9 [--date YYYY-MM-DD]`.
3. Run `python -m secretary progress "<Exercise>" --last 4` for the main lifts and reply with:
   - PRs (new best e1RM or rep PR) 🎉
   - what to do next time per `fitness/program.md` progression rules (e.g. "all sets hit 8 → 82.5 kg")
   - one line on recovery or nutrition if it is relevant (protein, sleep, heat)
4. If body weight was mentioned, log it with `python -m secretary body --weight …`.
5. Commit and push.
