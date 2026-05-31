# OzBargain MacBook deal notifier

Checks [ozbargain.com.au](https://www.ozbargain.com.au) a few times a day for new **MacBook**
deals and pushes any matches to **Discord** and **WhatsApp**. Free to run — it's just a
Python script on a GitHub Actions cron, no server, no database.

## How it works

1. GitHub Actions runs `check_deals.py` every few hours.
2. The script reads OzBargain's RSS feeds listed in `FEED_URLS` (default
   `…/brand/apple/feed`, which covers MacBook Air + Pro), keeps items whose title matches
   `KEYWORDS`, and drops anything older than `MAX_AGE_DAYS`.
   > We use the RSS feeds rather than the `…/search/node/macbook` HTML page because OzBargain
   > put that page behind a Cloudflare challenge (it now returns **HTTP 403**). The feeds are
   > not challenged and are sorted newest-first. To watch different keywords, point `FEED_URLS`
   > at the matching brand/tag/category feed (e.g. `/tag/laptop/feed`, `/cat/computing/feed`).
3. For each new deal, the script fetches its node page and skips it if it's already
   expired/out-of-stock (`SKIP_EXPIRED`).
4. New deals (not already in `seen.json`) are sent to Discord + WhatsApp.
5. `seen.json` is committed back to the repo so the same deal is never sent twice.

---

# Tutorial: deploy your own copy

Follow these steps end to end. It takes about 10 minutes and costs nothing.

## Step 1 — Get your own copy of the repo

You need the project under *your own* GitHub account so Actions and secrets belong to you.

1. Click **Fork** (top-right of this repo) to create `https://github.com/<your-username>/ozb-watcher`.
2. (Optional) Clone it locally if you want to edit config:
   ```bash
   git clone git@github.com:<your-username>/ozb-watcher.git
   cd ozb-watcher
   ```

> **Forks have Actions disabled by default.** On your fork, open the **Actions** tab and click
> **"I understand my workflows, go ahead and enable them"**. Scheduled (cron) runs only fire on
> the **default branch** (`main`).

## Step 2 — Create a Discord webhook (~1 min)

In Discord, on the channel you want deals posted to:
**Edit Channel** (gear icon) → **Integrations** → **Webhooks** → **New Webhook** →
**Copy Webhook URL**.

That URL is your `DISCORD_WEBHOOK_URL`. (Don't have Discord? Skip — see Step 3 for WhatsApp; at
least one channel is enough.)

## Step 3 — Enable free WhatsApp via CallMeBot (~2 min)

CallMeBot sends WhatsApp messages to *your own* number for free after a one-time opt-in:

1. Save **+34 644 84 71 89** as a contact in your phone.
2. Send it this exact WhatsApp message: `I allow callmebot to send me messages to this number`
3. It replies with your **API key** — that's your `WHATSAPP_APIKEY`.
4. Your `WHATSAPP_PHONE` is your full number with country code, **no `+` or spaces**
   (e.g. Australian mobile `0412 345 678` → `61412345678`).

Docs: <https://www.callmebot.com/blog/free-api-whatsapp-messages/>

> Don't want WhatsApp? Skip it — just configure Discord. Any channel whose secrets are missing
> is silently disabled.

## Step 4 — Add the secrets to your repo

GitHub Actions reads your credentials from **repository secrets** (never commit them to code).

**Option A — Web UI (no tools needed):**
1. Go to **`https://github.com/<your-username>/ozb-watcher/settings/secrets/actions`**
   (or: repo → **Settings** → **Secrets and variables** → **Actions**).
2. Click **New repository secret** and add each of these:

   | Name | Value |
   | --- | --- |
   | `DISCORD_WEBHOOK_URL` | the webhook URL from Step 2 |
   | `WHATSAPP_PHONE` | your number, e.g. `61412345678` |
   | `WHATSAPP_APIKEY` | the CallMeBot API key from Step 3 |

**Option B — GitHub CLI:**
```bash
# macOS: brew install gh   |   then: gh auth login
gh secret set DISCORD_WEBHOOK_URL --repo <your-username>/ozb-watcher
gh secret set WHATSAPP_PHONE     --repo <your-username>/ozb-watcher
gh secret set WHATSAPP_APIKEY    --repo <your-username>/ozb-watcher
```

## Step 5 — Run it once to seed state

Open the **Actions** tab → **OzBargain MacBook deals** → **Run workflow** → **Run workflow**.

This first run records the current deals into `seen.json` and **sends nothing** — so you don't
get flooded with a backlog. From then on the cron (every few hours) pings only genuinely *new* deals.

## Step 6 — Verify it's working

After the manual run finishes:

- The workflow run should be **green**.
- A new auto-commit **"Update seen deals [skip ci]"** appears on `main` — this proves the feed
  read and state persistence work end to end.
- The run log shows `Found N matching deal(s)` and `First run: seeded N deal(s)`.

That's it — you're deployed. Every few hours you'll get a ping for any new MacBook deal.

### Optional: confirm notifications actually deliver

The first run is intentionally silent, so to verify your Discord/WhatsApp credentials work,
hit the endpoints directly:

```bash
# Discord
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"ozb-watcher test"}' "<YOUR_WEBHOOK_URL>"

# WhatsApp (CallMeBot)
curl "https://api.callmebot.com/whatsapp.php?phone=<PHONE>&text=ozb-watcher%20test&apikey=<KEY>"
```

If both messages arrive, the live deal pings will too.

---

## Configuration

Edit the config block at the top of [`check_deals.py`](check_deals.py):

- `KEYWORDS` — terms that must appear in the deal title (default `["macbook"]`). Change this to
  watch for anything else, e.g. `["ipad"]` or `["rtx 5090"]`.
- `FEED_URLS` — OzBargain RSS feeds to read (default `["…/brand/apple/feed"]`, which covers
  MacBook Air + Pro). Point this at the brand/tag/category feed matching your `KEYWORDS` —
  e.g. `…/tag/laptop/feed`, `…/cat/computing/feed`, `…/brand/<brand>/feed`. Browse a feed in a
  browser to confirm it lists the deals you care about.
- `MAX_PRICE` — set to e.g. `2000` to only notify deals at/under $2000; `None` = no filter.
- `MAX_AGE_DAYS` — only notify deals posted within this many days (default `30`); `None` = no age limit.
- `SKIP_EXPIRED` — `True` (default) notifies only active deals: each new deal's node page is
  checked and expired / out-of-stock ones are dropped.
- `MAX_SEND_PER_RUN` — safety cap on notifications per run (default `10`).

The schedule lives in [`.github/workflows/macbook-deals.yml`](.github/workflows/macbook-deals.yml)
as a UTC cron. The default `0 */4 * * *` runs every 4 hours — the brand feed only holds ~10
newest items, so frequent checks (dedup makes extra runs free) avoid missing deals. Commit and
push any change to apply it.

## Run locally

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="…"      # optional
export WHATSAPP_PHONE="61412345678" # optional
export WHATSAPP_APIKEY="…"          # optional
python check_deals.py
```

The first local run with an empty `seen.json` seeds and sends nothing. To force a test
notification, temporarily remove one id from `seen.json` and re-run — that deal will be treated
as new.

## Troubleshooting

- **No notifications, but the run is green:** likely the first (seeding) run, or there were no
  new deals. Check the log for `0 new deal(s)`. Confirm secrets are set under *Actions* secrets
  (not *Codespaces* / *Dependabot*).
- **`Found 0 matching deal(s)`:** the configured `FEED_URLS` may not list your keyword right now,
  or OzBargain changed its feed. Open the feed URL in a browser to check it returns deals and that
  titles contain your `KEYWORDS`. (A 403 / Cloudflare "Just a moment…" page means that endpoint is
  challenged — use an RSS `…/feed` URL, which is not.)
- **The "Update seen deals" commit doesn't appear:** the workflow needs write access. It already
  declares `permissions: contents: write`; if you also tightened repo defaults, set
  **Settings → Actions → General → Workflow permissions** to **Read and write**.
- **Scheduled run never fires:** make sure Actions are enabled on your fork and the workflow is
  on the **default branch**. GitHub may also delay scheduled jobs under load — harmless here,
  since dedup is by deal id, not by time.
