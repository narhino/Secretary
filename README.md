# Secretary

A personal secretary and coach that runs on Claude (your subscription). It keeps track of goals,
priorities, tasks and appointments (orthodontist, immigration…); logs what you eat into a daily
nutrition sheet; tracks training, mood, sleep and the state of your studio; and turns all of it
into weekly strategies. It talks like a person: Claude writes every message itself, with no
templates.

## How it fits together
```
                 ┌──────────── this private repo = the secretary's memory ────────────┐
                 │ CLAUDE.md (voice + rules)   memory/playbook.md (self-updating)     │
                 │ profile/ goals/ data/(tasks, reminders, daily.csv) home/           │
                 │ nutrition/(meals.csv → daily.csv sheet) fitness/ thailand/ journal/│
                 └─────▲─────────────────────▲─────────────────────────▲──────────────┘
                       │                     │                         │ critical only,
        ┌──────────────┴─────────┐ ┌─────────┴───────────────┐ ┌───────┴─────────────────┐
        │ Claude app + scheduled │ │ Discord (optional):     │ │ Safety net: GitHub       │
        │ check-ins (cloud, your │ │ Claude Code + Discord   │ │ Actions → Discord webhook│
        │ subscription)          │ │ plugin on an always-on  │ │ if Claude didn't deliver │
        └────────────────────────┘ │ computer                │ └──────────────────────────┘
                                   └─────────────────────────┘
```
Read [`docs/setup.md`](docs/setup.md) for the design and setup (Plan A: no server; Plan B: Discord).

## What gets tracked
| You say / send | Lands in |
|---|---|
| What you ate (text or photo) | `nutrition/meals.csv` → per-day totals vs targets in `nutrition/daily.csv` |
| Mood, energy, stress, sleep, studio state, priorities | `data/daily.csv` |
| Sets and reps, body weight | `fitness/workouts.csv`, `fitness/body.csv`, progress vs `fitness/targets.yaml` |
| Appointments, deadlines, to-dos | `data/reminders.yaml`, `data/tasks.yaml` |
| Anything about you | `profile/me.md`, `memory/playbook.md` |

## Start here
1. Make this repository **private** (Settings → General → Danger Zone → Change visibility).
2. Answer the questions in [`ONBOARDING.md`](ONBOARDING.md), or say "onboard me".
3. Pick the check-in times; the secretary schedules them.

## Command line (used by Claude; handy for you too)
```bash
pip install -e ".[dev]"
python -m secretary status --json        # situation report
python -m secretary meal add --ref khao-man-gai --meal lunch ; python -m secretary meal today
python -m secretary day set --mood 7 --energy 6 --sleep-h 7.5 --tidy ok
python -m secretary log "Squat" 100x5 100x5 100x5@8 ; python -m secretary prs
python -m secretary week                  # weekly review numbers
python -m secretary remind add "Orthodontist" --due 2026-11-04 --time 15:00 --category appointment --before 1d,3h
python -m secretary validate && python -m pytest -q
```

## Privacy
Keep the repository private. Never store passport numbers, bank details or passwords. Secrets
(webhook URL, tokens) go in GitHub secrets or `.env`, never in commits.
