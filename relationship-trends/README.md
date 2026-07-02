# Kindred — relationship trend analyzer

A privacy-first app that looks at your texting and phone-call history with
friends and family and tells you whether each relationship is **trending up or
down**. Everything runs locally — no account, no server, no data ever leaves
your machine. Two front-ends share the same analysis engine:

- **Web app** (this directory) — zero dependencies, runs in any browser
- **iOS app** (`ios/`) — native SwiftUI + Swift Charts; see `ios/README.md`

## Run it

It's a static site with no build step or dependencies:

```bash
cd relationship-trends
python3 -m http.server 8080
# open http://localhost:8080
```

Click **Load demo data** to explore immediately, or import your own history.

## Getting your data in

Phone platforms don't let websites read your messages or call log directly
(and iOS doesn't let *any* third-party app do it), so Kindred works from
exports:

- **Android**: install the free [SMS Backup & Restore](https://play.google.com/store/apps/details?id=com.riteshsahu.SMSBackupRestore)
  app, back up "Calls" and "Messages" as XML, and import the resulting
  `calls.xml` / `sms.xml` files here. Both files at once gives the best picture.
- **iPhone**: iOS lets no app read messages or the call log directly, so use
  `export-tools/export_comms.py` — it exports Kindred's CSV from a Mac your
  phone syncs to (`mac` mode) or from a local unencrypted Finder/iTunes backup
  (`backup` mode). Works for both the web app and the iOS app.
- **CSV**: anything you can shape into this schema (see `sample-data/sample.csv`):

  ```csv
  date,kind,direction,contact,number,duration_seconds
  2026-05-04T18:30:00Z,text,out,Maya,+15557001001,
  2026-05-06T20:10:00Z,call,in,Maya,+15557001001,840
  ```

  `date` is ISO 8601 or epoch milliseconds; `kind` is `text` or `call`;
  `direction` is `in`, `out`, or `missed`; `duration_seconds` applies to calls.

MMS/group threads and iMessage exports aren't parsed yet (see Roadmap).

## How the analysis works

1. Events are grouped per contact by normalized phone number.
2. Activity is bucketed into calendar weeks and each week gets a
   **connection score**: `texts + 6 × calls + 0.4 × call-minutes + missed-call attempts`
   (a call counts for more than a text; longer calls count for more; even a
   missed call shows intent to connect).
3. The average score of the **last 4 complete weeks** is compared to the
   **prior 8 weeks** (the in-progress week is ignored so a fresh Monday doesn't
   read as everyone abandoning you):
   - **Rising** — up 25% or more
   - **Fading** — down 25% or more
   - **Steady** — inside that band
   - **Dormant** — zero contact for 8 straight weeks
4. It also surfaces **initiation balance** ("you reach out 88% of the time"),
   days since last contact, and lifetime totals.

Numbers seen only once are skipped — verification codes and spam aren't
relationships.

## Tests

```bash
cd relationship-trends
npm test                                  # web engine: node --test test/*.test.js
python3 -m unittest discover export-tools  # iPhone exporter
```

The iOS port's tests (`ios/KindredCore/Tests`) run in Xcode on a Mac.

## Project layout

```
index.html          app shell
css/style.css       theming (light/dark), layout, chart chrome
js/parsers.js       SMS Backup & Restore XML + CSV parsers
js/analysis.js      weekly bucketing, connection score, trend classification
js/charts.js        SVG sparkline + column chart with hover tooltips
js/demo.js          deterministic demo dataset
js/app.js           UI state and rendering
test/               node:test suites for parsers and analysis
sample-data/        example CSV import
export-tools/       iPhone exporter (Mac sync + iTunes/Finder backup modes)
ios/                native iOS app (SwiftUI + KindredCore Swift package)
```

## Roadmap ideas

- MMS / group-thread parsing
- Response-time analysis (how fast do they text back, and you them?)
- Reminders: "You haven't talked to Sam in 10 weeks"
- A native Android companion app that reads the call log and SMS providers
  directly and refreshes the dashboard automatically
