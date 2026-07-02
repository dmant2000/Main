# Kindred for iOS

Native SwiftUI version of the relationship trend analyzer. Everything stays
on-device: import your history, see who's rising and who's fading, and let the
Contacts framework turn phone numbers into real names.

## "Was I in person with this person?"

iOS has no presence API, so each contact's detail screen answers this two ways:

- **Check Calendar** — scans your calendar (read-only, on-device, with
  permission) for events in the last 6 months whose title or attendees mention
  the contact, and lets you confirm which ones were real in-person hangouts.
- **Log a hangout…** — records a meet manually with a date picker.

Confirmed meets are the highest-weighted signal in the connection score (15
points each — more than a call), the detail screen shows "you last saw them in
person N days ago", and re-confirming the same day twice is deduplicated.

## The iOS data problem, and the workaround

iOS sandboxes every third-party app away from the Messages database and the
call log — there is no API for it, for anyone, so no app can read them
directly. Kindred works from **exports** instead:

| Route | What you need | How |
|---|---|---|
| **Mac sync** (easiest) | A Mac your iPhone syncs to | `python3 export-tools/export_comms.py mac -o kindred.csv` |
| **iPhone backup** (no Mac) | A local, *unencrypted* Finder/iTunes backup | `python3 export-tools/export_comms.py backup <backup-folder> -o kindred.csv` |
| **Android history** | calls.xml / sms.xml from SMS Backup & Restore | import the XML files directly |

Then AirDrop or save `kindred.csv` to the iPhone and import it in the app
(Files picker). Exports carry numbers, not names — tap **Use contact names**
in the app menu to resolve them against your address book, entirely on-device.

On macOS, give your terminal Full Disk Access (System Settings → Privacy &
Security) or `chat.db` will be unreadable. Backups live in
`~/Library/Application Support/MobileSync/Backup/<UDID>` (macOS) or
`%APPDATA%\Apple Computer\MobileSync\Backup\` (Windows).

## Building

Open `Kindred.xcodeproj` in Xcode 16 or newer, select your team under
Signing & Capabilities (and change the placeholder bundle id
`com.example.kindred`), and run. Requires iOS 17+.

The analysis engine and parsers live in the local `KindredCore` Swift package —
a direct port of the web app's `analysis.js`/`parsers.js`, with the same test
suite. Run the tests in Xcode (⌘U) or with
`swift test` from `ios/KindredCore/` on a Mac.

> Note: this project was authored in a Linux environment without a Swift
> toolchain, so it has not been compiled here — the Python exporter and the
> shared algorithm (via its JS twin) are test-verified; expect at most minor
> compile fixes on first build.

## Structure

```
Kindred.xcodeproj/        Xcode 16 project (synchronized folders — no file lists)
Kindred/                  app target
  KindredApp.swift        entry point
  DataStore.swift         persistence, import, Contacts name resolution
  Theme.swift             validated chart palette (light/dark), trend tokens
  Views/                  dashboard, contact cards + sparklines, detail charts
KindredCore/              local Swift package: models, parsers, analysis, demo
  Tests/                  XCTest port of the web app's test suite
```

## Possible next steps

- App Intents / widget: "who's fading this month" on the home screen
- Local notifications: "you haven't talked to Sam in 10 weeks"
- CallKit `CXCallObserver` to log new calls live while the app is in use,
  supplementing imports going forward
- Encrypted-backup support in the exporter (needs the backup password)
