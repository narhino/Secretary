---
name: checkin
description: Daily check-in with the user. In the morning, plan the day; in the evening, review it. Use when the user says good morning / good night / "check in" / "plan my day" / "how did today go".
---

# Daily check-in

**Morning (before ~14:00 local):**
1. Run `python -m secretary brief`. Read `goals/goals.md` → *This week*.
2. Propose the day's top 3 (tie them to the weekly focus) plus the training session if it's a gym day.
3. Flag anything in the next 7 days that needs prep today (documents, bookings, shopping).
4. Ask one question at most, then update tasks and reminders from the answer.

**Evening:**
1. Ask what got done. Mark tasks done, and log any sets or body weight given (`python -m secretary log …`).
2. Note protein / meal plan adherence and sleep target in `journal/YYYY-MM-DD.md` (template in
   `journal/README.md`).
3. Agree tomorrow's top priority. Move unfinished tasks to new due dates instead of leaving them
   overdue.
4. Be honest and encouraging: name streaks and wins, call out patterns (e.g. third skipped leg day).

Finish by committing and pushing changes.
