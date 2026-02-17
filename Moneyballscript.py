#!/usr/bin/env python3
"""
Moneyball Quote SMS Bot
Sends a daily Moneyball quote via text message (email-to-SMS gateway)
"""

import smtplib
import random
import json
import os
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "ydws boof sawz duwn")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Paths
SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "moneyball_quotes.json"


def load_quotes():
    """Load quotes from JSON file."""
    with open(QUOTES_FILE, "r") as f:
        return json.load(f)


def save_quotes(quotes):
    """Save quotes back to JSON file."""
    with open(QUOTES_FILE, "w") as f:
        json.dump(quotes, f, indent=4)


def get_unused_quote(quotes):
    """Get a random unused quote. Resets all if every quote has been used."""
    unused = [q for q in quotes if not q["used"]]
    if not unused:
        for q in quotes:
            q["used"] = False
        unused = quotes
        print("All quotes used — reset cycle.")
    return random.choice(unused)


def format_message(quote):
    """Format quote for SMS."""
    return f'"{quote["quote"]}"\n- {quote["character"]}'


def send_sms(message):
    """Send SMS via email-to-SMS gateway."""
    msg = MIMEText(message)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = SMS_EMAIL
    msg["Subject"] = ""

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"SMS sent at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


def send_quote():
    """Pick a random unused quote and text it."""
    quotes = load_quotes()
    quote = get_unused_quote(quotes)

    message = format_message(quote)
    send_sms(message)

    quote["used"] = True
    save_quotes(quotes)
    print(f"Sent: {quote['quote'][:50]}...")


if __name__ == "__main__":
    send_quote()
