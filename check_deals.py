#!/usr/bin/env python3
"""Check OzBargain for new MacBook deals and notify Discord + WhatsApp.

Reads OzBargain RSS feeds (the search HTML page is now behind a Cloudflare
challenge and returns 403), dedupes by node id via seen.json, and pushes new
deals to the configured channels. Designed to run a few times a day from
GitHub Actions.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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
# Source feeds. OzBargain's RSS feeds (unlike /search/node/*) are not behind
# Cloudflare and are sorted newest-first. Point this at the brand/tag/category
# feed that covers your KEYWORDS — e.g. /brand/apple/feed for MacBooks (it
# carries Air + Pro), /tag/laptop/feed, /cat/computing/feed, etc.
FEED_URLS = ["https://www.ozbargain.com.au/brand/apple/feed"]
BASE_URL = "https://www.ozbargain.com.au"
SEEN_FILE = Path(__file__).with_name("seen.json")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# ----------------------------------------------------------------------------


def fetch_deals():
    """Return a list of {id, title, url, price} dicts from the RSS feeds."""
    deals = []
    seen_ids = set()
    for feed_url in FEED_URLS:
        resp = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.iter("item"):
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            # node id: guid is "<id> at https://...", link is /node/<id>.
            m = re.match(r"(\d+)", guid) or re.search(r"/node/(\d+)", link)
            if not m:
                continue
            node_id = m.group(1)
            if node_id in seen_ids:
                continue  # same deal can appear across multiple feeds

            title = re.sub(r"\s+", " ", (item.findtext("title") or "")).strip()
            if not any(k.lower() in title.lower() for k in KEYWORDS):
                continue

            # Recent deals only: drop anything posted more than MAX_AGE_DAYS ago.
            if MAX_AGE_DAYS is not None:
                posted = parse_pub_date(item)
                cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
                if posted is not None and posted < cutoff:
                    continue

            price = parse_price(title)
            if MAX_PRICE is not None and price is not None and price > MAX_PRICE:
                continue

            seen_ids.add(node_id)
            deals.append(
                {"id": node_id, "title": title, "url": link or f"{BASE_URL}/node/{node_id}", "price": price}
            )
    return deals


def parse_pub_date(item):
    """Timezone-aware post date from an RSS item's <pubDate>; None if absent."""
    raw = item.findtext("pubDate")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return None
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_expired(node_url):
    """True if the deal's node page is marked expired/out-of-stock.

    Node pages (unlike the search page) are not Cloudflare-challenged. On a
    dead deal the main article carries an "expired" class. On any fetch error
    we return False so a transient hiccup never silently drops a live deal.
    """
    try:
        resp = requests.get(node_url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return False
    soup = BeautifulSoup(resp.text, "html.parser")
    node = soup.select_one(".node-ozbdeal")
    return node is not None and "expired" in node.get("class", [])


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
    print(f"Found {len(deals)} matching deal(s) in the feed(s).")
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

    # Active deals only: the feed has no expiry flag, so check each new deal's
    # node page (cheap — only runs on unseen deals).
    to_notify = new
    if SKIP_EXPIRED:
        to_notify = []
        for deal in new:
            if is_expired(deal["url"]):
                print(f"  skip expired: {deal['id']} {deal['title']}")
                continue
            to_notify.append(deal)

    for deal in to_notify[:MAX_SEND_PER_RUN]:
        print(f"Notifying: {deal['title']}")
        notify_discord(deal)
        notify_whatsapp(deal)

    # Mark every new deal seen (incl. expired ones) so we don't re-check them.
    save_seen(seen | {d["id"] for d in new})
    return 0


if __name__ == "__main__":
    sys.exit(main())
