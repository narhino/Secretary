---
name: onboarding
description: Run or continue the intake interview that teaches the secretary who the user is (basics, visa status, fitness, nutrition, goals, preferences) and files the answers. Use when profile/me.md has TODOs or the user says "onboard me" / "get to know me".
---

# Onboarding interview

1. Read `profile/me.md`, `goals/goals.md` and `ONBOARDING.md`. List which TODO fields are still open.
2. Ask in rounds of 3–5 questions, in this priority order: visa and immigration dates (time-critical),
   then basics and routine, fitness, nutrition, goals, how to work together. Offer options where
   possible and accept "skip".
3. After each answer, **immediately**:
   - fill `profile/me.md` (replace the TODO; never store passport numbers or bank details)
   - create reminders for every date learned (visa expiry `[60d,30d,14d,7d,1d]`, 90-day report
     `every 90d` with `[15d,7d,2d,0m]`, gym days as `weekly:<days>`)
   - create tasks for pending admin (TM.30 receipt, residence certificate, licence steps…)
   - update `data/settings.yaml` (brief time ≈ 30 min after wake-up, evening check-in on/off,
     Discord user ID)
4. Once fitness and nutrition answers are in, rewrite `fitness/program.md` and `nutrition/targets.md`
   for them (show the maths for calories and macros) and draft this week in `nutrition/meal-prep.md`.
5. Once goals are in, fill `goals/goals.md` (vision → year → Q4 key results → This week).
6. Run `python -m secretary validate`, summarise what was set up in 5–8 lines, commit and push.
