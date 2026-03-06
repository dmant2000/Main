#!/usr/bin/env python3
"""
March Madness Bracket Prediction Model

Predicts tournament outcomes using:
- Historical seed performance
- Season statistics (KenPom-style efficiency metrics)
- Spread data / market consensus
- Hot/cold streaks (recent form)
- Conference strength

This is the foundation - designed to be extended with real data sources.
"""

import json
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

SCRIPT_DIR = Path(__file__).parent
BRACKET_FILE = SCRIPT_DIR / "bracket_2026.json"

# Historical upset rates by seed matchup (1-16 seeds)
# Based on all NCAA tournaments 1985-2025
HISTORICAL_SEED_WIN_RATES = {
    (1, 16): 0.99, (2, 15): 0.94, (3, 14): 0.85, (4, 13): 0.79,
    (5, 12): 0.65, (6, 11): 0.63, (7, 10): 0.61, (8, 9): 0.51,
}


@dataclass
class Team:
    name: str
    seed: int
    region: str
    # Season stats
    wins: int = 0
    losses: int = 0
    adj_efficiency: float = 0.0  # KenPom-style adjusted efficiency margin
    adj_offense: float = 0.0
    adj_defense: float = 0.0
    adj_tempo: float = 0.0
    strength_of_schedule: float = 0.0
    # Recent form (last 10 games)
    last_10_wins: int = 0
    last_10_losses: int = 0
    # Conference
    conference: str = ""
    conf_tournament_champ: bool = False
    # Odds
    spread: Optional[float] = None  # Spread for current game
    futures_odds: Optional[float] = None  # Championship futures odds


@dataclass
class Game:
    team1: Team
    team2: Team
    round_name: str
    predicted_winner: Optional[str] = None
    predicted_spread: Optional[float] = None
    confidence: float = 0.0
    actual_winner: Optional[str] = None


@dataclass
class Bracket:
    year: int
    teams: list = field(default_factory=list)
    games: list = field(default_factory=list)
    predictions: list = field(default_factory=list)


def seed_matchup_probability(seed1, seed2):
    """Get historical win probability for seed1 vs seed2."""
    low, high = min(seed1, seed2), max(seed1, seed2)
    key = (low, high)

    if key in HISTORICAL_SEED_WIN_RATES:
        prob = HISTORICAL_SEED_WIN_RATES[key]
        return prob if seed1 == low else 1 - prob

    # For matchups not in the first round, estimate based on seed difference
    diff = seed2 - seed1
    return 1 / (1 + math.exp(-0.15 * diff))


def efficiency_probability(team1, team2):
    """Predict win probability using adjusted efficiency margins."""
    if team1.adj_efficiency == 0 and team2.adj_efficiency == 0:
        return 0.5  # No data

    diff = team1.adj_efficiency - team2.adj_efficiency
    # Convert efficiency margin to win probability (logistic)
    return 1 / (1 + math.exp(-0.15 * diff))


def streak_factor(team):
    """Calculate a momentum factor from recent form. Returns 0.9 to 1.1."""
    if team.last_10_wins + team.last_10_losses == 0:
        return 1.0
    recent_pct = team.last_10_wins / (team.last_10_wins + team.last_10_losses)
    # Scale: .300 -> 0.93, .500 -> 1.0, .800 -> 1.08
    return 0.85 + (recent_pct * 0.3)


def spread_probability(spread):
    """Convert a point spread to a win probability."""
    if spread is None:
        return 0.5
    # Rough conversion: each point of spread ≈ 3% win probability shift
    return 1 / (1 + math.exp(0.15 * spread))


def predict_game(team1, team2, round_name="Round of 64"):
    """
    Predict the winner of a matchup using weighted model factors.

    Weights:
    - Seed history: 20% (less weight in later rounds)
    - Efficiency metrics: 35%
    - Spread/market: 30%
    - Recent form: 15%
    """
    # Adjust weights by round (seeds matter less in later rounds)
    round_weights = {
        "Round of 64": {"seed": 0.25, "efficiency": 0.30, "spread": 0.30, "streak": 0.15},
        "Round of 32": {"seed": 0.20, "efficiency": 0.35, "spread": 0.30, "streak": 0.15},
        "Sweet 16":    {"seed": 0.15, "efficiency": 0.35, "spread": 0.30, "streak": 0.20},
        "Elite Eight": {"seed": 0.10, "efficiency": 0.35, "spread": 0.30, "streak": 0.25},
        "Final Four":  {"seed": 0.10, "efficiency": 0.35, "spread": 0.30, "streak": 0.25},
        "Championship":{"seed": 0.05, "efficiency": 0.35, "spread": 0.35, "streak": 0.25},
    }

    w = round_weights.get(round_name, {"seed": 0.20, "efficiency": 0.35, "spread": 0.30, "streak": 0.15})

    # Factor 1: Historical seed performance
    p_seed = seed_matchup_probability(team1.seed, team2.seed)

    # Factor 2: Efficiency metrics
    p_eff = efficiency_probability(team1, team2)

    # Factor 3: Spread/market consensus
    p_spread = spread_probability(team1.spread) if team1.spread is not None else 0.5

    # Factor 4: Streak/momentum
    s1 = streak_factor(team1)
    s2 = streak_factor(team2)
    p_streak = s1 / (s1 + s2)

    # Weighted combination
    p_team1 = (
        w["seed"] * p_seed +
        w["efficiency"] * p_eff +
        w["spread"] * p_spread +
        w["streak"] * p_streak
    )

    winner = team1 if p_team1 > 0.5 else team2
    confidence = max(p_team1, 1 - p_team1)

    return Game(
        team1=team1,
        team2=team2,
        round_name=round_name,
        predicted_winner=winner.name,
        predicted_spread=round((p_team1 - 0.5) * 20, 1),  # Rough spread estimate
        confidence=round(confidence, 3),
    )


def simulate_bracket(teams):
    """
    Simulate an entire bracket given a list of 64 teams.
    Teams should be ordered by region and seed.
    Returns all game predictions round by round.
    """
    rounds = ["Round of 64", "Round of 32", "Sweet 16", "Elite Eight", "Final Four", "Championship"]
    all_games = []
    current_teams = list(teams)

    for round_name in rounds:
        next_round = []
        round_games = []

        for i in range(0, len(current_teams), 2):
            if i + 1 >= len(current_teams):
                next_round.append(current_teams[i])
                continue

            game = predict_game(current_teams[i], current_teams[i + 1], round_name)
            round_games.append(game)

            # Advance winner
            winner = current_teams[i] if game.predicted_winner == current_teams[i].name else current_teams[i + 1]
            next_round.append(winner)

        all_games.extend(round_games)
        current_teams = next_round

        if len(current_teams) <= 1:
            break

    return all_games


def print_predictions(games):
    """Print bracket predictions in a readable format."""
    current_round = ""
    for game in games:
        if game.round_name != current_round:
            current_round = game.round_name
            print(f"\n{'='*50}")
            print(f"  {current_round}")
            print(f"{'='*50}")

        marker = ">>>" if game.confidence > 0.7 else ">>" if game.confidence > 0.6 else ">"
        print(
            f"  ({game.team1.seed}) {game.team1.name} vs ({game.team2.seed}) {game.team2.name}"
            f"  {marker} {game.predicted_winner} ({game.confidence:.0%})"
        )


def save_bracket(games, filepath=BRACKET_FILE):
    """Save predictions to JSON."""
    output = []
    for g in games:
        output.append({
            "round": g.round_name,
            "team1": {"name": g.team1.name, "seed": g.team1.seed, "region": g.team1.region},
            "team2": {"name": g.team2.name, "seed": g.team2.seed, "region": g.team2.region},
            "predicted_winner": g.predicted_winner,
            "confidence": g.confidence,
            "predicted_spread": g.predicted_spread,
        })
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Bracket saved to {filepath}")


# --- Demo with example teams ---
def demo():
    """Demo the model with a small sample matchup."""
    duke = Team(
        name="Duke", seed=1, region="East",
        wins=29, losses=4, adj_efficiency=30.5,
        adj_offense=120.3, adj_defense=89.8,
        last_10_wins=9, last_10_losses=1,
        conference="ACC", spread=-8.5,
    )
    vermont = Team(
        name="Vermont", seed=16, region="East",
        wins=25, losses=8, adj_efficiency=5.2,
        adj_offense=105.1, adj_defense=99.9,
        last_10_wins=7, last_10_losses=3,
        conference="AEC", spread=8.5,
    )
    houston = Team(
        name="Houston", seed=2, region="East",
        wins=30, losses=3, adj_efficiency=28.1,
        adj_offense=118.5, adj_defense=90.4,
        last_10_wins=8, last_10_losses=2,
        conference="Big 12", spread=-12.0,
    )
    colgate = Team(
        name="Colgate", seed=15, region="East",
        wins=24, losses=9, adj_efficiency=3.8,
        adj_offense=103.2, adj_defense=99.4,
        last_10_wins=6, last_10_losses=4,
        conference="Patriot", spread=12.0,
    )

    print("MARCH MADNESS BRACKET PREDICTOR")
    print("================================\n")
    print("Demo: Sample First Round Matchups\n")

    games = [
        predict_game(duke, vermont, "Round of 64"),
        predict_game(houston, colgate, "Round of 64"),
    ]

    print_predictions(games)

    # Simulate a second round
    winner1 = duke if games[0].predicted_winner == "Duke" else vermont
    winner2 = houston if games[1].predicted_winner == "Houston" else colgate

    r2 = predict_game(winner1, winner2, "Round of 32")
    print_predictions([r2])


if __name__ == "__main__":
    demo()
