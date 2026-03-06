#!/usr/bin/env python3
"""
March Madness SMS Bot
Texts game matchups, rounds, and spreads for every NCAA Tournament game.
Uses The Odds API for live odds/spreads.
"""

import smtplib
import json
import os
import sys
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

# SMS Configuration (reuses movie quote bot setup)
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# The Odds API Configuration
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_ncaab"  # NCAA Basketball

# March Madness round dates (2026 - update yearly)
# These get auto-detected from game context, but serve as fallback labels
ROUND_LABELS = {
    "First Four": "First Four",
    "Round of 64": "Round of 64",
    "Round of 32": "Round of 32",
    "Sweet 16": "Sweet 16",
    "Elite 8": "Elite Eight",
    "Final Four": "Final Four",
    "Championship": "National Championship",
}


def api_get(url):
    """Make a GET request and return parsed JSON."""
    req = Request(url)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"API error: {e}")
        return None


def get_todays_games():
    """Fetch today's NCAAB games with spreads from The Odds API."""
    if not ODDS_API_KEY:
        print("ERROR: ODDS_API_KEY not set")
        sys.exit(1)

    # Get odds with spreads for NCAAB
    url = (
        f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds/"
        f"?apiKey={ODDS_API_KEY}"
        f"&regions=us"
        f"&markets=spreads"
        f"&oddsFormat=american"
    )

    data = api_get(url)
    if data is None:
        print("Failed to fetch odds data")
        return []

    # Filter to today's games (ET timezone)
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    # Also include tomorrow for games starting after midnight ET
    # (covers late-night games and next-day scheduling)
    window_end = tomorrow_start + timedelta(hours=6)

    games = []
    for event in data:
        game_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))

        if today_start <= game_time <= window_end:
            game = parse_game(event)
            if game:
                games.append(game)

    # Sort by game time
    games.sort(key=lambda g: g["time"])
    return games


def parse_game(event):
    """Parse a single game event into our format."""
    home = event.get("home_team", "TBD")
    away = event.get("away_team", "TBD")
    game_time = datetime.fromisoformat(
        event["commence_time"].replace("Z", "+00:00")
    )

    # Convert to ET for display
    et_offset = timezone(timedelta(hours=-5))
    game_time_et = game_time.astimezone(et_offset)

    # Extract spread from bookmakers
    spread = get_best_spread(event.get("bookmakers", []), home)

    return {
        "home": home,
        "away": away,
        "time": game_time,
        "time_et": game_time_et.strftime("%-I:%M %p ET"),
        "spread": spread,
        "id": event.get("id", ""),
    }


def get_best_spread(bookmakers, home_team):
    """Get consensus spread from bookmakers. Prefers FanDuel/DraftKings."""
    preferred = ["fanduel", "draftkings", "betmgm", "pointsbetus"]

    for book_key in preferred:
        for book in bookmakers:
            if book["key"] == book_key:
                spread = extract_spread(book, home_team)
                if spread:
                    return spread

    # Fall back to first available
    for book in bookmakers:
        spread = extract_spread(book, home_team)
        if spread:
            return spread

    return None


def extract_spread(bookmaker, home_team):
    """Extract spread info from a bookmaker's data."""
    for market in bookmaker.get("markets", []):
        if market["key"] == "spreads":
            for outcome in market.get("outcomes", []):
                if outcome["name"] == home_team:
                    point = outcome.get("point", 0)
                    return {
                        "team": home_team,
                        "points": point,
                        "source": bookmaker["title"],
                    }
    return None


def detect_round(game_count):
    """Estimate tournament round based on number of games today."""
    if game_count >= 14:
        return "Round of 64"
    elif game_count >= 7:
        return "Round of 32"
    elif game_count >= 3:
        return "Sweet 16"
    elif game_count == 2:
        return "Elite Eight"
    elif game_count == 2:
        return "Final Four"
    elif game_count == 1:
        return "Championship"
    else:
        return "March Madness"


def format_game_message(game, round_name):
    """Format a single game for SMS."""
    spread_str = "No line"
    if game["spread"]:
        pts = game["spread"]["points"]
        team = game["spread"]["team"]
        if pts < 0:
            spread_str = f"{team} {pts}"
        elif pts > 0:
            spread_str = f"{team} +{pts}"
        else:
            spread_str = "Pick'em"

    return (
        f"{game['away']} vs {game['home']}\n"
        f"{game['time_et']} | {spread_str}"
    )


def format_daily_message(games, round_name):
    """Format all games into SMS messages."""
    if not games:
        return None

    today = datetime.now().strftime("%m/%d")
    header = f"MARCH MADNESS {today}\n{round_name} - {len(games)} games\n"
    divider = "---\n"

    # SMS has ~160 char limit per segment, but email-to-SMS handles longer
    # messages by splitting them. Keep it readable.
    game_lines = []
    for game in games:
        game_lines.append(format_game_message(game, round_name))

    # Split into chunks if too many games (SMS readability)
    messages = []
    chunk_size = 4  # 4 games per text
    for i in range(0, len(game_lines), chunk_size):
        chunk = game_lines[i:i + chunk_size]
        part = ""
        if i == 0:
            part = header + divider
        else:
            part = f"GAMES {i+1}-{i+len(chunk)}\n" + divider

        part += ("\n" + divider).join(chunk)
        messages.append(part)

    return messages


def send_sms(message):
    """Send SMS via email-to-SMS gateway."""
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


def run():
    """Main entry point: fetch today's games and text them."""
    print(f"Fetching March Madness games for {datetime.now().strftime('%Y-%m-%d')}...")

    games = get_todays_games()

    if not games:
        print("No March Madness games today.")
        return

    round_name = detect_round(len(games))
    messages = format_daily_message(games, round_name)

    print(f"Found {len(games)} games ({round_name})")
    for msg in messages:
        send_sms(msg)
        print(f"---\n{msg}")

    print(f"\nDone! Sent {len(messages)} message(s).")


if __name__ == "__main__":
    run()
