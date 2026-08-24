#!/usr/bin/env python3
"""
Red Light Therapy Reminder
Texts every other day when it's a therapy day (email-to-SMS gateway)
"""

import smtplib
import os
import sys
import time
from email.mime.text import MIMEText
from datetime import date, datetime

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Anchor date - a known therapy day. Therapy happens every 2 days from here.
ANCHOR_DATE = date(2026, 7, 22)


def is_therapy_day(today=None):
    """True if today falls on the every-other-day cycle from the anchor date."""
    today = today or date.today()
    return (today - ANCHOR_DATE).days % 2 == 0


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
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        today = date.today()
        for offset in range(7):
            d = date.fromordinal(today.toordinal() + offset)
            status = "THERAPY DAY" if is_therapy_day(d) else "rest day"
            print(f"{d.strftime('%a %b %d')}: {status}")
        return

    if is_therapy_day():
        send_sms("Red light therapy day!")
        print("Therapy day - text sent.")
    else:
        print("Rest day - no text.")


if __name__ == "__main__":
    main()
