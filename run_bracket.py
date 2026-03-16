#!/usr/bin/env python3
"""
Run the 2026 March Madness bracket prediction.

Loads the tournament field from data/tournament_2026.json,
fetches live efficiency data from Barttorvik and odds from The Odds API,
then simulates the full bracket round by round.

Usage:
    python run_bracket.py              # Run with whatever data is available
    python run_bracket.py --fetch      # Fetch fresh data before running
    python run_bracket.py --dry-run    # Show bracket without fetching
"""

import json
import sys
from pathlib import Path
from bracket_model import (
    Team, predict_game, simulate_bracket, print_predictions,
    save_bracket, populate_teams_from_data, fetch_kenpom_data,
    fetch_odds_data, load_trained_model, ROUND_NAMES,
)

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
TOURNAMENT_FILE = DATA_DIR / "tournament_2026.json"
TEAM_STATS_FILE = DATA_DIR / "team_stats_2026.json"


def load_tournament():
    """Load the 2026 tournament bracket."""
    with open(TOURNAMENT_FILE, "r") as f:
        return json.load(f)


def build_teams_from_bracket(tournament_data):
    """Build Team objects from the bracket data, ordered for simulation."""
    teams_by_region = {}
    notes = tournament_data.get("notes", {})

    for region_name, region_data in tournament_data["regions"].items():
        # Tournament bracket order: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
        region_teams = []
        for matchup in region_data["matchups"]:
            t1 = Team(
                name=matchup["team1"],
                seed=matchup["seed1"],
                region=region_name,
            )
            t2 = Team(
                name=matchup["team2"],
                seed=matchup["seed2"],
                region=region_name,
            )

            # Apply known notes
            if t1.name in notes:
                apply_notes(t1, notes[t1.name])
            if t2.name in notes:
                apply_notes(t2, notes[t2.name])

            region_teams.append(t1)
            region_teams.append(t2)

        teams_by_region[region_name] = region_teams

    return teams_by_region


def apply_notes(team, note_text):
    """Apply known context from notes to team object."""
    note = note_text.lower()

    # Extract record if present (e.g. "32-2")
    import re
    record = re.search(r"(\d+)-(\d+)", note)
    if record:
        team.wins = int(record.group(1))
        team.losses = int(record.group(2))

    # Conference champ flags
    if "champ" in note and ("acc" in note or "big 12" in note or "big ten" in note
                             or "big east" in note or "sec" in note or "wcc" in note):
        team.conf_tournament_champ = True

    # Injury flags
    if "without" in note or "injury" in note or "torn acl" in note or "surgery" in note:
        team.key_player_out = True
        team.injury_impact = -3.0  # Rough estimate: losing a starter costs ~3 pts

    # Win streaks
    streak = re.search(r"(\d+)-game win streak", note)
    if streak:
        team.win_streak = int(streak.group(1))


def simulate_region(region_name, teams, trained_model):
    """Simulate one region through the Elite Eight."""
    print(f"\n{'#'*60}")
    print(f"  {region_name.upper()} REGION")
    print(f"{'#'*60}")

    all_games = []
    current = list(teams)
    region_rounds = {1: "Round of 64", 2: "Round of 32", 3: "Sweet 16", 4: "Elite Eight"}

    for round_num in range(1, 5):
        round_name = region_rounds[round_num]
        next_round = []

        for i in range(0, len(current), 2):
            if i + 1 >= len(current):
                next_round.append(current[i])
                continue

            game = predict_game(current[i], current[i + 1], round_name, round_num, trained_model)
            all_games.append(game)

            winner = current[i] if game.predicted_winner == current[i].name else current[i + 1]
            next_round.append(winner)

        current = next_round
        if len(current) <= 1:
            break

    print_predictions(all_games)

    # Return the regional champion
    return current[0] if current else None, all_games


def run():
    """Full bracket simulation."""
    print("=" * 60)
    print("  2026 MARCH MADNESS BRACKET PREDICTOR")
    print("=" * 60)
    print()

    # Load bracket
    tournament = load_tournament()
    teams_by_region = build_teams_from_bracket(tournament)

    # Load team stats
    stats_data = {}
    if TEAM_STATS_FILE.exists():
        with open(TEAM_STATS_FILE, "r") as f:
            raw = json.load(f)
        stats_data = raw.get("teams", {})
        print(f"Loaded stats for {len(stats_data)} teams from team_stats_2026.json")

    # Apply stats directly to team objects
    all_teams = []
    for region_teams in teams_by_region.values():
        all_teams.extend(region_teams)

    for team in all_teams:
        if team.name in stats_data:
            s = stats_data[team.name]
            team.adj_efficiency = s.get("adj_efficiency", team.adj_efficiency)
            team.adj_offense = s.get("adj_offense", team.adj_offense)
            team.adj_defense = s.get("adj_defense", team.adj_defense)
            team.adj_tempo = s.get("adj_tempo", team.adj_tempo)
            team.barthag = s.get("barthag", team.barthag)
            team.elite_sos = s.get("elite_sos", team.elite_sos)
            team.effective_fg_pct = s.get("effective_fg_pct", team.effective_fg_pct)
            team.turnover_pct = s.get("turnover_pct", team.turnover_pct)
            team.off_rebound_pct = s.get("off_rebound_pct", team.off_rebound_pct)
            team.ft_rate = s.get("ft_rate", team.ft_rate)
            team.opp_effective_fg_pct = s.get("opp_effective_fg_pct", team.opp_effective_fg_pct)
            team.opp_turnover_pct = s.get("opp_turnover_pct", team.opp_turnover_pct)
            team.opp_off_rebound_pct = s.get("opp_off_rebound_pct", team.opp_off_rebound_pct)
            team.opp_ft_rate = s.get("opp_ft_rate", team.opp_ft_rate)
            team.wins = s.get("wins", team.wins)
            team.losses = s.get("losses", team.losses)
            team.last_10_wins = s.get("last_10_wins", team.last_10_wins)
            team.last_10_losses = s.get("last_10_losses", team.last_10_losses)
            team.win_streak = s.get("win_streak", team.win_streak)
            team.loss_streak = s.get("loss_streak", team.loss_streak)
            team.conference = s.get("conference", team.conference)
            team.conference_strength = s.get("conference_strength", team.conference_strength)
            team.conf_tournament_champ = s.get("conf_tournament_champ", team.conf_tournament_champ)
            team.spread = s.get("spread", team.spread)
            team.futures_odds = s.get("futures_odds", team.futures_odds)
            team.experience = s.get("experience", team.experience)
            team.key_player_out = s.get("key_player_out", team.key_player_out)
            team.injury_impact = s.get("injury_impact", team.injury_impact)

    # Also try fetching live data if requested
    if "--fetch" in sys.argv:
        print("\nFetching live data...")
        kenpom_data = fetch_kenpom_data()
        spreads, futures = fetch_odds_data()
        if kenpom_data or spreads or futures:
            populate_teams_from_data(all_teams, kenpom_data, spreads, futures)

    # Load trained ML model if available
    trained_model = load_trained_model()
    if trained_model:
        print("Loaded trained ML model")
    else:
        print("No trained ML model found - using baseline logistic + seed model")

    # Simulate each region
    regional_champs = {}
    all_games = []

    for region_name in ["East", "West", "South", "Midwest"]:
        champ, games = simulate_region(region_name, teams_by_region[region_name], trained_model)
        regional_champs[region_name] = champ
        all_games.extend(games)

    # Final Four
    print(f"\n{'#'*60}")
    print(f"  FINAL FOUR")
    print(f"{'#'*60}")

    # Traditional Final Four matchups: East vs West, South vs Midwest
    ff1 = predict_game(
        regional_champs["East"], regional_champs["West"],
        "Final Four", 5, trained_model,
    )
    ff2 = predict_game(
        regional_champs["South"], regional_champs["Midwest"],
        "Final Four", 5, trained_model,
    )
    all_games.extend([ff1, ff2])
    print_predictions([ff1, ff2])

    # Championship
    print(f"\n{'#'*60}")
    print(f"  NATIONAL CHAMPIONSHIP")
    print(f"{'#'*60}")

    ff1_winner = regional_champs["East"] if ff1.predicted_winner == regional_champs["East"].name else regional_champs["West"]
    ff2_winner = regional_champs["South"] if ff2.predicted_winner == regional_champs["South"].name else regional_champs["Midwest"]

    championship = predict_game(ff1_winner, ff2_winner, "Championship", 6, trained_model)
    all_games.append(championship)
    print_predictions([championship])

    print(f"\n{'='*60}")
    print(f"  PREDICTED CHAMPION: {championship.predicted_winner}")
    print(f"  Confidence: {championship.confidence:.0%}")
    print(f"{'='*60}")

    # Summary
    print("\nFinal Four:")
    for region, champ in regional_champs.items():
        print(f"  {region}: ({champ.seed}) {champ.name}")

    # Save
    save_bracket(all_games)


if __name__ == "__main__":
    run()
