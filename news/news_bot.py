#!/usr/bin/env python3
"""
Morning News Digest SMS Bot
Sends a daily text with the top 10 headlines, categorized by topic,
plus any major earnings reports happening that day.

Uses Google News RSS (free, no API key) and Finnhub for earnings calendar.
Runs via GitHub Actions cron at 7:30 AM ET.
"""

import smtplib
import json
import os
import sys
import re
import xml.etree.ElementTree as ET
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from html import unescape

# SMS Configuration
PHONE_NUMBER = "7178476602"
SMS_GATEWAY = "vtext.com"
SMS_EMAIL = f"{PHONE_NUMBER}@{SMS_GATEWAY}"

# Yahoo Mail Configuration
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "dmant2000@yahoo.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.mail.yahoo.com"
SMTP_PORT = 465

# Finnhub API for earnings calendar (free tier - get key at finnhub.io)
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")

ET_TZ = timezone(timedelta(hours=-4))

# Major capex spenders / market movers to watch for earnings
CAPEX_TICKERS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Google", "GOOG": "Google",
    "AMZN": "Amazon", "META": "Meta", "NVDA": "NVIDIA", "TSLA": "Tesla",
    "AMD": "AMD", "INTC": "Intel", "CRM": "Salesforce", "ORCL": "Oracle",
    "AVGO": "Broadcom", "ADBE": "Adobe", "NOW": "ServiceNow", "SNOW": "Snowflake",
    "NFLX": "Netflix", "DIS": "Disney", "CMCSA": "Comcast", "T": "AT&T",
    "VZ": "Verizon", "UBER": "Uber", "ABNB": "Airbnb", "SHOP": "Shopify",
    "SQ": "Block", "COIN": "Coinbase", "PLTR": "Palantir", "AI": "C3.ai",
    "JPM": "JPMorgan", "GS": "Goldman Sachs", "MS": "Morgan Stanley",
    "BAC": "Bank of America", "WMT": "Walmart", "COST": "Costco",
    "HD": "Home Depot", "LOW": "Lowe's", "TGT": "Target",
    "XOM": "Exxon", "CVX": "Chevron", "BA": "Boeing", "LMT": "Lockheed",
    "RTX": "RTX/Raytheon", "GE": "GE Aerospace", "CAT": "Caterpillar",
    "DE": "John Deere", "UNH": "UnitedHealth", "JNJ": "Johnson & Johnson",
    "PFE": "Pfizer", "LLY": "Eli Lilly", "MRNA": "Moderna",
    "TSM": "TSMC", "ASML": "ASML", "ARM": "Arm Holdings",
}

# Category keywords for tagging headlines
CATEGORIES = {
    "AI": [
        "artificial intelligence", " ai ", "chatgpt", "openai", "claude",
        "anthropic", "deepmind", "machine learning", "neural", "llm",
        "generative ai", "nvidia", "gpu", "chatbot", "copilot",
    ],
    "GEO": [
        "ukraine", "russia", "china", "taiwan", "nato", "sanctions",
        "missile", "military", "troops", "invasion", "war ", "conflict",
        "iran", "israel", "gaza", "hamas", "hezbollah", "north korea",
        "diplomacy", "summit", "tariff", "trade war", "geopolit",
    ],
    "DISASTER": [
        "earthquake", "hurricane", "tornado", "wildfire", "flood",
        "tsunami", "volcanic", "eruption", "cyclone", "typhoon",
        "disaster", "emergency declaration", "evacuation", "death toll",
        "storm", "devastat",
    ],
    "EARNINGS": [
        "earnings", "revenue", "quarterly results", "beat estimates",
        "missed expectations", "profit", "guidance", "forecast",
        "wall street", "stock", "shares",
    ],
    "MARKETS": [
        "dow jones", "s&p 500", "nasdaq", "fed ", "federal reserve",
        "interest rate", "inflation", "recession", "ipo", "market",
    ],
}


def fetch_url(url):
    headers = {"User-Agent": "Mozilla/5.0 (NewsBot/1.0)"}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"Fetch error for {url}: {e}")
        return None


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


def clean_title(title):
    """Clean up RSS title text."""
    title = unescape(title)
    # Remove source suffix like " - CNN" or " | Reuters"
    title = re.sub(r'\s*[-|]\s*[A-Z][A-Za-z\s.]+$', '', title)
    return title.strip()


def categorize(title):
    """Tag a headline with categories."""
    lower = f" {title.lower()} "
    tags = []
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in lower:
                tags.append(cat)
                break
    return tags


def fetch_google_news():
    """Fetch top headlines from Google News RSS."""
    url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    xml_text = fetch_url(url)
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"XML parse error: {e}")
        return []

    headlines = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            title = clean_title(title_el.text)
            tags = categorize(title)
            headlines.append({"title": title, "tags": tags})

    return headlines


def fetch_category_news(query, limit=5):
    """Fetch headlines for a specific search query from Google News."""
    encoded = query.replace(" ", "+")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    xml_text = fetch_url(url)
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    headlines = []
    for item in root.findall(".//item")[:limit]:
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            title = clean_title(title_el.text)
            headlines.append(title)

    return headlines


def fetch_earnings_today():
    """Check if any major capex spenders report earnings today."""
    if not FINNHUB_KEY:
        print("No Finnhub API key — skipping earnings check")
        return []

    today = datetime.now(ET_TZ).strftime("%Y-%m-%d")
    url = (
        f"https://finnhub.io/api/v1/calendar/earnings?"
        f"from={today}&to={today}&token={FINNHUB_KEY}"
    )
    data = api_get(url)
    if not data:
        return []

    reporting = []
    for entry in data.get("earningsCalendar", []):
        symbol = entry.get("symbol", "")
        if symbol in CAPEX_TICKERS:
            name = CAPEX_TICKERS[symbol]
            hour = entry.get("hour", "")
            timing = "before open" if hour == "bmo" else "after close" if hour == "amc" else ""
            est_eps = entry.get("epsEstimate")
            est_rev = entry.get("revenueEstimate")

            info = f"{name} ({symbol})"
            if timing:
                info += f" {timing}"
            if est_rev:
                rev_b = est_rev / 1_000_000_000
                info += f" | Est Rev: ${rev_b:.1f}B"

            reporting.append(info)

    return reporting


def build_digest():
    """Build the morning news digest."""
    now = datetime.now(ET_TZ)
    date_str = now.strftime("%a %b %d")

    print("Fetching top headlines...")
    headlines = fetch_google_news()

    # Also fetch category-specific news to ensure coverage
    print("Fetching AI news...")
    ai_news = fetch_category_news("artificial intelligence technology", 3)

    print("Fetching geopolitical news...")
    geo_news = fetch_category_news("geopolitical world conflict diplomacy", 3)

    # Deduplicate by checking if title already exists
    seen_titles = {h["title"].lower()[:40] for h in headlines}

    for title in ai_news:
        key = title.lower()[:40]
        if key not in seen_titles:
            headlines.append({"title": title, "tags": ["AI"]})
            seen_titles.add(key)

    for title in geo_news:
        key = title.lower()[:40]
        if key not in seen_titles:
            headlines.append({"title": title, "tags": ["GEO"]})
            seen_titles.add(key)

    # Prioritize: tagged headlines first, then general
    tagged = [h for h in headlines if h["tags"]]
    untagged = [h for h in headlines if not h["tags"]]

    # Build final top 10: mix of tagged + top general
    final = []
    seen = set()

    # Add tagged headlines first (prioritize AI, GEO, DISASTER)
    for h in tagged:
        key = h["title"].lower()[:40]
        if key not in seen and len(final) < 10:
            final.append(h)
            seen.add(key)

    # Fill remaining with top general headlines
    for h in untagged:
        key = h["title"].lower()[:40]
        if key not in seen and len(final) < 10:
            final.append(h)
            seen.add(key)

    # Check earnings
    print("Checking earnings calendar...")
    earnings = fetch_earnings_today()

    # Format the text
    lines = [f"Morning Brief - {date_str}"]
    lines.append("")

    for i, h in enumerate(final[:10], 1):
        tag_str = ""
        if h["tags"]:
            tag_str = " [" + "/".join(h["tags"][:2]) + "]"
        # Truncate long headlines for SMS
        title = h["title"]
        if len(title) > 100:
            title = title[:97] + "..."
        lines.append(f"{i}. {title}{tag_str}")

    if earnings:
        lines.append("")
        lines.append("EARNINGS TODAY:")
        for e in earnings:
            lines.append(f"- {e}")

    return "\n".join(lines)


def fetch_earnings_results():
    """Fetch actual earnings results for major companies that reported today."""
    if not FINNHUB_KEY:
        print("No Finnhub API key — skipping earnings results")
        return []

    today = datetime.now(ET_TZ).strftime("%Y-%m-%d")
    url = (
        f"https://finnhub.io/api/v1/calendar/earnings?"
        f"from={today}&to={today}&token={FINNHUB_KEY}"
    )
    data = api_get(url)
    if not data:
        return []

    results = []
    for entry in data.get("earningsCalendar", []):
        symbol = entry.get("symbol", "")
        if symbol not in CAPEX_TICKERS:
            continue

        name = CAPEX_TICKERS[symbol]
        actual_eps = entry.get("epsActual")
        est_eps = entry.get("epsEstimate")
        actual_rev = entry.get("revenueActual")
        est_rev = entry.get("revenueEstimate")

        # Only include if we have actual results (they've reported)
        if actual_eps is None and actual_rev is None:
            continue

        line = f"{name} ({symbol})"

        # EPS beat/miss
        if actual_eps is not None and est_eps is not None:
            diff = actual_eps - est_eps
            if diff > 0:
                line += f" BEAT EPS ${actual_eps:.2f} vs ${est_eps:.2f} est"
            elif diff < 0:
                line += f" MISSED EPS ${actual_eps:.2f} vs ${est_eps:.2f} est"
            else:
                line += f" MET EPS ${actual_eps:.2f}"
        elif actual_eps is not None:
            line += f" EPS ${actual_eps:.2f}"

        # Revenue
        if actual_rev is not None:
            rev_b = actual_rev / 1_000_000_000
            if est_rev is not None:
                est_b = est_rev / 1_000_000_000
                if actual_rev > est_rev:
                    line += f" | Rev ${rev_b:.1f}B (beat ${est_b:.1f}B)"
                else:
                    line += f" | Rev ${rev_b:.1f}B (miss ${est_b:.1f}B)"
            else:
                line += f" | Rev ${rev_b:.1f}B"

        results.append(line)

    return results


def fetch_after_hours_headlines():
    """Fetch earnings-related headlines for after-hours context."""
    headlines = fetch_category_news("earnings results quarterly report", 5)
    # Filter to only headlines mentioning companies we track
    relevant = []
    for h in headlines:
        lower = h.lower()
        for ticker, name in CAPEX_TICKERS.items():
            if name.lower() in lower or ticker.lower() in lower.split():
                relevant.append(h)
                break
    return relevant[:3]


def build_evening_earnings():
    """Build the evening earnings results text."""
    now = datetime.now(ET_TZ)
    date_str = now.strftime("%a %b %d")

    print("Fetching earnings results...")
    results = fetch_earnings_results()

    print("Fetching earnings headlines...")
    headlines = fetch_after_hours_headlines()

    if not results and not headlines:
        print("No major earnings today — skipping text")
        return None

    lines = [f"Earnings Wrap - {date_str}"]
    lines.append("")

    if results:
        for r in results:
            lines.append(f"- {r}")
    elif headlines:
        lines.append("Major earnings reported:")

    if headlines:
        lines.append("")
        for h in headlines:
            title = h if len(h) <= 100 else h[:97] + "..."
            lines.append(f"- {title}")

    return "\n".join(lines)


def run_morning():
    digest = build_digest()
    print(f"\n{digest}\n")
    send_sms(digest)


def run_evening():
    text = build_evening_earnings()
    if text:
        print(f"\n{text}\n")
        send_sms(text)
    else:
        print("No major earnings to report tonight")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"

    if mode == "morning":
        run_morning()
    elif mode == "evening":
        run_evening()
    else:
        print("Usage: python news_bot.py [morning|evening]")
        sys.exit(1)
