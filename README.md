# OzBargain MacBook deal notifier

Checks [ozbargain.com.au](https://www.ozbargain.com.au) every morning for new **MacBook**
deals and pushes any matches to **Discord** and **WhatsApp**. Free to run — it's just a
Python script on a GitHub Actions cron, no server.

## How it works

1. GitHub Actions runs `check_deals.py` once each morning.
2. The script scrapes the keyword search page `…/search/node/macbook` (the only reliable
   source that lists *all* MacBook matches), keeps genuine deals, and drops competitions and
   forum posts.
3. New deals (not in `seen.json`) are sent to Discord + WhatsApp.
4. `seen.json` is committed back so the same deal is never sent twice.

## Setup

### 1. Discord webhook
Discord channel → **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook** →
**Copy Webhook URL**.

### 2. WhatsApp via CallMeBot (free)
1. Save **+34 644 84 71 89** as a phone contact.
2. Send it this WhatsApp message: `I allow callmebot to send me messages to this number`
3. It replies with your **API key**.
4. Your phone value is your full number with country code, no `+` or spaces
   (e.g. Australian mobile `0412 345 678` → `61412345678`).

More: https://www.callmebot.com/blog/free-api-whatsapp-messages/

### 3. Add GitHub repository secrets
Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value |
| --- | --- |
| `DISCORD_WEBHOOK_URL` | the webhook URL from step 1 |
| `WHATSAPP_PHONE` | your number, e.g. `61412345678` |
| `WHATSAPP_APIKEY` | the CallMeBot API key from step 2 |

Any secret you leave out simply disables that channel — both are optional.

### 4. First run
Push this repo to GitHub, then **Actions** → *OzBargain MacBook deals* → **Run workflow**.
The first run seeds `seen.json` with current deals and sends nothing (so you don't get a
backlog flood). From then on it notifies only genuinely new deals each morning.

## Configuration

Edit the config block at the top of [`check_deals.py`](check_deals.py):

- `KEYWORDS` — terms that must appear in the deal title (default `["macbook"]`).
- `MAX_PRICE` — set to e.g. `2000` to only notify deals at/under $2000; `None` = no filter.
- `MAX_SEND_PER_RUN` — safety cap on notifications per run (default `10`).

Schedule lives in [`.github/workflows/macbook-deals.yml`](.github/workflows/macbook-deals.yml)
as a UTC cron. The default `0 21 * * *` is ~7–8am Sydney; adjust the hour to taste.

## Run locally

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="…"      # optional
export WHATSAPP_PHONE="61412345678" # optional
export WHATSAPP_APIKEY="…"          # optional
python check_deals.py
```
