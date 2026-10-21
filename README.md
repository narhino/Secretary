# Secretary

A personal secretary built on Claude. It keeps track of goals, tasks and appointments, tracks gym
progress and meal prep, handles life admin in Thailand (visa, 90-day reports, driving licence) and
reminds you before things are due. You can talk to it **in the Claude app** and **on Discord**.

## How it fits together
```
                ┌──────────────── this git repo = the secretary's memory ────────────────┐
                │ CLAUDE.md (how it behaves)  profile/  goals/  data/*.yaml  fitness/    │
                │ nutrition/  thailand/  journal/  memory/                               │
                └───────▲──────────────────────▲─────────────────────────▲───────────────┘
                        │ read/write + push    │ read/write + push       │ read + sent-log
         ┌──────────────┴───────┐  ┌───────────┴──────────────┐  ┌───────┴───────────────────┐
         │ Claude app / Claude  │  │ Discord bot              │  │ GitHub Actions (cron)     │
         │ Code (this chat)     │  │ secretary/bot, Claude API│  │ reminders via webhook     │
         └──────────────────────┘  │ DMs you, reads photos    │  └───────────────────────────┘
                                   └──────────────────────────┘
```
- **One memory.** Every surface reads and writes the same files and syncs through git. Tell the bot
  something on Discord and the Claude app knows it next time, and the other way round.
- **Reliable reminders.** Reminders are plain code, not AI: `data/reminders.yaml` + `secretary/reminders.py`.
  They fire through the bot (as DMs) or through GitHub Actions (webhook). A sent-log stops repeats.
- **Morning brief, evening check-in, weekly review.** These are built in; set the times in
  `data/settings.yaml`.

## Start here
1. Answer the questions in [`ONBOARDING.md`](ONBOARDING.md), or just tell the secretary "onboard me".
2. Set up Discord: [`docs/discord-setup.md`](docs/discord-setup.md). Layer 1 takes about 10 minutes
   and needs no server.
3. Talk to it every day: "plan my day", "bench 80x8 80x8", "remind me to…", "weekly review".

## Command line
```bash
pip install -e ".[bot,dev]"
python -m secretary brief                 # today's brief
python -m secretary upcoming --days 30
python -m secretary remind add "Visa extension" --due 2026-12-01 --time 09:00 --before 30d,14d,7d,1d
python -m secretary task add "Get residence certificate" --priority high --area thailand
python -m secretary log "Squat" 100x5 100x5 100x5@8
python -m secretary progress "Squat" ; python -m secretary prs
python -m secretary validate && python -m pytest -q
python -m secretary.bot                   # run the Discord bot (needs .env)
```

## Privacy
Keep this repository **private**. Don't store passport numbers, bank details or passwords here.
Secrets (bot token, API key, webhook URL) go in `.env` or GitHub secrets, never in commits.
