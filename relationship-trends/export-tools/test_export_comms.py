"""Tests for export_comms.py using synthetic databases that mimic the real
chat.db / CallHistory.storedata / iPhone-backup schemas.

Run: python3 -m unittest discover relationship-trends/export-tools
"""

import csv
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "export_comms.py"
APPLE = 978307200  # 2001-01-01 UTC


def make_chat_db(path, *, nanoseconds):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY, date INTEGER,
            is_from_me INTEGER, handle_id INTEGER
        );
        """
    )
    conn.execute("INSERT INTO handle VALUES (1, '+15551234567')")
    conn.execute("INSERT INTO handle VALUES (2, 'friend@example.com')")
    # 2026-01-01 12:00:00 UTC = Apple 788961600
    base = 788961600
    scale = 10**9 if nanoseconds else 1
    rows = [
        (1, base * scale, 0, 1),          # received from +1555...
        (2, (base + 60) * scale, 1, 1),   # sent to +1555...
        (3, (base + 120) * scale, 1, 2),  # sent to email handle
        (4, 0, 0, 1),                     # invalid date: skipped
    ]
    conn.executemany("INSERT INTO message VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()


def make_call_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE ZCALLRECORD (
            Z_PK INTEGER PRIMARY KEY, ZDATE FLOAT, ZDURATION FLOAT,
            ZORIGINATED INTEGER, ZANSWERED INTEGER, ZADDRESS VARCHAR
        )
        """
    )
    base = 788961600.5
    rows = [
        (1, base, 300.0, 1, 1, "+15551234567"),       # outgoing, 5 min
        (2, base + 3600, 120.0, 0, 1, "5559876543"),  # incoming answered
        (3, base + 7200, 0.0, 0, 0, "5559876543"),    # missed
        (4, base + 9000, 60.0, 1, 1, None),           # no address: skipped
    ]
    conn.executemany("INSERT INTO ZCALLRECORD VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def run_script(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class MacModeTests(unittest.TestCase):
    def test_exports_messages_and_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_chat_db(tmp / "chat.db", nanoseconds=True)
            make_call_db(tmp / "CallHistory.storedata")
            out = tmp / "out.csv"
            result = run_script(
                "mac",
                "--chat-db", str(tmp / "chat.db"),
                "--call-db", str(tmp / "CallHistory.storedata"),
                "-o", str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_csv(out)
            texts = [r for r in rows if r["kind"] == "text"]
            calls = [r for r in rows if r["kind"] == "call"]
            self.assertEqual(len(texts), 3)
            self.assertEqual(len(calls), 3)

            self.assertEqual(texts[0]["date"], "2026-01-01T12:00:00Z")
            self.assertEqual(texts[0]["direction"], "in")
            self.assertEqual(texts[0]["number"], "+15551234567")
            self.assertEqual(texts[1]["direction"], "out")

            self.assertEqual(calls[0]["direction"], "out")
            self.assertEqual(calls[0]["duration_seconds"], "300")
            self.assertEqual(calls[1]["direction"], "in")
            self.assertEqual(calls[2]["direction"], "missed")
            self.assertEqual(calls[2]["duration_seconds"], "")

    def test_seconds_precision_chat_db(self):
        # Older macOS stores seconds, not nanoseconds, since 2001.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_chat_db(tmp / "chat.db", nanoseconds=False)
            make_call_db(tmp / "calls.db")
            out = tmp / "out.csv"
            result = run_script(
                "mac", "--chat-db", str(tmp / "chat.db"),
                "--call-db", str(tmp / "calls.db"), "-o", str(out),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            texts = [r for r in read_csv(out) if r["kind"] == "text"]
            self.assertEqual(texts[0]["date"], "2026-01-01T12:00:00Z")


class BackupModeTests(unittest.TestCase):
    def build_backup(self, root):
        """Backup layout: Manifest.db plus files at <first2-of-id>/<id>."""
        sms_id = "3d0d7e5fb2ce288813306e4d4636395e047a3d28"
        call_id = "5a4935c78a5255723f707230a451d79c540d2741"
        for file_id, maker in ((sms_id, lambda p: make_chat_db(p, nanoseconds=True)),
                               (call_id, make_call_db)):
            dest = root / file_id[:2]
            dest.mkdir(exist_ok=True)
            maker(dest / file_id)
        manifest = sqlite3.connect(root / "Manifest.db")
        manifest.execute(
            "CREATE TABLE Files (fileID TEXT, domain TEXT, relativePath TEXT)"
        )
        manifest.executemany(
            "INSERT INTO Files VALUES (?,?,?)",
            [
                (sms_id, "HomeDomain", "Library/SMS/sms.db"),
                (call_id, "HomeDomain", "Library/CallHistoryDB/CallHistory.storedata"),
            ],
        )
        manifest.commit()
        manifest.close()

    def test_exports_from_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.build_backup(tmp)
            out = tmp / "out.csv"
            result = run_script("backup", str(tmp), "-o", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_csv(out)
            self.assertEqual(len([r for r in rows if r["kind"] == "text"]), 3)
            self.assertEqual(len([r for r in rows if r["kind"] == "call"]), 3)

    def test_encrypted_backup_gives_friendly_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # An encrypted Manifest.db is not valid SQLite.
            (tmp / "Manifest.db").write_bytes(b"\x00encrypted-blob\x00" * 64)
            result = run_script("backup", str(tmp), "-o", str(tmp / "out.csv"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("encrypted", result.stderr)

    def test_missing_backup_dir(self):
        result = run_script("backup", "/nonexistent/backup", "-o", "/tmp/x.csv")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)


class CsvCompatibilityTests(unittest.TestCase):
    def test_output_parses_in_the_web_app_schema(self):
        """The exported header must match what parsers.js/Parsers.swift expect."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_chat_db(tmp / "chat.db", nanoseconds=True)
            make_call_db(tmp / "calls.db")
            out = tmp / "out.csv"
            run_script("mac", "--chat-db", str(tmp / "chat.db"),
                       "--call-db", str(tmp / "calls.db"), "-o", str(out))
            with open(out, encoding="utf-8") as f:
                header = f.readline().strip()
            self.assertEqual(
                header, "date,kind,direction,contact,number,duration_seconds"
            )


if __name__ == "__main__":
    unittest.main()
