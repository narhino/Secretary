---
name: log-meal
description: Log food and drinks from text or a photo into the nutrition sheet, and give a one-line read of the day. Use whenever the user mentions eating or drinking something, sends a food photo, or asks how their nutrition looks.
---

# Log a meal

1. Split what they ate into items. For each one:
   - If it matches `nutrition/foods.yaml` (see `python -m secretary meal foods`), log with
     `--ref <id> [--qty N]`.
   - Otherwise estimate kcal, protein, carbs, fat (and fibre/sugar/sodium if you reasonably can)
     from the description or photo: portion size, cooking oil, sauces, sugar in drinks. Use
     `--source photo|label|estimate`. A packet label beats any estimate.
   - Add `--meal breakfast|lunch|dinner|snack|drink|pre-workout|post-workout` and `--time HH:MM`.
   - If they eat something repeatedly, add it to `foods.yaml` so future logs are consistent.
2. `python -m secretary meal add ...` for each item (this also refreshes `nutrition/daily.csv`,
   the per-day sheet).
3. Reply in one or two human lines: what you logged ("~650 kcal, 32 g protein") and something useful,
   e.g. protein left for the day, a swap idea for next time, or a reminder that dinner can be
   lighter. No tables unless they ask.
4. Ask about portions only if the guess could be off by more than ~30% and it matters for their
   goal.
5. Commit and push.
