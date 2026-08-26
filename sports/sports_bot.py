#!/usr/bin/env python3
"""
Major Sporting Events SMS Bot

Texts a heads-up when a major event is coming up: once a few days out,
then again the morning it starts. Silent on days with nothing to report.

Covers the Olympics, tennis and golf majors, motor racing, horse racing,
cycling, and US league championships. Events live in events.json.

Usage:
    python sports_bot.py              send today's alerts, if any
    python sports_bot.py --dry-run    print what would send, send nothing
    python sports_bot.py --date DATE  pretend today is DATE (YYYY-MM-DD)
    python sports_bot.py --check      validate the calendar, send nothing
"""

import smtplib
import json
import os
import sys
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Verizon's vtext gateway drops or truncates past 160 characters, so each
# text is packed to stay under this.
MAX_SMS_LENGTH = 150

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Days before an event to send the advance warning
LEAD_DAYS = 3

# Warn from --check when the calendar runs dry sooner than this
STALE_AFTER_DAYS = 120

EASTERN = ZoneInfo("America/New_York")
SCRIPT_DIR = Path(__file__).parent
EVENTS_FILE = SCRIPT_DIR / "events.json"


def load_events():
    """Load events, sorted by start date."""
    with open(EVENTS_FILE, "r") as f:
        events = json.load(f)["events"]
    for e in events:
        e["start_date"] = date.fromisoformat(e["start"])
    return sorted(events, key=lambda e: e["start_date"])


def today_eastern():
    return datetime.now(EASTERN).date()


def describe(event, days_out):
    """One line describing an event, e.g. '[TODAY] The Masters (Golf major)'."""
    when = "TODAY" if days_out == 0 else f"IN {days_out} DAYS"
    approx = "" if event.get("exact", True) else " approx"
    line = f"[{when}{approx}] {event['name']} ({event['category']})"
    venue = event.get("venue")
    if venue:
        line += f" - {venue}"
    return line


def alerts_for(events, today):
    """Lines for every event starting today or exactly LEAD_DAYS out."""
    lines = []
    for e in events:
        days_out = (e["start_date"] - today).days
        if days_out in (0, LEAD_DAYS):
            lines.append(describe(e, days_out))
    return lines


def pack(lines, limit=MAX_SMS_LENGTH):
    """Pack lines into as few messages as possible, each within the limit."""
    messages = []
    current = ""
    for line in lines:
        line = line[:limit]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                messages.append(current)
            current = line
    if current:
        messages.append(current)
    return messages


def send_sms(message):
    """Send SMS via email-to-SMS gateway."""
    if not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_PASSWORD is not set.")

    msg = MIMEText(message)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = SMS_EMAIL
    msg["Subject"] = ""

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


def check_calendar():
    """Validate the calendar and report when it needs topping up."""
    events = load_events()
    today = today_eastern()
    future = [e for e in events if e["start_date"] >= today]

    print(f"Events in calendar: {len(events)}")
    print(f"Still upcoming:     {len(future)}")

    problems = 0
    for e in events:
        if len(describe(e, 0)) > MAX_SMS_LENGTH:
            print(f"TOO LONG: {e['name']}")
            problems += 1
        if any(ord(c) > 126 for c in e["name"] + e.get("venue", "")):
            print(f"NON-ASCII: {e['name']}")
            problems += 1

    if not future:
        print("EMPTY: no future events left. Add more to events.json.")
        problems += 1
    else:
        last = future[-1]["start_date"]
        runway = (last - today).days
        print(f"Calendar runs through {last} ({runway} days out)")
        if runway < STALE_AFTER_DAYS:
            # A warning, not a failure. A thinning calendar must never block
            # the alerts that are still valid.
            print(f"WARNING: under {STALE_AFTER_DAYS} days of runway left. "
                  f"Add more events to events.json.")
        print("\nNext up:")
        for e in future[:5]:
            days = (e["start_date"] - today).days
            print(f"  {e['start_date']}  (in {days:>4} days)  {e['name']}")

    approx = [e for e in future if not e.get("exact", True)]
    if approx:
        print(f"\n{len(approx)} upcoming dates are estimates, worth confirming:")
        for e in approx:
            print(f"  {e['start_date']}  {e['name']}")

    return 1 if problems else 0


def run(today, dry_run=False):
    events = load_events()
    lines = alerts_for(events, today)

    if not lines:
        print(f"{today}: nothing to report.")
        return 0

    for message in pack(lines):
        if dry_run:
            print(f"[DRY RUN] ({len(message)} chars)\n{message}\n")
        else:
            send_sms(message)
            print(f"Sent ({len(message)} chars):\n{message}\n")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--check" in args:
        sys.exit(check_calendar())

    when = today_eastern()
    if "--date" in args:
        when = date.fromisoformat(args[args.index("--date") + 1])

    sys.exit(run(when, dry_run="--dry-run" in args))
