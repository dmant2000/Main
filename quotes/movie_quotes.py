#!/usr/bin/env python3
"""
Movie Quote SMS Bot
Sends a daily movie quote via text message (email-to-SMS gateway)

Run with --check to validate quotes.json and print rotation coverage
without sending anything.
"""

import smtplib
import random
import json
import os
import sys
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Verizon's vtext gateway drops or truncates anything past 160 characters.
# Cap the whole formatted body below that so every quote actually arrives.
MAX_SMS_LENGTH = 150

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Paths
SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "quotes.json"


def load_quotes():
    """Load quotes from JSON file."""
    with open(QUOTES_FILE, "r") as f:
        return json.load(f)


def save_quotes(quotes):
    """Save quotes back to JSON file."""
    with open(QUOTES_FILE, "w") as f:
        json.dump(quotes, f, indent=4)
        f.write("\n")


def format_message(quote):
    """Format quote for SMS. Facts are stated plainly, not quoted."""
    if quote.get("source") == "Fact":
        return f'{quote["quote"]}\n- {quote["character"]}'
    return f'"{quote["quote"]}"\n- {quote["character"]}'


def is_sendable(quote):
    """True if the formatted quote fits in a single SMS."""
    return len(format_message(quote)) <= MAX_SMS_LENGTH


def get_unused_quote(quotes):
    """Get a random unused quote. Resets all if every quote has been used."""
    sendable = [q for q in quotes if is_sendable(q)]
    if not sendable:
        raise ValueError("No quotes short enough to send.")

    unused = [q for q in sendable if not q["used"]]
    if not unused:
        for q in quotes:
            q["used"] = False
        unused = sendable
        print("All quotes used - reset cycle.")
    return random.choice(unused)


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

    print(f"SMS sent at {datetime.now().strftime('%Y-%m-%d %H:%M')}")


def check_quotes():
    """Report rotation coverage and flag anything that can't be delivered."""
    quotes = load_quotes()
    too_long = [q for q in quotes if not is_sendable(q)]

    seen = {}
    duplicates = []
    for q in quotes:
        key = q["quote"].strip().lower()
        if key in seen:
            duplicates.append(q)
        seen[key] = True

    sendable = [q for q in quotes if is_sendable(q)]
    used = [q for q in sendable if q["used"]]

    print(f"Total quotes:    {len(quotes)}")
    print(f"Sendable:        {len(sendable)}")
    print(f"Used this cycle: {len(used)}")
    print(f"Remaining:       {len(sendable) - len(used)}")
    if sendable:
        print(f"Longest:         {max(len(format_message(q)) for q in sendable)}"
              f" / {MAX_SMS_LENGTH} chars")

    for q in too_long:
        print(f"TOO LONG ({len(format_message(q))} chars): "
              f"{q['character']} - {q['quote'][:60]}...")
    for q in duplicates:
        print(f"DUPLICATE: {q['quote'][:60]}...")

    return 1 if (too_long or duplicates) else 0


def send_quote():
    """Pick a random unused quote and text it."""
    quotes = load_quotes()
    quote = get_unused_quote(quotes)

    message = format_message(quote)
    send_sms(message)

    quote["used"] = True
    save_quotes(quotes)
    print(f"Sent ({len(message)} chars): {quote['quote'][:50]}...")


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check_quotes())
    send_quote()
