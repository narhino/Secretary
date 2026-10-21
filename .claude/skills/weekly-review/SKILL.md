---
name: weekly-review
description: Sunday weekly review and strategy session. Turns the week's data (training, nutrition, mood, sleep, studio, tasks, appointments) into wins, lessons and 2-3 concrete strategies for next week, and updates goals, targets, routines and the playbook. Use when a scheduled task says "check-in: weekly" or the user asks for a review.
---

# Weekly review & strategy

1. `git pull --quiet`. Gather: `python -m secretary week --json`, `data/daily.csv` (last 7–14 days),
   `nutrition/daily.csv`, `python -m secretary prs`, `memory/playbook.md` (current experiments),
   `goals/goals.md`, and `python -m secretary upcoming --days 21`.
2. Find the story in the data. Look for correlations, not just totals: sleep vs mood, training days
   vs energy, weekends vs nutrition, studio "messy" streaks vs busy days, missed sessions vs
   late work. Check each running experiment against its success criteria.
3. Open the conversation like a coach. Start with one real win, then the main thing that held them
   back. Keep the message short and end with one question. Go deeper as they reply. Cover
   training (sessions vs target, PRs, progress toward `fitness/targets.yaml`), nutrition (days on
   target, average protein), mind (mood/energy/stress/sleep), home (studio and routines),
   priorities and upcoming appointments.
4. Agree on **2–3 specific strategies** for next week. Small, measurable, tied to a pattern.
   Example: "on late-work days, train at 7:00 instead of 19:00"; "prep 2 extra chicken boxes for
   Wed–Thu"; "10-min reset before Netflix".
5. Apply the changes. Update *This week* and the key-result statuses in `goals/goals.md`; adjust
   `nutrition/targets.yaml` (e.g. a 2-week weight stall on a cut → −150–200 kcal), `fitness/program.md`,
   routines, reminders and check-in times if the data says so. Plan meal prep in
   `nutrition/meal-prep.md`. Add the experiments, observed patterns and a change-log line to
   `memory/playbook.md`. Write `journal/YYYY-Www-review.md`.
6. Commit and push.
