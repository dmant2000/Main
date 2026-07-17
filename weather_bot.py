#!/usr/bin/env python3
"""
Weather SMS Bot
Sends a morning weather brief and rain alerts via text message.

Uses Open-Meteo API (free, no API key required).
Runs via GitHub Actions cron:
  - Morning brief at 7:00 AM ET
  - Rain checks every 30 minutes during the day

Uses the same email-to-SMS gateway as the March Madness bot.
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

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Location — defaults to Washington DC
LATITUDE = float(os.environ.get("WEATHER_LAT", "38.9072"))
LONGITUDE = float(os.environ.get("WEATHER_LON", "-77.0369"))
LOCATION_NAME = os.environ.get("WEATHER_LOCATION", "DC")

SCRIPT_DIR = Path(__file__).parent
RAIN_ALERT_FILE = SCRIPT_DIR / "last_rain_alert.json"

ET = timezone(timedelta(hours=-4))

WMO_CODES = {
    0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    66: "Freezing Rain", 67: "Heavy Freezing Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Showers", 81: "Showers", 82: "Heavy Showers",
    85: "Light Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Severe Thunderstorm",
}

RAIN_CODES = {51, 53, 55, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


def api_get(url):
    req = Request(url)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"API error: {e}")
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


def get_forecast():
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"precipitation_probability_max,weathercode,sunrise,sunset,uv_index_max,"
        f"windspeed_10m_max"
        f"&hourly=temperature_2m,precipitation_probability,weathercode,precipitation"
        f"&temperature_unit=fahrenheit"
        f"&windspeed_unit=mph"
        f"&precipitation_unit=inch"
        f"&timezone=America/New_York"
        f"&forecast_days=1"
    )
    return api_get(url)


def format_morning_brief(data):
    daily = data["daily"]
    hourly = data["hourly"]

    high = round(daily["temperature_2m_max"][0])
    low = round(daily["temperature_2m_min"][0])
    precip_chance = daily["precipitation_probability_max"][0]
    precip_total = daily["precipitation_sum"][0]
    code = daily["weathercode"][0]
    condition = WMO_CODES.get(code, "Unknown")
    wind = round(daily["windspeed_10m_max"][0])
    uv = round(daily["uv_index_max"][0])

    sunrise = daily["sunrise"][0].split("T")[1]
    sunset = daily["sunset"][0].split("T")[1]

    now_et = datetime.now(ET)
    date_str = now_et.strftime("%A, %b %d")

    # Find rain windows
    rain_windows = []
    in_rain = False
    rain_start = None
    for i, (time_str, prob, wcode, precip) in enumerate(zip(
        hourly["time"], hourly["precipitation_probability"],
        hourly["weathercode"], hourly["precipitation"]
    )):
        hour = datetime.fromisoformat(time_str)
        is_rain = wcode in RAIN_CODES or (prob >= 50 and precip > 0)
        if is_rain and not in_rain:
            rain_start = hour
            in_rain = True
        elif not is_rain and in_rain:
            rain_windows.append((rain_start, hour))
            in_rain = False
    if in_rain:
        rain_windows.append((rain_start, None))

    lines = [
        f"{LOCATION_NAME} Weather - {date_str}",
        f"{condition} | {high}°/{low}°F",
        f"Wind: {wind}mph | UV: {uv}",
        f"Sunrise {sunrise} | Sunset {sunset}",
    ]

    if precip_chance > 20:
        lines.append(f"Rain: {precip_chance}% chance, {precip_total}\" expected")

    if rain_windows:
        for start, end in rain_windows:
            s = start.strftime("%-I%p").lower()
            if end:
                e = end.strftime("%-I%p").lower()
                lines.append(f"Rain {s}-{e}")
            else:
                lines.append(f"Rain from {s}")
    elif precip_chance <= 20:
        lines.append("No rain expected")

    return "\n".join(lines)


def check_rain_ahead(data):
    """Check if rain starts in the next 30-60 minutes."""
    hourly = data["hourly"]
    now_et = datetime.now(ET)

    for i, (time_str, wcode, precip, prob) in enumerate(zip(
        hourly["time"], hourly["weathercode"],
        hourly["precipitation"], hourly["precipitation_probability"]
    )):
        hour = datetime.fromisoformat(time_str)
        minutes_away = (hour - now_et.replace(tzinfo=None)).total_seconds() / 60

        if 20 <= minutes_away <= 75:
            is_rain = wcode in RAIN_CODES or (prob >= 60 and precip > 0)
            if is_rain:
                return hour, WMO_CODES.get(wcode, "Rain"), prob
    return None, None, None


def load_last_alert():
    if RAIN_ALERT_FILE.exists():
        try:
            with open(RAIN_ALERT_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_last_alert(alert_time):
    with open(RAIN_ALERT_FILE, "w") as f:
        json.dump({"last_alert": alert_time}, f)


def run_morning_brief():
    print(f"Fetching forecast for {LOCATION_NAME}...")
    data = get_forecast()
    if not data:
        print("Failed to fetch forecast")
        return

    brief = format_morning_brief(data)
    print(f"Morning brief:\n{brief}")
    send_sms(brief)


def run_rain_check():
    print(f"Checking rain for {LOCATION_NAME}...")
    data = get_forecast()
    if not data:
        print("Failed to fetch forecast")
        return

    rain_time, condition, prob = check_rain_ahead(data)
    if not rain_time:
        print("No rain coming soon")
        return

    last = load_last_alert()
    rain_key = rain_time.strftime("%Y-%m-%d %H:00")
    if last.get("last_alert") == rain_key:
        print(f"Already alerted for {rain_key}")
        return

    now_et = datetime.now(ET)
    mins = round((rain_time - now_et.replace(tzinfo=None)).total_seconds() / 60)
    time_str = rain_time.strftime("%-I:%M%p").lower()

    msg = f"Rain alert - {LOCATION_NAME}\n{condition} at {time_str} (~{mins} min)\nGrab an umbrella!"
    print(f"Rain alert:\n{msg}")
    send_sms(msg)
    save_last_alert(rain_key)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "brief"

    if mode == "brief":
        run_morning_brief()
    elif mode == "rain":
        run_rain_check()
    else:
        print(f"Usage: python weather_bot.py [brief|rain]")
        sys.exit(1)
