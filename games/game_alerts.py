#!/usr/bin/env python3
"""
Sports Game Alert System
Sends SMS alert 7 days before favorite teams/players come to Washington DC
"""

import smtplib
import requests
import os
import sys
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# ESPN API base
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Teams to track and their DC opponents
# (sport, league, team_id, team_name, dc_team_id, dc_team_name)
MATCHUPS = [
    ("football", "nfl", 16, "Vikings", 28, "Commanders"),
    ("basketball", "nba", 20, "76ers", 27, "Wizards"),
    ("basketball", "nba", 13, "Lakers", 27, "Wizards"),       # LeBron
    ("basketball", "nba", 24, "Spurs", 27, "Wizards"),        # Wembanyama
    ("hockey", "nhl", 15, "Flyers", 23, "Capitals"),
    ("baseball", "mlb", 22, "Phillies", 20, "Nationals"),
    ("football", "college-football", 213, "Penn State", None, "DC area"),
]

# DC area venue cities to match for college football
DC_CITIES = ["washington", "landover", "college park", "annapolis", "baltimore"]


def get_team_schedule(sport, league, team_id):
    """Fetch team schedule from ESPN API."""
    now = datetime.now()
    # NFL uses fall year, NBA/NHL use end year, MLB uses current year
    if league == "nfl" or league == "college-football":
        season = now.year if now.month >= 6 else now.year - 1
    elif league in ("nba", "nhl"):
        season = now.year if now.month >= 9 else now.year
    else:
        season = now.year

    url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/schedule?season={season}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as e:
        print(f"  Error fetching {sport}/{league} team {team_id}: {e}")
        return []


def is_dc_game(event, dc_team_id):
    """Check if this game is played in DC (away team traveling to DC opponent)."""
    competitions = event.get("competitions", [])
    if not competitions:
        return False

    comp = competitions[0]
    competitors = comp.get("competitors", [])

    for team in competitors:
        team_id = int(team.get("id", 0))
        home_away = team.get("homeAway", "")
        if team_id == dc_team_id and home_away == "home":
            return True

    return False


def is_dc_area_venue(event):
    """Check if game venue is in the DC area (for college football)."""
    competitions = event.get("competitions", [])
    if not competitions:
        return False

    venue = competitions[0].get("venue", {})
    city = venue.get("address", {}).get("city", "").lower()
    return any(dc_city in city for dc_city in DC_CITIES)


def parse_game_date(event):
    """Parse game date from ESPN event."""
    date_str = event.get("date", "")
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def get_game_name(event):
    """Get the game display name."""
    return event.get("name", event.get("shortName", "Unknown Game"))


def get_venue(event):
    """Get venue name from event."""
    competitions = event.get("competitions", [])
    if not competitions:
        return ""
    venue = competitions[0].get("venue", {})
    return venue.get("fullName", venue.get("shortName", ""))


def check_upcoming_games(days_ahead=7, scan_range=1):
    """Check for games happening in `days_ahead` days. scan_range allows checking multiple days."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    alerts = []

    for sport, league, team_id, team_name, dc_team_id, dc_team_name in MATCHUPS:
        print(f"Checking {team_name} ({league})...")
        events = get_team_schedule(sport, league, team_id)

        for event in events:
            game_date = parse_game_date(event)
            if not game_date:
                continue

            game_day = game_date.replace(hour=0, minute=0, second=0, microsecond=0)
            days_until = (game_day - today).days

            # Check if game is in the target window
            if days_until < days_ahead or days_until >= days_ahead + scan_range:
                continue

            # Check if it's a DC game
            is_dc = False
            if dc_team_id is not None:
                is_dc = is_dc_game(event, dc_team_id)
            else:
                # College football - check venue city
                is_dc = is_dc_area_venue(event)

            if is_dc:
                venue = get_venue(event)
                game_str = game_date.strftime("%a %b %d")
                alerts.append(f"{team_name} vs {dc_team_name}\n{game_str} @ {venue}")
                print(f"  ALERT: {team_name} at {dc_team_name} on {game_str}")

    return alerts


def send_sms(message, attempts=4):
    """Send SMS via email-to-SMS gateway.

    Yahoo intermittently drops the connection mid-AUTH when the request comes
    from a datacenter IP, so retry with backoff before giving up.
    """
    msg = MIMEText(message)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = SMS_EMAIL
    msg["Subject"] = ""

    for attempt in range(1, attempts + 1):
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            print(f"SMS sent at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            return
        except (smtplib.SMTPException, OSError) as e:
            print(f"Attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}")
            if attempt == attempts:
                raise
            delay = 15 * (2 ** (attempt - 1))
            print(f"Retrying in {delay}s...")
            time.sleep(delay)


def main():
    # --test flag: scan next 30 days and print all upcoming DC games
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("TEST MODE: Scanning next 30 days for DC games...\n")
        alerts = check_upcoming_games(days_ahead=0, scan_range=30)
        if alerts:
            print(f"\nFound {len(alerts)} upcoming DC games:")
            for a in alerts:
                print(f"\n{a}")
        else:
            print("\nNo upcoming DC games found in next 30 days.")
        return

    # Normal mode: check for games exactly 7 days away
    alerts = check_upcoming_games(days_ahead=7, scan_range=1)

    if alerts:
        message = "Game in 1 week!\n\n" + "\n\n".join(alerts)
        send_sms(message)
        print(f"Sent {len(alerts)} game alert(s).")
    else:
        print("No games in 7 days.")


if __name__ == "__main__":
    main()
