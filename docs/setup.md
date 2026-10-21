# How your secretary runs on your Claude subscription

## The principles
1. **One memory, many doors.** This private repo is the single source of truth. The Claude app,
   scheduled check-ins and Discord all read and write the same files, so a conversation can start
   in one place and continue in another.
2. **Claude writes every word.** Code only keeps time and stores data. Every message you get is
   written fresh by Claude with your latest data, playbook and mood in view, so nothing comes
   from a template.
3. **The conversation is the interface.** You talk normally ("had khao man gai, slept badly,
   studio's a mess"), and Claude files meals, mood, sleep, training and chores into the sheets as
   it goes.
4. **A safety net for what can't be missed.** If Claude is ever unavailable, a small GitHub
   Actions job still delivers *critical* reminders (orthodontist, immigration, health) after a
   grace period. Nothing else ever comes from code.
5. **It evolves.** Every Sunday the review turns the data into strategies, then updates targets,
   program, routines, check-in times and `memory/playbook.md`.

## Plan A — the Claude app as home base (recommended start, no server)
Everything runs on Anthropic's cloud with your subscription:

| When | What happens |
|---|---|
| Morning (≈30 min after you wake) | A scheduled task starts a session, reads your data and writes your morning message. You get a push notification; tap it and reply in that thread. |
| Midday | A meal nudge, only if lunch isn't logged yet. |
| Evening | "How was today?": meals, mood, energy, training and studio gathered conversationally, then a one-line read of the day. |
| Sunday | Weekly review and strategy session. |
| Exact-time reminders | When an appointment is added, Claude schedules a one-shot message for the lead time (e.g. 3 h before the orthodontist). |
| Any time | Open the Secretary repo in the Claude app (claude.ai/code) and just talk. |

Limits to know: cloud scheduled tasks run at most hourly, and each run counts toward your plan's
usage. Four check-ins a day plus a few reminders is light. Each run starts a fresh thread, but
continuity comes from the repo (journal, daily log, playbook), so it still remembers yesterday.

**Optional: also post check-ins to Discord.** In the cloud environment's settings, allow the
domain `discord.com` under *Network access*, and add `DISCORD_WEBHOOK_URL` as an environment
variable. Check-ins then also land in your Discord channel. Replies on Discord need Plan B.

## Plan B — Discord as home (needs a computer that's always on)
Anthropic's official Discord plugin for Claude Code connects a running Claude Code session, logged
in with *your subscription*, to a Discord bot. You DM it like a contact. Same repo, same memory,
same voice.

Requirements: an always-on machine (home mini-PC/laptop or a small VPS), Claude Code v2.1.80+
logged in with your claude.ai Pro/Max account, [Bun](https://bun.sh), and a Discord bot (steps
below).
```bash
git clone git@github.com:narhino/Secretary.git && cd Secretary
claude
#   /plugin install discord@claude-plugins-official
#   /discord:configure <bot token>
# exit, then run inside tmux so it survives logout:
tmux new -s secretary 'claude --continue --channels plugin:discord@claude-plugins-official'
# DM the bot → it replies with a pairing code → in Claude Code:
#   /discord:access pair <code>
#   /discord:access policy allowlist
```
Proactive messages in Plan B: keep Plan A's scheduled check-ins (posting to Discord through the
webhook) and reply to the bot. Or ask the session itself to schedule its check-ins: session tasks
expire after 7 days, so the Sunday review re-creates them. `.claude/settings.json` pre-approves the
secretary's own commands, so it doesn't stall waiting for permission. Channels is a research
preview, so expect occasional changes. Docs: https://code.claude.com/docs/en/channels

## The safety net (GitHub Actions + Discord webhook), 10 minutes
1. **Discord server:** **+** → *Create My Own* → a private server, e.g. "HQ", with a `#secretary`
   channel.
2. **Webhook:** `#secretary` → ⚙️ *Edit Channel* → *Integrations* → *Webhooks* → *New Webhook* →
   **Copy Webhook URL** (treat it like a password).
3. **Your user ID** (for @mentions that buzz your phone): *User Settings* → *Advanced* →
   **Developer Mode** → right-click your name → **Copy User ID**. Put it in `data/settings.yaml` →
   `discord.owner_user_id`, or just tell me.
4. **GitHub:** repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*
   `DISCORD_WEBHOOK_URL`.
5. **Test:** *Actions* → **Safety net** → *Run workflow*.

It runs every 30 minutes and sends only critical reminders that nobody delivered within 45
minutes. On a private repo that uses about 1,440 of the 2,000 free Actions minutes a month.

## Creating the Discord bot (needed for Plan B)
1. https://discord.com/developers/applications → **New Application** → give it a name and avatar.
2. **Bot** tab → *Reset Token* → copy the token. Turn on **Message Content Intent**. Turn off
   *Public Bot*.
3. **OAuth2 → URL Generator:** scope `bot`; permissions *View Channels, Send Messages, Send
   Messages in Threads, Read Message History, Attach Files, Embed Links, Add Reactions*. Open the
   URL and add it to your private server.

**About "a real account":** Discord bans automating a normal user account (self-bots). The
secretary is a bot account with its own name and avatar; Discord shows a small "APP" tag next to it.

## Plan C — the pay-per-use bot (optional, not on your subscription)
`secretary/bot/` is a self-contained Discord bot that calls the Claude API directly. It's two-way
and proactive without Claude Code running, but **it is billed per message through an API key**
(Anthropic doesn't allow subscription logins in custom apps). Use it only if you want Discord
chat without an always-on Claude Code session. Setup: `pip install -e ".[bot]"`, fill `.env` from
`.env.example`, run `python -m secretary.bot`.
