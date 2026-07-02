#!/usr/bin/env python3
"""Export iPhone text/call history to Kindred's CSV format.

iOS apps are sandboxed away from the Messages and call-log databases, so this
script extracts them from the two places Apple *does* let you get at them:

  mac     — a Mac your iPhone syncs Messages/calls to:
              ~/Library/Messages/chat.db
              ~/Library/Application Support/CallHistoryDB/CallHistory.storedata
  backup  — a local iPhone backup made with Finder/iTunes (must be
            unencrypted), which contains sms.db and CallHistory.storedata.

Usage:
  python3 export_comms.py mac -o kindred.csv
  python3 export_comms.py backup ~/Library/Application\\ Support/MobileSync/Backup/<UDID> -o kindred.csv

Then AirDrop / copy kindred.csv to your iPhone and import it in the Kindred
app (or the web app). Everything runs locally; nothing is uploaded.

macOS note: give your terminal "Full Disk Access" (System Settings → Privacy &
Security) or the Messages database will be unreadable.
"""

import argparse
import csv
import datetime
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

APPLE_EPOCH_OFFSET = 978307200  # 2001-01-01 00:00:00 UTC in Unix seconds

# Well-known file IDs inside an iPhone backup (SHA-1 of "domain-relativePath");
# resolved via Manifest.db, with these as a fallback for odd backups.
BACKUP_FILES = {
    "sms": ("HomeDomain", "Library/SMS/sms.db",
            "3d0d7e5fb2ce288813306e4d4636395e047a3d28"),
    "calls": ("HomeDomain", "Library/CallHistoryDB/CallHistory.storedata",
              "5a4935c78a5255723f707230a451d79c540d2741"),
}


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def apple_time_to_unix(value):
    """Apple databases store dates as seconds — or, in newer iOS versions,
    nanoseconds — since 2001-01-01. Normalize to Unix seconds."""
    if value is None:
        return None
    value = float(value)
    if abs(value) > 1e12:  # nanoseconds
        value /= 1e9
    return value + APPLE_EPOCH_OFFSET


def iso_utc(unix_seconds):
    return datetime.datetime.fromtimestamp(
        unix_seconds, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def open_sqlite_copy(path, tmpdir):
    """Copy the database (plus WAL/SHM sidecars if present) into a temp dir
    and open the copy read-only, so live/locked databases are safe to read."""
    src = Path(path)
    if not src.exists():
        fail(f"database not found: {src}")
    dest = Path(tmpdir) / src.name
    shutil.copy2(src, dest)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(src) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(dest) + suffix))
    try:
        conn = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
        conn.execute("SELECT count(*) FROM sqlite_master")
        return conn
    except sqlite3.DatabaseError:
        fail(
            f"{src.name} is not a readable SQLite database. If this came from "
            "an iPhone backup, the backup is probably encrypted — make a new "
            "one with 'Encrypt local backup' turned off."
        )


def export_messages(conn):
    """chat.db / sms.db: one row per sent or received message."""
    rows = conn.execute(
        """
        SELECT message.date, message.is_from_me, handle.id
        FROM message
        JOIN handle ON message.handle_id = handle.ROWID
        WHERE message.date > 0 AND handle.id IS NOT NULL
        """
    )
    for date, is_from_me, address in rows:
        ts = apple_time_to_unix(date)
        if ts is None:
            continue
        yield {
            "date": iso_utc(ts),
            "kind": "text",
            "direction": "out" if is_from_me else "in",
            "contact": "",
            "number": address or "",
            "duration_seconds": "",
        }


def export_calls(conn):
    """CallHistory.storedata: Core Data store with one ZCALLRECORD per call."""
    rows = conn.execute(
        """
        SELECT ZDATE, ZDURATION, ZORIGINATED, ZANSWERED, ZADDRESS
        FROM ZCALLRECORD
        WHERE ZADDRESS IS NOT NULL
        """
    )
    for date, duration, originated, answered, address in rows:
        ts = apple_time_to_unix(date)
        if ts is None:
            continue
        if isinstance(address, bytes):
            address = address.decode("utf-8", errors="ignore")
        if originated:
            direction = "out"
        elif answered:
            direction = "in"
        else:
            direction = "missed"
        duration = int(float(duration or 0))
        yield {
            "date": iso_utc(ts),
            "kind": "call",
            "direction": direction,
            "contact": "",
            "number": address or "",
            "duration_seconds": "" if direction == "missed" else str(duration),
        }


def locate_backup_file(backup_dir, domain, relative_path, fallback_id):
    """Find a file inside a Finder/iTunes backup via Manifest.db."""
    backup = Path(backup_dir)
    manifest = backup / "Manifest.db"
    file_id = None
    if manifest.exists():
        try:
            conn = sqlite3.connect(f"file:{manifest}?mode=ro", uri=True)
            row = conn.execute(
                "SELECT fileID FROM Files WHERE domain = ? AND relativePath = ?",
                (domain, relative_path),
            ).fetchone()
            conn.close()
            if row:
                file_id = row[0]
        except sqlite3.DatabaseError:
            fail(
                "Manifest.db is unreadable — this backup is encrypted. Make a "
                "new backup with 'Encrypt local backup' turned off, or use "
                "the 'mac' mode instead."
            )
    if file_id is None:
        file_id = fallback_id
    for candidate in (backup / file_id[:2] / file_id, backup / file_id):
        if candidate.exists():
            return candidate
    return None


def write_csv(events, output):
    events = sorted(events, key=lambda e: e["date"])
    fieldnames = ["date", "kind", "direction", "contact", "number", "duration_seconds"]
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)
    texts = sum(1 for e in events if e["kind"] == "text")
    calls = len(events) - texts
    print(f"wrote {output}: {texts} texts, {calls} calls")
    if not events:
        print("warning: no events found — check the source paths", file=sys.stderr)


def run_mac(args):
    home = Path.home()
    chat_db = Path(args.chat_db or home / "Library/Messages/chat.db")
    call_db = Path(
        args.call_db
        or home / "Library/Application Support/CallHistoryDB/CallHistory.storedata"
    )
    events = []
    with tempfile.TemporaryDirectory() as tmp:
        if chat_db.exists():
            events.extend(export_messages(open_sqlite_copy(chat_db, tmp)))
        else:
            print(f"note: {chat_db} not found, skipping messages", file=sys.stderr)
        if call_db.exists():
            events.extend(export_calls(open_sqlite_copy(call_db, tmp)))
        else:
            print(f"note: {call_db} not found, skipping calls", file=sys.stderr)
    if not chat_db.exists() and not call_db.exists():
        fail("neither the Messages nor the call-history database was found")
    write_csv(events, args.output)


def run_backup(args):
    backup = Path(args.backup_dir)
    if not backup.is_dir():
        fail(f"backup directory not found: {backup}")
    events = []
    with tempfile.TemporaryDirectory() as tmp:
        for key, exporter in (("sms", export_messages), ("calls", export_calls)):
            domain, rel_path, fallback = BACKUP_FILES[key]
            found = locate_backup_file(backup, domain, rel_path, fallback)
            if found is None:
                print(f"note: {rel_path} not found in backup, skipping", file=sys.stderr)
                continue
            events.extend(exporter(open_sqlite_copy(found, tmp)))
    write_csv(events, args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    mac = sub.add_parser("mac", help="export from this Mac's synced Messages/call history")
    mac.add_argument("-o", "--output", default="kindred.csv")
    mac.add_argument("--chat-db", help="override path to chat.db")
    mac.add_argument("--call-db", help="override path to CallHistory.storedata")
    mac.set_defaults(func=run_mac)

    backup = sub.add_parser("backup", help="export from a local iPhone backup folder")
    backup.add_argument("backup_dir", help="path to the backup (the folder containing Manifest.db)")
    backup.add_argument("-o", "--output", default="kindred.csv")
    backup.set_defaults(func=run_backup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
