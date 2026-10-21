---
name: onboarding
description: Run or continue the intake interview that teaches the secretary who the user is (basics, visa status, fitness, nutrition, goals, preferences) and files the answers. Use when profile/me.md has TODOs or the user says "onboard me" / "get to know me".
---

# Onboarding interview

1. Read `profile/me.md`, `goals/goals.md` and `ONBOARDING.md`. List which TODO fields are still open.
2. Make it a conversation, not a form: 2–3 questions at a time, in this order: visa and
   immigration dates, orthodontic treatment and next appointment (both time-critical), then basics
   and daily routine (wake time sets the check-in times), fitness, nutrition, home and living alone,
   wellbeing, goals, and how they want you to talk to them. Accept "skip". Spread it over several
   days if they're busy.
3. After each answer, **immediately**:
   - fill `profile/me.md` (replace the TODO; never store passport numbers or bank details)
   - create reminders for every date learned (visa expiry `[60d,30d,14d,7d,1d]`, 90-day report
     `every 90d` with `[15d,7d,2d,0m]`, gym days as `weekly:<days>`)
   - create tasks for pending admin (TM.30 receipt, residence certificate, licence steps…)
   - orthodontist: appointments as `--category appointment --critical --before 1d,3h`; aligner
     changes / elastics routines as repeating reminders
   - update `data/settings.yaml` → `checkins` (morning ≈ 30 min after waking, evening ≈ 1–2 h
     before bed), quiet hours, Discord user ID
   - write how they like to be talked to into `memory/playbook.md`
4. Once fitness and nutrition answers are in, rewrite `fitness/program.md`, set
   `fitness/targets.yaml` (sessions per week + 2–3 measurable goals) and `nutrition/targets.yaml`
   (show the maths for calories and macros), and draft this week in `nutrition/meal-prep.md`.
5. Once goals are in, fill `goals/goals.md` (vision → year → Q4 key results → This week).
6. Run `python -m secretary validate`, summarise what was set up in 5–8 lines, commit and push.
