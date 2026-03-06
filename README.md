This is Dylans first python bot
The bots purpose is to post a quote from Moneyball or another movie or book everyday to his twitter account

## March Madness Bot

Two-part March Madness system:

### Game Alert Bot (`march_madness.py`)
Texts you every March Madness game with teams, round, time, and spread.
- Uses The Odds API for live spreads from real sportsbooks
- Sends SMS via email-to-SMS gateway (Verizon vtext)
- Runs automatically via GitHub Actions (9 AM + 5 PM ET during tournament)
- Groups games into readable text chunks (4 games per message)

**Setup:**
1. Get a free API key from https://the-odds-api.com (500 requests/month free)
2. Add `ODDS_API_KEY` to your GitHub repo secrets
3. Workflow runs automatically during March or trigger manually

### Bracket Prediction Model (`bracket_model.py`)
Predicts tournament outcomes using a weighted model:
- Historical seed win rates (1985-present)
- KenPom-style adjusted efficiency metrics
- Market spreads / betting consensus
- Hot/cold streaks (last 10 games)
- Weights adjust by round (seeds matter less in later rounds)

Run the demo: `python bracket_model.py`
