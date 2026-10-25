# Phone sync: steps, calories and places with no screenshots

Apple Health and Google Maps Timeline can't be connected directly: their data stays on your
phone, and there's no online access or claude.ai connector for either. Instead, a small automation
on your phone sends the data to your secretary on a schedule:

```
phone automation ──POST──▶ GitHub (your private Secretary repo) ──▶ data/daily.csv, data/places.csv
                                                                  └──▶ HQ app (synced at each check-in)
```

It runs only while the repo is **private**. The workflow refuses public repos, so your location
never becomes public.

## 1. Create a GitHub token (once, 2 minutes)
github.com → your avatar → **Settings** → **Developer settings** → **Personal access tokens** →
**Fine-grained tokens** → **Generate new token**
- Name: `secretary-phone` · Expiration: 1 year (the secretary reminds you before it expires)
- Repository access: **Only select repositories** → `narhino/Secretary`
- Permissions → Repository permissions → **Contents: Read and write**
- Generate, then copy the token straight into the phone automation below. Never paste it in chat.

Every request the automation sends:
- URL: `https://api.github.com/repos/narhino/Secretary/dispatches`
- Method: `POST`
- Headers: `Authorization` = `Bearer <your token>`, `Accept` = `application/vnd.github+json`
- Body (JSON), one of:
  - `{"event_type": "health", "client_payload": {"date": "2026-10-25", "steps": 8432, "active_kcal": 410, "distance_km": 6.3}}`
  - `{"event_type": "location", "client_payload": {"time": "2026-10-25 18:32", "lat": 13.779, "lon": 100.544, "name": "Fitness First", "event": "arrive", "kind": "gym"}}`

`kind` is one of: home, gym, work, food, shop, health, social, transit, outdoors, other.

## 2a. iPhone (Shortcuts app)

**Shortcut "Send health to secretary"**
1. *Find Health Samples* → Type **Steps**, Start Date **is today** → *Calculate Statistics* **Sum**
   → *Set Variable* `steps`.
2. Same for **Active Energy** → `kcal`, and **Walking + Running Distance** (unit km) → `km`.
3. *Current Date* → *Format Date* custom `yyyy-MM-dd` → `day`.
4. *Get Contents of URL*: the URL, method, headers and body from step 1. In the body, add
   `event_type` (Text) `health` and `client_payload` (Dictionary) with `date`=`day`, `steps`=`steps`,
   `active_kcal`=`kcal`, `distance_km`=`km` (set the three numbers' type to Number).

Automate it: Shortcuts → **Automation** → **+** → **Time of Day** → 21:45, Daily → **Run
Immediately** → choose the shortcut. Add a second one at 12:30 if you want midday numbers.

**Shortcut "Send location to secretary"**
1. *Get Current Location* → *Get Details of Locations* → **Name** → `place`.
2. *Current Date* → *Format Date* custom `yyyy-MM-dd HH:mm` → `time`.
3. *Get Contents of URL* with body `event_type`=`location` and `client_payload` = `time`,
   `lat` (Latitude of Current Location), `lon` (Longitude), `name`=`place`, `event`=`ping`.

Automate it:
- **Arrive** automations for the places that matter (home, gym, ortho clinic, work): Automation →
  **+** → **Arrive** → pick the place → Run Immediately. Duplicate the shortcut per place and set
  `event`=`arrive` and the right `kind`.
- A few **Time of Day** automations (e.g. 10:00, 14:00, 18:00, 22:00) running the ping version,
  for a rough trail of the day.

## 2b. Android
- **Location:** MacroDroid (free) works well. Trigger: *Location Trigger* (enter an area) or
  *Day/Time*. Action: *HTTP Request* (POST) with the URL, headers and JSON body from step 1,
  filling `lat`/`lon` from MacroDroid's location variables.
- **Steps and calories:** Android keeps them in Health Connect, which automation apps can't read
  by default. Tell the secretary which app you use (Samsung Health, Google Fit, Fitbit, a watch)
  and she'll find the simplest route.

## 3. Test it
Run the shortcut once by hand. Within a minute you'll see a **Phone sync** run under the repo's
*Actions* tab, then the numbers appear in your HQ app at the next check-in.
