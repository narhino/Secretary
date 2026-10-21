---
name: checkin
description: Proactive or on-demand check-in (morning, midday, evening, or ad hoc). Use when a scheduled task says "check-in: <kind>", or when the user says good morning / good night / "check in" / "plan my day" / "how did today go".
---

# Check-in

1. `git pull --quiet`. Read `memory/playbook.md` (how this person likes to be treated) and run
   `python -m secretary status --json`.
2. Decide if a message is worth sending. Skip it (record it as done) if this check-in already went
   out today, if it's inside `quiet_hours` and nothing critical is due, or if you talked in the
   last ~2 hours and nothing new needs saying. Proactive messages per day must stay under
   `max_proactive_per_day` (critical reminders excepted).
3. Write ONE natural message in the voice from CLAUDE.md. It's a text from a friend who runs their
   life, not a report.
   - **morning:** what today holds (appointments, gym day, the one priority), plus one easy question.
   - **midday:** only if lunch isn't logged: a light ask for what they ate (a photo works).
   - **evening:** how was today? Gather whatever is missing from `daylog_missing_today` and the
     meals not yet logged, over the conversation, not as a questionnaire. Close with a one-line
     nutrition read and tomorrow's priority.
   - Fold `due_reminders` in naturally, then `python -m secretary mark-sent <key> <covers…>`.
   - If something has an exact time later today (e.g. orthodontist 15:00 with a 3h lead), schedule
     a one-shot message for that minute if you can (send_later / one-shot task); the safety net
     covers critical ones if you can't.
4. Deliver it: in a scheduled run your reply IS the message (the user gets a push notification).
   If the Discord webhook is configured and allowed, also post it there.
5. As they answer: log everything (meals, `day set`, workouts, tasks, reminders), update profile
   and playbook facts, reply like a person.
6. `python -m secretary checkin-done <kind>`, then commit and push.
