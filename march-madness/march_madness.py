#!/usr/bin/env python3
"""
March Madness SMS Bot
Texts game matchups, rounds, and spreads for every NCAA Tournament game.
Uses The Odds API for live odds/spreads.

Designed to run hourly via cron. Each run checks for games starting within
the next hour and sends one text per game right before tipoff.
Tracks which games have already been texted to avoid duplicates.
"""

import smtplib
import json
import os
import sys
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path
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

# Tracking file to avoid duplicate texts
SCRIPT_DIR = Path(__file__).parent
SENT_GAMES_FILE = SCRIPT_DIR / "sent_games.json"

# How far ahead to look for upcoming games (minutes)
ALERT_WINDOW_MINUTES = 65  # Slightly over an hour to cover cron drift


def api_get(url):
    """Make a GET request and return parsed JSON."""
    req = Request(url)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"API error: {e}")
        return None


def load_sent_games():
    """Load the set of game IDs we've already texted about."""
    if SENT_GAMES_FILE.exists():
        try:
            data = json.loads(SENT_GAMES_FILE.read_text())
            # Clean out entries older than 2 days
            cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            return {k: v for k, v in data.items() if v > cutoff}
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def save_sent_games(sent):
    """Save the set of game IDs we've texted about."""
    SENT_GAMES_FILE.write_text(json.dumps(sent, indent=2))


def get_upcoming_games():
    """Fetch NCAAB games starting within the next hour."""
    if not ODDS_API_KEY:
        print("ERROR: ODDS_API_KEY not set")
        sys.exit(1)

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

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=ALERT_WINDOW_MINUTES)

    games = []
    for event in data:
        game_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))

        # Only games starting between now and the alert window
        if now <= game_time <= window_end:
            game = parse_game(event)
            if game:
                games.append(game)

    games.sort(key=lambda g: g["time"])
    return games


def get_todays_games():
    """Fetch all of today's NCAAB games (for morning summary mode)."""
    if not ODDS_API_KEY:
        print("ERROR: ODDS_API_KEY not set")
        sys.exit(1)

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

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = today_start + timedelta(days=1, hours=6)

    games = []
    for event in data:
        game_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
        if today_start <= game_time <= tomorrow_end:
            game = parse_game(event)
            if game:
                games.append(game)

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
        return "Final Four"
    elif game_count == 1:
        return "Championship"
    else:
        return "March Madness"


def format_spread(spread):
    """Format spread for display."""
    if not spread:
        return "No line"
    pts = spread["points"]
    team = spread["team"]
    if pts < 0:
        return f"{team} {pts}"
    elif pts > 0:
        return f"{team} +{pts}"
    return "Pick'em"


def format_game_text(game, round_name):
    """Format a single game as one complete text message."""
    spread_str = format_spread(game["spread"])

    return (
        f"MARCH MADNESS\n"
        f"{round_name}\n"
        f"\n"
        f"{game['away']} vs {game['home']}\n"
        f"Tip: {game['time_et']}\n"
        f"Spread: {spread_str}"
    )


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
    """
    Main entry point. Runs hourly via cron.
    Finds games starting in the next ~hour and texts each one individually.
    Tracks sent games to avoid duplicates.
    """
    print(f"Checking for upcoming games at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}...")

    games = get_upcoming_games()
    if not games:
        print("No games starting in the next hour.")
        return

    # Get today's total game count for round detection
    all_today = get_todays_games()
    round_name = detect_round(len(all_today))

    sent = load_sent_games()
    new_count = 0

    for game in games:
        game_id = game["id"]
        if game_id in sent:
            print(f"Already sent: {game['away']} vs {game['home']}")
            continue

        message = format_game_text(game, round_name)
        send_sms(message)
        print(f"Sent: {game['away']} vs {game['home']} ({game['time_et']})")

        sent[game_id] = datetime.now(timezone.utc).isoformat()
        new_count += 1

    save_sent_games(sent)
    print(f"\nDone! Sent {new_count} new game alert(s).")


if __name__ == "__main__":
    run()
