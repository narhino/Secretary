---
name: weekly-review
description: Sunday weekly review — wins, misses, training and nutrition stats, Thai admin status, next week's top 3, and updating goals.md. Use when the user asks for a weekly review or on Sundays.
---

# Weekly review

1. Gather facts: tasks completed in the last 7 days (`data/tasks.yaml`), workouts
   (`fitness/workouts.csv`: sessions, PRs, e1RM trends via `python -m secretary progress`), body
   weight trend (`fitness/body.csv`), journal notes, and `python -m secretary upcoming --days 21`.
2. Present a short scorecard: sessions done vs planned, PRs, weight trend, tasks done/overdue,
   upcoming deadlines (especially immigration).
3. Ask the five review questions from the weekly reminder (win/miss, training, nutrition, Thai admin,
   next week's top 3). Keep it conversational.
4. Write `journal/YYYY-Www-review.md`, replace *This week* in `goals/goals.md`, update Q4 key result
   statuses, reschedule stale tasks, and adjust the program or calorie targets if the data says so
   (e.g. 2 weeks of no weight change on a cut → −150–200 kcal).
5. Plan meal prep for the week in `nutrition/meal-prep.md`.
6. Commit and push.
