#!/usr/bin/env python3
"""Check OzBargain for new MacBook deals and notify Discord + WhatsApp.

Scrapes the keyword search page (the only reliable source for all matches),
dedupes by node id via seen.json, and pushes new deals to the configured
channels. Designed to run once a morning from GitHub Actions.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# --- Config -----------------------------------------------------------------
KEYWORDS = ["macbook"]          # title must contain one of these (case-insensitive)
MAX_PRICE = None                # e.g. 2000 to only notify deals at/under $2000; None = no filter
MAX_AGE_DAYS = 30               # only deals posted within this many days; None = no age limit
SKIP_EXPIRED = True             # only active deals (drop expired / out-of-stock)
MAX_SEND_PER_RUN = 10           # flood guard
SEARCH_URL = "https://www.ozbargain.com.au/search/node/" + "+".join(KEYWORDS)
BASE_URL = "https://www.ozbargain.com.au"
SEEN_FILE = Path(__file__).with_name("seen.json")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# ----------------------------------------------------------------------------


def fetch_deals():
    """Return a list of {id, title, url, price} dicts from the search page."""
    resp = requests.get(SEARCH_URL, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    deals = []
    for dt in soup.select("dl.search-results dt.title"):
        # Two anchors point at /node/<id>: the thumbnail (no text) and the
        # title (has text). Pick the one carrying the title text.
        title_link = next(
            (a for a in dt.select('a[href^="/node/"]') if a.get_text(strip=True)),
            None,
        )
        if not title_link:
            continue

        href = title_link["href"]
        m = re.search(r"/node/(\d+)", href)
        if not m:
            continue
        node_id = m.group(1)
        # Separator + collapse fixes titles mangled by search-term highlighting
        # (e.g. "MacBook"+"Air" -> "MacBook Air").
        title = re.sub(r"\s+", " ", title_link.get_text(" ", strip=True)).strip()

        # Keep genuine deals only: the result row carries an "n-deal" marker.
        # Competitions ("Win a...") are "n-comp"; forum posts have neither.
        dd = dt.find_next_sibling("dd")
        scope = str(dt) + (str(dd) if dd else "")
        if "n-deal" not in scope:
            continue

        # Active deals only: expired/out-of-stock deals carry a ".expired" tag.
        if SKIP_EXPIRED and dt.select_one(".expired"):
            continue

        if not any(k.lower() in title.lower() for k in KEYWORDS):
            continue

        # Recent deals only: drop anything posted more than MAX_AGE_DAYS ago.
        if MAX_AGE_DAYS is not None:
            posted = parse_post_date(dd)
            if posted is not None and posted < datetime.now() - timedelta(days=MAX_AGE_DAYS):
                continue

        price = parse_price(title)
        if MAX_PRICE is not None and price is not None and price > MAX_PRICE:
            continue

        deals.append(
            {"id": node_id, "title": title, "url": BASE_URL + href, "price": price}
        )
    return deals


def parse_post_date(dd):
    """Best-effort post date from a result's metadata (DD/MM/YYYY); None if absent."""
    if dd is None:
        return None
    m = re.search(r"\d{2}/\d{2}/\d{4}", dd.get_text(" ", strip=True))
    if not m:
        return None
    try:
        return datetime.strptime(m.group(0), "%d/%m/%Y")
    except ValueError:
        return None


def parse_price(title):
    """Best-effort dollar amount from a deal title; None if not found."""
    m = re.search(r"\$\s?([\d,]+(?:\.\d{2})?)", title)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def load_seen():
    """Return the set of known ids, or None to signal a first/empty run."""
    if not SEEN_FILE.exists():
        return None
    try:
        ids = json.loads(SEEN_FILE.read_text()).get("ids", [])
    except (json.JSONDecodeError, OSError):
        return None
    return set(ids) if ids else None  # empty state => seed silently


def save_seen(ids):
    SEEN_FILE.write_text(json.dumps({"ids": sorted(ids, reverse=True)}, indent=2) + "\n")


def notify_discord(deal):
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return
    price = f" — ${deal['price']:.0f}" if deal["price"] else ""
    payload = {"content": f"\U0001f34e **{deal['title']}**{price}\n{deal['url']}"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print(f"  discord: sent {deal['id']}")
    except requests.RequestException as e:
        print(f"  discord: FAILED {deal['id']}: {e}")


def notify_whatsapp(deal):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("WHATSAPP_APIKEY")
    if not (phone and apikey):
        return
    price = f" - ${deal['price']:.0f}" if deal["price"] else ""
    text = quote(f"\U0001f34e {deal['title']}{price}\n{deal['url']}")
    api = (
        f"https://api.callmebot.com/whatsapp.php?"
        f"phone={quote(phone)}&text={text}&apikey={quote(apikey)}"
    )
    try:
        r = requests.get(api, timeout=20)
        r.raise_for_status()
        print(f"  whatsapp: sent {deal['id']}")
    except requests.RequestException as e:
        print(f"  whatsapp: FAILED {deal['id']}: {e}")


def main():
    deals = fetch_deals()
    print(f"Found {len(deals)} MacBook deal(s) on the search page.")
    if not deals:
        return 0

    seen = load_seen()
    if seen is None:
        # First run: seed state, send nothing, avoid flooding with history.
        save_seen({d["id"] for d in deals})
        print(f"First run: seeded {len(deals)} deal(s), sent no notifications.")
        return 0

    new = [d for d in deals if d["id"] not in seen]
    print(f"{len(new)} new deal(s) since last run.")
    if not new:
        return 0

    for deal in new[:MAX_SEND_PER_RUN]:
        print(f"Notifying: {deal['title']}")
        notify_discord(deal)
        notify_whatsapp(deal)

    save_seen(seen | {d["id"] for d in new})
    return 0


if __name__ == "__main__":
    sys.exit(main())
