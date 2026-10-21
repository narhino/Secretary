# Talking to your secretary on Discord

There are three layers. Start with **Layer 1** (about 10 minutes, free, no server), then add a two-way
chat layer when you're ready.

| | Layer 1: reminder pings | Layer 2: custom bot (recommended) | Layer 3: Claude Code Channels |
|---|---|---|---|
| What you get | Reminders, morning brief and weekly review posted to your Discord | Chat with the secretary in DMs, send photos, get reminders as DMs | Chat with a full Claude Code session through a Discord bot |
| Runs on | GitHub Actions (free) | Your always-on PC or a small VPS (~US$5/month) | Your always-on PC or a VPS, with Claude Code running |
| AI cost | none | Anthropic API usage (pay per message; set a monthly limit) | Included in your Claude Pro/Max plan |
| Proactive pings | yes (every 30 min, can run a few minutes late) | yes (checks every minute) | no (use Layer 1 for pings) |
| Maturity | stable | stable, this repo's code | research preview, so flags may change |

**About "a real account":** Discord forbids automating a normal user account ("self-bots") and
terminates accounts that do it. The secretary runs as a **bot account**. You give it a name, avatar
and status, and it DMs you like a contact; Discord shows a small "APP" tag next to its name.

---

## Layer 1 — reminder pings via webhook (no server)

1. **Create a private server:** in Discord, **+** → *Create My Own* → *For me and my friends*. Name it
   e.g. "HQ". Create a text channel `#secretary`.
2. **Create a webhook:** `#secretary` → ⚙️ *Edit Channel* → *Integrations* → *Webhooks* → *New
   Webhook* → name it "Secretary" → **Copy Webhook URL**. Treat it like a password.
3. **Your user ID** (so it can @mention you and your phone buzzes): *User Settings* → *Advanced* →
   turn on **Developer Mode** → right-click your own name → **Copy User ID**. Paste it into
   `data/settings.yaml` → `discord.owner_user_id`, or tell me and I'll do it.
4. **GitHub:** repo → *Settings* → *Secrets and variables* → *Actions*:
   - *Secrets* tab → **New repository secret** `DISCORD_WEBHOOK_URL` = the webhook URL
   - *Variables* tab → **New repository variable** `REMINDER_RUNNER` = `actions`
5. **Test:** repo → *Actions* → **Reminders** → *Run workflow*. Then set the channel's notification
   setting to *All messages* on your phone.

The workflow (`.github/workflows/reminders.yml`) runs every 30 minutes. That stays within the free
2,000 Actions minutes a month for private repos as long as nothing else uses many minutes. It records
what it sent in `data/state/sent.json`, so nothing is sent twice.

---

## Layer 2 — your own secretary bot (two-way chat)

### 2.1 Create the bot
1. Open https://discord.com/developers/applications → **New Application** → name it ("Secretary",
   or any name you like) and upload an avatar.
2. **Bot** tab → *Reset Token* → copy the **bot token** (shown once). Under *Privileged Gateway
   Intents* turn on **Message Content Intent**. Turn **off** *Public Bot*.
3. **OAuth2 → URL Generator:** scope `bot`; permissions *View Channels, Send Messages, Send Messages
   in Threads, Read Message History, Attach Files, Embed Links, Add Reactions*. Open the URL and add
   the bot to your private server. It has to share a server with you before it can DM you.

### 2.2 Anthropic API key
Create a key at https://platform.claude.com (Console) → *API keys*. Add billing and **set a monthly
spend limit**. The bot uses `claude-opus-5-5` by default; each message costs a few cents. Set
`SECRETARY_MODEL=claude-sonnet-5-5` in `.env` for about half the price, or
`SECRETARY_MODEL=claude-haiku-5-5` for much less, with weaker judgement.

### 2.3 Run it
On an always-on Linux machine or VPS (a Singapore region keeps latency low from Thailand):
```bash
git clone git@github.com:narhino/Secretary.git && cd Secretary
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[bot]"
cp .env.example .env && nano .env      # DISCORD_BOT_TOKEN, DISCORD_OWNER_ID, ANTHROPIC_API_KEY
python -m secretary.bot                 # Ctrl+C to stop; then install the service below
```
The bot needs to **push** to GitHub so every surface shares the same memory. Use a deploy key:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/secretary_deploy -N ""
cat ~/.ssh/secretary_deploy.pub   # GitHub repo → Settings → Deploy keys → Add → tick "Allow write access"
printf 'Host github.com\n  IdentityFile ~/.ssh/secretary_deploy\n' >> ~/.ssh/config
git config user.name "Secretary bot" && git config user.email "secretary-bot@users.noreply.github.com"
```
Keep it running with systemd: edit the paths in `deploy/secretary-bot.service`, then
```bash
sudo cp deploy/secretary-bot.service /etc/systemd/system/
sudo systemctl enable --now secretary-bot && journalctl -u secretary-bot -f
```
On Windows or Mac at home, keep the terminal open or use Task Scheduler / launchd. The computer
must stay awake.

### 2.4 Choose one reminder sender
While the bot runs it sends reminders itself, as DMs. Set the GitHub variable `REMINDER_RUNNER` to
`bot` so Actions stays quiet. If the bot will be offline for a while, switch the variable back to
`actions`. Both runners share `sent.json`, so switching never re-sends old reminders.

### 2.5 Use it
DM the bot `!help`. Then just talk: *"remind me to do the 90-day report on 12 Dec"*, *"bench 80x8 80x8
77.5x7"*, *"what's my week?"*, or send a photo of a receipt or immigration stamp. Only your user ID is
answered; everyone else is ignored. Optional `.env` settings: `DISCORD_CHAT_CHANNEL_ID` (a server
channel where the bot answers without an @mention), `DISCORD_NOTIFY_CHANNEL_ID` (post reminders
there instead of DMs).

---

## Layer 3 — Claude Code Channels (uses your Claude subscription)

Anthropic's official Discord channel plugin bridges a running Claude Code session to a Discord bot.
Claude then works directly in this repo with all its tools. Requirements: Claude Code v2.1.80+,
logged in with claude.ai (Pro/Max), [Bun](https://bun.sh) installed, and a bot created as in 2.1
(**use a separate bot application** from Layer 2's, or run only one of them).
```bash
cd Secretary && claude
# inside Claude Code:
/plugin install discord@claude-plugins-official
/discord:configure <bot token>
# exit, then start with the channel enabled (inside tmux so it keeps running):
claude --channels plugin:discord@claude-plugins-official
# DM the bot → it replies with a pairing code → in Claude Code:
/discord:access pair <code>
/discord:access policy allowlist
```
Notes: messages only arrive while that session runs. Permission prompts pause the session while
you're away; `.claude/settings.json` pre-allows the secretary's own commands to reduce this. Keep
Layer 1 on for scheduled pings. Docs: https://code.claude.com/docs/en/channels

---

## And from the Claude app
Open this repository in Claude Code on the web or in the app (claude.ai/code) and talk to me there.
I read `CLAUDE.md` and the same files, and push changes the bot and reminders pick up.
