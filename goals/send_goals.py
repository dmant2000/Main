#!/usr/bin/env python3
"""
Daily Goals SMS Bot
Sends daily goals via text message (email-to-SMS gateway)
"""

import smtplib
import json
import os
import time
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Paths
SCRIPT_DIR = Path(__file__).parent
GOALS_FILE = SCRIPT_DIR / "goals.json"


def load_goals():
    """Load goals from JSON file."""
    with open(GOALS_FILE, "r") as f:
        return json.load(f)


def format_message(goals):
    """Format goals as a numbered top-down list."""
    lines = [f"{i}. {goal}" for i, goal in enumerate(goals, 1)]
    return "Yearly Goals:\n" + "\n".join(lines)


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


def send_goals():
    """Load goals and text them."""
    goals = load_goals()
    message = format_message(goals)
    send_sms(message)
    print("Goals sent!")


if __name__ == "__main__":
    send_goals()
