#!/usr/bin/env python3
"""
Concert Announcement SMS Bot

Sends a weekly roundup text covering:
  1. PRIORITY - new shows from artists on your watchlist (anywhere in the US)
  2. DC AREA  - newly announced shows at venues within ~50mi of DC

Uses the Ticketmaster Discovery API (free key at developer.ticketmaster.com).
Tracks event IDs already texted so each show is only announced once.

Runs Monday mornings via GitHub Actions cron.
"""

import smtplib
import json
import os
import sys
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote
from urllib.error import URLError, HTTPError

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Ticketmaster Discovery API
TM_KEY = os.environ.get("TICKETMASTER_API_KEY", "")
TM_BASE = "https://app.ticketmaster.com/discovery/v2/events.json"

# Search area — defaults to DC, ~50 mile radius covers MD/VA venues
LATITUDE = os.environ.get("CONCERT_LAT", "38.9072")
LONGITUDE = os.environ.get("CONCERT_LON", "-77.0369")
RADIUS_MILES = os.environ.get("CONCERT_RADIUS", "50")
AREA_NAME = os.environ.get("CONCERT_AREA", "DC")

SCRIPT_DIR = Path(__file__).parent
ARTISTS_FILE = SCRIPT_DIR / "artists.json"
SEEN_FILE = SCRIPT_DIR / "seen_events.json"

ET = timezone(timedelta(hours=-5))

# Keep the text readable — cap how many local shows we list
MAX_LOCAL_SHOWS = 12
# Drop tracked events older than this so the file doesn't grow forever
SEEN_RETENTION_DAYS = 400


def api_get(url, retries=3):
    """GET JSON with simple retry/backoff for rate limits."""
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "ConcertBot/1.0"})
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"HTTP {e.code} for {url.split('apikey=')[0]}")
            return None
        except URLError as e:
            print(f"API error: {e}")
            return None
    return None


def send_sms(message):
    if not EMAIL_PASSWORD:
        print(f"[DRY RUN] Would send:\n{message}\n")
        return

    msg = MIMEText(message)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = SMS_EMAIL
    msg["Subject"] = ""

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"SMS sent at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


def load_watchlist():
    if not ARTISTS_FILE.exists():
        print(f"No artists.json found at {ARTISTS_FILE}")
        return []
    try:
        with open(ARTISTS_FILE) as f:
            data = json.load(f)
        return [a for a in data.get("watchlist", []) if a and not a.startswith("_")]
    except (json.JSONDecodeError, IOError) as e:
        print(f"Could not read artists.json: {e}")
        return []


def load_seen():
    """Load previously texted event IDs -> the show date, so we can expire them."""
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_seen(seen):
    """Persist seen events, pruning anything long past."""
    cutoff = (datetime.now(ET) - timedelta(days=SEEN_RETENTION_DAYS)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN_FILE, "w") as f:
        json.dump(pruned, f, indent=2, sort_keys=True)
    print(f"Tracking {len(pruned)} events")


def parse_event(ev):
    """Pull the fields we care about out of a Ticketmaster event object."""
    name = ev.get("name", "Unknown")
    ev_id = ev.get("id", "")

    dates = ev.get("dates", {}).get("start", {})
    date_str = dates.get("localDate", "")

    venue = ""
    city = ""
    embedded = ev.get("_embedded", {})
    venues = embedded.get("venues", [])
    if venues:
        venue = venues[0].get("name", "")
        city_obj = venues[0].get("city", {})
        state_obj = venues[0].get("state", {})
        city = city_obj.get("name", "")
        state = state_obj.get("stateCode", "")
        if state and city:
            city = f"{city}, {state}"

    # Presale / onsale info is the actionable part
    onsale = ""
    sales = ev.get("sales", {}).get("public", {})
    start = sales.get("startDateTime", "")
    if start:
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            dt_et = dt.astimezone(ET)
            if dt_et > datetime.now(ET):
                onsale = dt_et.strftime("%-m/%-d")
        except (ValueError, AttributeError):
            pass

    return {
        "id": ev_id,
        "name": name,
        "date": date_str,
        "venue": venue,
        "city": city,
        "onsale": onsale,
    }


def fetch_local_events():
    """All upcoming music events within radius of the configured location."""
    url = (
        f"{TM_BASE}?apikey={TM_KEY}"
        f"&latlong={LATITUDE},{LONGITUDE}"
        f"&radius={RADIUS_MILES}&unit=miles"
        f"&classificationName=music"
        f"&sort=date,asc"
        f"&size=200"
    )
    data = api_get(url)
    if not data:
        return []

    events = data.get("_embedded", {}).get("events", [])
    return [parse_event(e) for e in events]


def fetch_artist_events(artist):
    """Upcoming events for one watchlist artist, nationwide."""
    url = (
        f"{TM_BASE}?apikey={TM_KEY}"
        f"&keyword={quote(artist)}"
        f"&classificationName=music"
        f"&sort=date,asc"
        f"&size=50"
    )
    data = api_get(url)
    if not data:
        return []

    events = data.get("_embedded", {}).get("events", [])
    parsed = [parse_event(e) for e in events]

    # Ticketmaster keyword search is fuzzy — keep only real name matches
    needle = artist.lower().strip()
    return [p for p in parsed if needle in p["name"].lower()]


def fmt_date(date_str):
    """2026-09-14 -> Sep 14"""
    if not date_str:
        return "TBA"
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%-b %-d")
    except ValueError:
        return date_str


def fmt_show(ev, include_city=True):
    parts = [f"{ev['name']}"]
    detail = fmt_date(ev["date"])
    if ev["venue"]:
        detail += f" @ {ev['venue']}"
    if include_city and ev["city"]:
        detail += f" ({ev['city']})"
    parts.append(detail)
    line = " - ".join(parts)
    if ev["onsale"]:
        line += f" | onsale {ev['onsale']}"
    return line


def build_roundup():
    if not TM_KEY:
        print("TICKETMASTER_API_KEY not set — cannot fetch concerts")
        return None

    seen = load_seen()
    watchlist = load_watchlist()
    new_seen = dict(seen)

    # --- Priority: watchlist artists, anywhere ---
    priority = []
    for artist in watchlist:
        print(f"Checking {artist}...")
        for ev in fetch_artist_events(artist):
            if ev["id"] and ev["id"] not in seen:
                priority.append(ev)
                new_seen[ev["id"]] = ev["date"] or "9999-12-31"
        time.sleep(0.25)  # be polite to the API

    # --- Local: everything new near DC ---
    print(f"Checking {AREA_NAME} area venues...")
    local = []
    for ev in fetch_local_events():
        if ev["id"] and ev["id"] not in new_seen:
            local.append(ev)
            new_seen[ev["id"]] = ev["date"] or "9999-12-31"

    if not priority and not local:
        print("Nothing newly announced this week")
        save_seen(new_seen)
        return None

    week = datetime.now(ET).strftime("%b %-d")
    lines = [f"New Concerts - week of {week}", ""]

    if priority:
        lines.append("YOUR ARTISTS:")
        for ev in priority:
            lines.append(f"- {fmt_show(ev)}")
        lines.append("")

    if local:
        lines.append(f"{AREA_NAME.upper()} AREA:")
        for ev in local[:MAX_LOCAL_SHOWS]:
            lines.append(f"- {fmt_show(ev, include_city=False)}")
        extra = len(local) - MAX_LOCAL_SHOWS
        if extra > 0:
            lines.append(f"+{extra} more")

    save_seen(new_seen)
    return "\n".join(lines).strip()


def run():
    text = build_roundup()
    if text:
        print(f"\n{text}\n")
        send_sms(text)
    else:
        print("No text sent")


if __name__ == "__main__":
    # First run would text every show already on sale — use --seed to
    # record the current slate silently, then real alerts start next week.
    if "--seed" in sys.argv:
        if not TM_KEY:
            print("TICKETMASTER_API_KEY not set")
            sys.exit(1)
        seen = load_seen()
        for ev in fetch_local_events():
            if ev["id"]:
                seen[ev["id"]] = ev["date"] or "9999-12-31"
        for artist in load_watchlist():
            for ev in fetch_artist_events(artist):
                if ev["id"]:
                    seen[ev["id"]] = ev["date"] or "9999-12-31"
            time.sleep(0.25)
        save_seen(seen)
        print("Seeded — future runs will only report newly announced shows.")
    else:
        run()
