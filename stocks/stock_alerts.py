#!/usr/bin/env python3
"""
Stock 200-Week Moving Average Alert System
Sends SMS alerts via email when Mag 7 or Top 10 stocks hit their 200-week MA
"""

import yfinance as yf
import smtplib
import json
import os
import subprocess
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"  # Xfinity Mobile uses Verizon's network
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Email configuration - shared with every other bot in this repo
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465


# Stocks to monitor
MAG_7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
TOP_10 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V"]
ADDITIONAL = ["UNH", "INTC", "ZETA", "OSCR", "GRAB", "LULU", "HIMS"]

# Combine and deduplicate
STOCKS_TO_MONITOR = list(set(MAG_7 + TOP_10 + ADDITIONAL))

# Alert threshold - how close to 200-week MA triggers alert (percentage)
MA_THRESHOLD = 3.0  # Alert when within 3% of 200-week MA

# State file to avoid duplicate alerts
STATE_FILE = Path(__file__).parent / "alert_state.json"


def load_state():
    """Load previous alert state to avoid duplicates."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"alerted": {}, "last_run": None}


def save_state(state):
    """Save alert state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_200_week_ma(symbol):
    """Fetch stock data and calculate 200-week moving average."""
    try:
        stock = yf.Ticker(symbol)
        # Get 5 years of weekly data (enough for 200-week MA)
        hist = stock.history(period="5y", interval="1wk")

        if len(hist) < 200:
            print(f"  ⚠️  {symbol}: Not enough data ({len(hist)} weeks)")
            return None, None, None

        # Calculate 200-week MA
        hist["MA200"] = hist["Close"].rolling(window=200).mean()

        current_price = hist["Close"].iloc[-1]
        ma_200 = hist["MA200"].iloc[-1]

        if ma_200 is None or current_price is None:
            return None, None, None

        pct_from_ma = ((current_price - ma_200) / ma_200) * 100

        return current_price, ma_200, pct_from_ma

    except Exception as e:
        print(f"  ❌ Error fetching {symbol}: {e}")
        return None, None, None


def send_sms(subject, message, attempts=4):
    """Send SMS via email-to-SMS gateway.

    Raises on total failure so the workflow surfaces the problem instead of
    reporting success on a message that never went out.
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("EMAIL_ADDRESS/EMAIL_PASSWORD not set")

    msg = MIMEText(message)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = SMS_EMAIL
    msg["Subject"] = ""

    for attempt in range(1, attempts + 1):
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            print(f"  📱 SMS sent: {subject}")
            return True
        except (smtplib.SMTPException, OSError) as e:
            print(f"  Attempt {attempt}/{attempts} failed: {type(e).__name__}: {e}")
            if attempt == attempts:
                raise
            delay = 15 * (2 ** (attempt - 1))
            print(f"  Retrying in {delay}s...")
            time.sleep(delay)


def send_alert(subject, message):
    """Send alert via SMS."""
    return send_sms(subject, message)


def check_stocks():
    """Check all monitored stocks and send alerts if near 200-week MA."""
    print(f"\n{'='*60}")
    print(f"Stock 200-Week MA Alert Check - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    state = load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    stocks_to_alert = []  # Collect all stocks to alert

    for symbol in STOCKS_TO_MONITOR:
        print(f"\nChecking {symbol}...")

        current_price, ma_200, pct_from_ma = get_200_week_ma(symbol)

        if current_price is None:
            continue

        print(f"  Price: ${current_price:.2f} | 200-Week MA: ${ma_200:.2f} | Distance: {pct_from_ma:+.2f}%")

        # Check if near or below 200-week MA
        if pct_from_ma <= MA_THRESHOLD:
            # Check if we already alerted today
            last_alert = state["alerted"].get(symbol, {}).get("date")
            last_pct = state["alerted"].get(symbol, {}).get("pct", 999)

            # Alert if: new day, or significantly closer to MA (2% closer)
            should_alert = (last_alert != today) or (pct_from_ma < last_pct - 2)

            if should_alert:
                if pct_from_ma <= 0:
                    status = "BELOW"
                else:
                    status = "NEAR"

                stocks_to_alert.append({
                    "symbol": symbol,
                    "status": status,
                    "price": current_price,
                    "ma_200": ma_200,
                    "pct": pct_from_ma
                })
            else:
                print(f"  ℹ️  Already alerted today")
        else:
            # Clear old alert state if stock moved away from MA
            if symbol in state["alerted"]:
                if pct_from_ma > MA_THRESHOLD + 5:  # 5% buffer before clearing
                    del state["alerted"][symbol]
                    print(f"  ✓ Cleared previous alert state")

    # Send combined alert for all stocks
    alerts_sent = 0
    if stocks_to_alert:
        # Sort by percentage (most below first)
        stocks_to_alert.sort(key=lambda x: x["pct"])

        # Build combined message (stacked, one per line)
        lines = []
        for stock in stocks_to_alert:
            lines.append(f"{stock['symbol']} ${stock['price']:.0f} ({stock['pct']:+.0f}%)")

        subject = ""
        message = f"{len(stocks_to_alert)} Below 200-Wk MA:\n" + "\n".join(lines)

        if send_alert(subject, message):
            # Update state for all alerted stocks
            for stock in stocks_to_alert:
                state["alerted"][stock["symbol"]] = {
                    "date": today,
                    "pct": stock["pct"],
                    "price": stock["price"]
                }
            alerts_sent = len(stocks_to_alert)
    else:
        send_sms("", "No stocks near 200-week MA today")

    state["last_run"] = datetime.now().isoformat()
    save_state(state)

    print(f"\n{'='*60}")
    print(f"Check complete. {alerts_sent} stocks in alert.")
    print(f"{'='*60}\n")

    return alerts_sent


def show_current_status():
    """Show current status of all monitored stocks."""
    print(f"\n{'='*60}")
    print(f"Current Stock Status - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"{'Symbol':<8} {'Price':>10} {'200-Wk MA':>12} {'Distance':>10}")
    print(f"{'-'*8} {'-'*10} {'-'*12} {'-'*10}")

    results = []
    for symbol in STOCKS_TO_MONITOR:
        current_price, ma_200, pct_from_ma = get_200_week_ma(symbol)
        if current_price:
            results.append((symbol, current_price, ma_200, pct_from_ma))

    # Sort by distance from MA (closest first)
    results.sort(key=lambda x: x[3])

    for symbol, price, ma, pct in results:
        indicator = "🔴" if pct <= 0 else "🟡" if pct <= MA_THRESHOLD else "🟢"
        print(f"{indicator} {symbol:<6} ${price:>9.2f} ${ma:>11.2f} {pct:>+9.1f}%")

    print(f"\n🔴 = Below MA | 🟡 = Within {MA_THRESHOLD}% | 🟢 = Above threshold")


def is_weekend():
    """Check if today is Saturday or Sunday."""
    return datetime.now().weekday() >= 5  # 5=Saturday, 6=Sunday


def already_ran_today():
    """Check if we already ran today."""
    state = load_state()
    last_run = state.get("last_run")
    if not last_run:
        return False

    last_run_date = datetime.fromisoformat(last_run).date()
    today = datetime.now().date()
    return last_run_date == today


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        show_current_status()
    elif len(sys.argv) > 1 and sys.argv[1] == "force":
        # Force run even if already ran today
        check_stocks()
    else:
        # Skip weekends
        if is_weekend():
            print("Skipping - market closed on weekends")
        elif already_ran_today():
            print("Already ran today. Use 'force' argument to run anyway.")
        else:
            check_stocks()
