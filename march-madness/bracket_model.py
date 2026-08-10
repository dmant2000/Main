#!/usr/bin/env python3
"""
March Madness Bracket Prediction Model

Multi-factor ML model for predicting NCAA Tournament outcomes.

Data sources:
- KenPom: Adjusted efficiency, tempo, offensive/defensive ratings
- Barttorvik (T-Rank): Alternative efficiency metrics, player-level data
- FiveThirtyEight/Raptor-style: Team quality ratings adapted for college
- The Odds API: Market spreads and futures (wisdom of the crowd)
- NCAA Stats: Official season statistics
- Historical: Seed performance data from 1985-present

Model architecture:
- Feature engineering from all data sources
- Logistic regression baseline
- Gradient boosted trees (XGBoost) for main predictions
- Ensemble with market odds for final output
"""

import json
import csv
import math
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

# Optional ML imports - gracefully degrade if not installed
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    import pickle
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
MODEL_DIR = SCRIPT_DIR / "models"
BRACKET_FILE = SCRIPT_DIR / "bracket_2026.json"

# Historical seed win rates (1985-2025, first round only)
HISTORICAL_SEED_WIN_RATES = {
    (1, 16): 0.99, (2, 15): 0.94, (3, 14): 0.85, (4, 13): 0.79,
    (5, 12): 0.65, (6, 11): 0.63, (7, 10): 0.61, (8, 9): 0.51,
}

# Average seed advancement rates by round (historical)
SEED_ROUND_SURVIVAL = {
    # seed: [R64, R32, S16, E8, F4, Champ, Winner]
    1:  [0.99, 0.85, 0.68, 0.51, 0.35, 0.22, 0.14],
    2:  [0.94, 0.72, 0.50, 0.33, 0.19, 0.11, 0.06],
    3:  [0.85, 0.61, 0.36, 0.20, 0.10, 0.05, 0.03],
    4:  [0.79, 0.54, 0.31, 0.16, 0.08, 0.04, 0.02],
    5:  [0.65, 0.39, 0.19, 0.09, 0.04, 0.02, 0.01],
    6:  [0.63, 0.37, 0.17, 0.08, 0.03, 0.01, 0.005],
    7:  [0.61, 0.34, 0.14, 0.06, 0.02, 0.01, 0.004],
    8:  [0.51, 0.25, 0.10, 0.04, 0.02, 0.01, 0.003],
    9:  [0.49, 0.20, 0.07, 0.03, 0.01, 0.005, 0.002],
    10: [0.39, 0.16, 0.06, 0.02, 0.01, 0.003, 0.001],
    11: [0.37, 0.16, 0.07, 0.03, 0.02, 0.007, 0.004],
    12: [0.35, 0.13, 0.04, 0.01, 0.005, 0.002, 0.001],
    13: [0.21, 0.06, 0.02, 0.005, 0.001, 0.0005, 0.0],
    14: [0.15, 0.04, 0.01, 0.003, 0.001, 0.0, 0.0],
    15: [0.06, 0.02, 0.007, 0.003, 0.001, 0.0, 0.0],
    16: [0.01, 0.005, 0.001, 0.0, 0.0, 0.0, 0.0],
}


# ============================================================
# Data Models
# ============================================================

@dataclass
class Team:
    name: str
    seed: int
    region: str
    # Record
    wins: int = 0
    losses: int = 0
    # KenPom-style efficiency metrics
    adj_efficiency: float = 0.0     # Adjusted efficiency margin (AdjEM)
    adj_offense: float = 0.0        # Adjusted offensive efficiency (pts/100 poss)
    adj_defense: float = 0.0        # Adjusted defensive efficiency (pts/100 poss)
    adj_tempo: float = 0.0          # Adjusted tempo (possessions/game)
    # Barttorvik T-Rank style
    barthag: float = 0.0            # Power rating (win probability vs avg D1 team)
    elite_sos: float = 0.0          # Strength of schedule vs top 50 teams
    # Raptor-style composite rating
    raptor_offense: float = 0.0     # Offensive quality above average
    raptor_defense: float = 0.0     # Defensive quality above average
    raptor_total: float = 0.0       # Combined Raptor rating
    # Shooting / four factors
    effective_fg_pct: float = 0.0   # eFG% (accounts for 3-pt value)
    turnover_pct: float = 0.0       # Turnover rate
    off_rebound_pct: float = 0.0    # Offensive rebound %
    ft_rate: float = 0.0            # Free throw rate (FTA/FGA)
    opp_effective_fg_pct: float = 0.0
    opp_turnover_pct: float = 0.0
    opp_off_rebound_pct: float = 0.0
    opp_ft_rate: float = 0.0
    # Experience & roster
    avg_height: float = 0.0         # Average height in inches
    experience: float = 0.0         # Years of experience weighted
    bench_minutes_pct: float = 0.0  # % of minutes from bench
    # Streaks / form
    last_10_wins: int = 0
    last_10_losses: int = 0
    win_streak: int = 0
    loss_streak: int = 0
    # Conference
    conference: str = ""
    conf_tournament_champ: bool = False
    conf_regular_season_champ: bool = False
    conference_strength: float = 0.0  # Conference RPI/quality rating
    # Market data
    spread: Optional[float] = None
    futures_odds: Optional[float] = None  # Implied probability to win it all
    # 3-Point X-Factor
    three_pt_pct: float = 0.0       # Team 3PT shooting percentage
    three_pt_rate: float = 0.0      # % of FGA that are 3-pointers
    three_pt_made: float = 0.0      # 3-pointers made per game
    opp_three_pt_pct: float = 0.0   # Opponent 3PT shooting percentage allowed
    has_elite_shooter: bool = False  # Has a standout 3PT threat (35%+ on volume)
    # Injuries / availability
    key_player_out: bool = False
    injury_impact: float = 0.0  # Estimated point impact of injuries


@dataclass
class Game:
    team1: Team
    team2: Team
    round_name: str
    round_number: int = 0  # 1=R64, 2=R32, 3=S16, 4=E8, 5=F4, 6=Champ
    predicted_winner: Optional[str] = None
    win_probability: float = 0.0
    predicted_spread: Optional[float] = None
    confidence: float = 0.0
    model_factors: dict = field(default_factory=dict)
    actual_winner: Optional[str] = None


@dataclass
class Bracket:
    year: int
    teams: list = field(default_factory=list)
    games: list = field(default_factory=list)


# ============================================================
# Data Fetching
# ============================================================

def api_get(url):
    """Make a GET request and return parsed JSON."""
    req = Request(url, headers={"User-Agent": "MarchMadnessBot/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"API error fetching {url}: {e}")
        return None


def fetch_kenpom_data():
    """
    Fetch KenPom-style efficiency data.

    In production, you'd scrape kenpom.com (requires subscription) or use
    Barttorvik's free data at barttorvik.com.

    Returns dict of {team_name: {adj_efficiency, adj_offense, adj_defense, adj_tempo}}
    """
    # Barttorvik T-Rank data is free and similar to KenPom
    # URL pattern: barttorvik.com/trank.php?year=2026&json=1
    print("  [Data] Fetching efficiency ratings...")
    url = "https://barttorvik.com/getadvstats.php?year=2026&top=358&json=1"
    data = api_get(url)
    if data is None:
        print("  [Data] Could not fetch Barttorvik data - will use manual input")
        return {}

    teams = {}
    for row in data:
        name = row.get("team", row.get("Team", ""))
        if not name:
            continue
        teams[name] = {
            "adj_offense": float(row.get("adjoe", row.get("AdjOE", 0))),
            "adj_defense": float(row.get("adjde", row.get("AdjDE", 0))),
            "adj_efficiency": float(row.get("adjoe", 0)) - float(row.get("adjde", 0)),
            "adj_tempo": float(row.get("adjt", row.get("AdjT", 0))),
            "barthag": float(row.get("barthag", row.get("Barthag", 0))),
            "elite_sos": float(row.get("esos", row.get("Elite SOS", 0))),
            "effective_fg_pct": float(row.get("efg", row.get("eFG%", 0))),
            "turnover_pct": float(row.get("tor", row.get("TO%", 0))),
            "off_rebound_pct": float(row.get("orb", row.get("ORB%", 0))),
            "ft_rate": float(row.get("ftr", row.get("FTR", 0))),
            "opp_effective_fg_pct": float(row.get("efgd", row.get("Opp eFG%", 0))),
            "opp_turnover_pct": float(row.get("tord", row.get("Opp TO%", 0))),
            "opp_off_rebound_pct": float(row.get("orbr", row.get("Opp ORB%", 0))),
            "opp_ft_rate": float(row.get("ftrd", row.get("Opp FTR", 0))),
            "wins": int(row.get("wins", row.get("W", 0))),
            "losses": int(row.get("losses", row.get("L", 0))),
        }
    return teams


def fetch_odds_data():
    """Fetch current spreads and futures from The Odds API."""
    api_key = os.environ.get("ODDS_API_KEY", "")
    if not api_key:
        print("  [Data] No ODDS_API_KEY - skipping market data")
        return {}, {}

    print("  [Data] Fetching market odds...")
    base = "https://api.the-odds-api.com/v4"

    # Current game spreads
    spreads_url = (
        f"{base}/sports/basketball_ncaab/odds/"
        f"?apiKey={api_key}&regions=us&markets=spreads&oddsFormat=american"
    )
    spreads_data = api_get(spreads_url) or []

    spreads = {}
    for event in spreads_data:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        for book in event.get("bookmakers", []):
            if book["key"] in ("fanduel", "draftkings"):
                for market in book.get("markets", []):
                    if market["key"] == "spreads":
                        for outcome in market.get("outcomes", []):
                            spreads[outcome["name"]] = outcome.get("point", 0)
                break

    # Championship futures
    futures_url = (
        f"{base}/sports/basketball_ncaab_championship_winner/odds/"
        f"?apiKey={api_key}&regions=us&oddsFormat=american"
    )
    futures_data = api_get(futures_url) or []

    futures = {}
    for event in futures_data:
        for book in event.get("bookmakers", []):
            if book["key"] in ("fanduel", "draftkings"):
                for market in book.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        odds = outcome.get("price", 0)
                        # Convert American odds to implied probability
                        if odds > 0:
                            prob = 100 / (odds + 100)
                        elif odds < 0:
                            prob = abs(odds) / (abs(odds) + 100)
                        else:
                            prob = 0
                        futures[outcome["name"]] = prob
                break

    return spreads, futures


def build_raptor_rating(team):
    """
    Calculate a Raptor-style composite rating for a team.

    Modeled after FiveThirtyEight's college basketball ratings:
    - Offensive component from adj_offense, eFG%, turnover rate
    - Defensive component from adj_defense, opp_eFG%, opp_turnover rate
    - Adjustments for SOS, experience, and conference strength
    """
    # Offensive Raptor: efficiency + shooting + ball security
    off_eff_component = (team.adj_offense - 100) * 0.5  # Centered on D1 average ~100
    off_shooting = (team.effective_fg_pct - 0.50) * 30 if team.effective_fg_pct > 0 else 0
    off_turnovers = (0.18 - team.turnover_pct) * 20 if team.turnover_pct > 0 else 0
    off_boards = (team.off_rebound_pct - 0.30) * 15 if team.off_rebound_pct > 0 else 0

    raptor_off = off_eff_component + off_shooting + off_turnovers + off_boards

    # Defensive Raptor: efficiency + opponent shooting + forced turnovers
    def_eff_component = (100 - team.adj_defense) * 0.5
    def_shooting = (0.48 - team.opp_effective_fg_pct) * 30 if team.opp_effective_fg_pct > 0 else 0
    def_turnovers = (team.opp_turnover_pct - 0.18) * 20 if team.opp_turnover_pct > 0 else 0
    def_boards = (0.28 - team.opp_off_rebound_pct) * 15 if team.opp_off_rebound_pct > 0 else 0

    raptor_def = def_eff_component + def_shooting + def_turnovers + def_boards

    # SOS adjustment: teams with harder schedules get a boost
    sos_adj = team.elite_sos * 0.5

    # Conference strength adjustment
    conf_adj = team.conference_strength * 0.3

    team.raptor_offense = round(raptor_off + sos_adj * 0.5, 2)
    team.raptor_defense = round(raptor_def + sos_adj * 0.5, 2)
    team.raptor_total = round(raptor_off + raptor_def + sos_adj + conf_adj, 2)


# ============================================================
# Feature Engineering
# ============================================================

FEATURE_NAMES = [
    "seed_diff",
    "adj_efficiency_diff",
    "adj_offense_diff",
    "adj_defense_diff",
    "barthag_diff",
    "raptor_total_diff",
    "raptor_offense_diff",
    "raptor_defense_diff",
    "efg_diff",
    "turnover_diff",
    "off_reb_diff",
    "ft_rate_diff",
    "opp_efg_diff",
    "elite_sos_diff",
    "win_pct_diff",
    "streak_diff",
    "experience_diff",
    "conf_strength_diff",
    "spread",
    "futures_diff",
    "seed_hist_prob",
    "injury_impact_diff",
    "is_conf_champ_1",
    "is_conf_champ_2",
    "round_number",
    # 3-Point X-Factor
    "three_pt_pct_diff",
    "three_pt_rate_diff",
    "opp_three_pt_pct_diff",
    "three_pt_xfactor",
]


def compute_three_pt_xfactor(shooter_team, defender_team):
    """
    Compute the 3-point X-factor for shooter_team attacking defender_team.

    Factors:
    1. Shooter's 3PT% vs defender's opp 3PT% (mismatch)
    2. Shooter's 3PT volume (rate) — teams that live by the 3 get amplified
    3. Elite shooter bonus — having a go-to guy who can get hot

    Returns a score where positive = 3PT advantage, negative = disadvantage.
    Typical range: -0.5 to +0.5
    """
    if shooter_team.three_pt_pct == 0:
        return 0.0

    # How much better/worse does the shooter shoot vs what the defender allows?
    # If team shoots 37% and opponent allows 35%, that's a +2% mismatch
    mismatch = 0.0
    if defender_team.opp_three_pt_pct > 0:
        mismatch = shooter_team.three_pt_pct - defender_team.opp_three_pt_pct
    else:
        # No defensive data — just compare to D1 average (~33.5%)
        mismatch = shooter_team.three_pt_pct - 0.335

    # Volume amplifier: teams that shoot lots of 3s get more leverage from the mismatch
    # Average 3PT rate is ~35% of FGA. Scale: 0.8x at 25%, 1.0x at 35%, 1.3x at 45%
    volume_mult = 1.0
    if shooter_team.three_pt_rate > 0:
        volume_mult = 0.5 + (shooter_team.three_pt_rate / 0.35)

    # Elite shooter bonus: +0.05 if team has a standout threat
    elite_bonus = 0.05 if shooter_team.has_elite_shooter else 0.0

    # Defender penalty: if higher seed allows high opp 3PT%, they're vulnerable
    # This is the "bad at defending the 3" penalty
    def_vulnerability = 0.0
    if defender_team.opp_three_pt_pct > 0.345:
        # Above average 3PT defense allowed = vulnerable
        def_vulnerability = (defender_team.opp_three_pt_pct - 0.335) * 2.0

    xfactor = (mismatch * 5.0 * volume_mult) + elite_bonus + def_vulnerability
    return round(xfactor, 4)


def build_features(team1, team2, round_number=1):
    """
    Build the feature vector for a team1 vs team2 matchup.
    Positive values favor team1, negative favor team2.
    """
    win_pct_1 = team1.wins / max(team1.wins + team1.losses, 1)
    win_pct_2 = team2.wins / max(team2.wins + team2.losses, 1)

    streak_1 = team1.win_streak - team1.loss_streak
    streak_2 = team2.win_streak - team2.loss_streak

    seed_prob = seed_matchup_probability(team1.seed, team2.seed)
    spread_val = team1.spread if team1.spread is not None else 0.0
    futures_1 = team1.futures_odds if team1.futures_odds is not None else 0.0
    futures_2 = team2.futures_odds if team2.futures_odds is not None else 0.0

    # 3-Point X-Factor: measures the mismatch between a team's shooting and
    # the opponent's ability to defend the 3. A team that shoots 38% from 3
    # facing a team that allows 36% from 3 = major advantage.
    three_xfactor = compute_three_pt_xfactor(team1, team2) - compute_three_pt_xfactor(team2, team1)

    features = [
        team2.seed - team1.seed,                        # seed_diff (positive = team1 better seed)
        team1.adj_efficiency - team2.adj_efficiency,     # adj_efficiency_diff
        team1.adj_offense - team2.adj_offense,           # adj_offense_diff
        team2.adj_defense - team1.adj_defense,           # adj_defense_diff (lower is better)
        team1.barthag - team2.barthag,                   # barthag_diff
        team1.raptor_total - team2.raptor_total,         # raptor_total_diff
        team1.raptor_offense - team2.raptor_offense,     # raptor_offense_diff
        team1.raptor_defense - team2.raptor_defense,     # raptor_defense_diff
        team1.effective_fg_pct - team2.effective_fg_pct, # efg_diff
        team2.turnover_pct - team1.turnover_pct,         # turnover_diff (lower is better)
        team1.off_rebound_pct - team2.off_rebound_pct,   # off_reb_diff
        team1.ft_rate - team2.ft_rate,                   # ft_rate_diff
        team2.opp_effective_fg_pct - team1.opp_effective_fg_pct,  # opp_efg_diff
        team1.elite_sos - team2.elite_sos,               # elite_sos_diff
        win_pct_1 - win_pct_2,                           # win_pct_diff
        streak_1 - streak_2,                             # streak_diff
        team1.experience - team2.experience,             # experience_diff
        team1.conference_strength - team2.conference_strength,  # conf_strength_diff
        spread_val,                                       # spread (negative = team1 favored)
        futures_1 - futures_2,                            # futures_diff
        seed_prob,                                        # seed_hist_prob
        team2.injury_impact - team1.injury_impact,        # injury_impact_diff
        1.0 if team1.conf_tournament_champ else 0.0,      # is_conf_champ_1
        1.0 if team2.conf_tournament_champ else 0.0,      # is_conf_champ_2
        float(round_number),                              # round_number
        # 3-Point X-Factor features
        team1.three_pt_pct - team2.three_pt_pct,          # three_pt_pct_diff
        team1.three_pt_rate - team2.three_pt_rate,        # three_pt_rate_diff
        team2.opp_three_pt_pct - team1.opp_three_pt_pct, # opp_three_pt_pct_diff (lower = better D)
        three_xfactor,                                     # three_pt_xfactor (composite mismatch)
    ]

    return features


# ============================================================
# Prediction Models
# ============================================================

def seed_matchup_probability(seed1, seed2):
    """Historical win probability for seed1 vs seed2."""
    low, high = min(seed1, seed2), max(seed1, seed2)
    key = (low, high)

    if key in HISTORICAL_SEED_WIN_RATES:
        prob = HISTORICAL_SEED_WIN_RATES[key]
        return prob if seed1 == low else 1 - prob

    diff = seed2 - seed1
    return 1 / (1 + math.exp(-0.15 * diff))


def logistic_model(features):
    """
    Simple logistic regression prediction using hand-tuned weights.
    Used as baseline when sklearn is not available or model isn't trained.
    """
    # Weights tuned for March Madness upset sensitivity
    # Key changes from v1: reduced seed weight, boosted streaks, added 3PT X-factor
    weights = {
        "seed_diff": 0.05,              # Reduced from 0.08 — seeds overrated in March
        "adj_efficiency_diff": 0.05,     # Slightly reduced — let other factors breathe
        "adj_offense_diff": 0.02,
        "adj_defense_diff": 0.02,
        "barthag_diff": 2.0,            # Reduced from 2.5
        "raptor_total_diff": 0.05,
        "raptor_offense_diff": 0.02,
        "raptor_defense_diff": 0.02,
        "efg_diff": 3.0,
        "turnover_diff": 2.0,
        "off_reb_diff": 1.5,
        "ft_rate_diff": 1.0,
        "opp_efg_diff": 2.5,
        "elite_sos_diff": 0.25,
        "win_pct_diff": 0.8,
        "streak_diff": 0.12,            # Doubled from 0.05 — hot teams matter in March
        "experience_diff": 0.20,         # Boosted — experience wins in tourney pressure
        "conf_strength_diff": 0.08,
        "spread": -0.07,
        "futures_diff": 1.5,
        "seed_hist_prob": 1.0,           # Reduced from 1.5 — less chalk
        "injury_impact_diff": 0.15,      # Boosted — injuries are massive in single elim
        "is_conf_champ_1": 0.15,         # Boosted — conf champs are battle-tested
        "is_conf_champ_2": -0.15,
        "round_number": 0.0,
        # 3-Point X-Factor
        "three_pt_pct_diff": 2.5,        # Good 3PT shooting is a weapon
        "three_pt_rate_diff": 0.8,        # Teams that shoot more 3s have higher variance (upsets)
        "opp_three_pt_pct_diff": 2.0,     # Bad 3PT defense = vulnerable to upsets
        "three_pt_xfactor": 0.6,          # Composite mismatch factor
    }

    z = 0
    for i, name in enumerate(FEATURE_NAMES):
        z += weights.get(name, 0) * features[i]

    return 1 / (1 + math.exp(-z))


def ensemble_predict(team1, team2, round_number=1, trained_model=None):
    """
    Ensemble prediction combining multiple model signals.

    Components:
    1. Historical seed probability (10-25% weight, decreases in later rounds)
    2. Logistic regression on features (25-35%)
    3. Trained ML model if available (30-40%)
    4. Market/spread signal (15-25%)
    """
    features = build_features(team1, team2, round_number)

    # Component 1: Seed history
    p_seed = seed_matchup_probability(team1.seed, team2.seed)

    # Component 2: Logistic baseline
    p_logistic = logistic_model(features)

    # Component 3: Trained model (XGBoost/GBM)
    p_ml = None
    if trained_model is not None and HAS_NUMPY:
        try:
            X = np.array(features).reshape(1, -1)
            p_ml = trained_model.predict_proba(X)[0][1]
        except Exception:
            p_ml = None

    # Component 4: Market signal
    p_market = 0.5
    if team1.spread is not None:
        p_market = 1 / (1 + math.exp(0.15 * team1.spread))
    elif team1.futures_odds and team2.futures_odds:
        total = team1.futures_odds + team2.futures_odds
        if total > 0:
            p_market = team1.futures_odds / total

    # Dynamic weights by round — reduced seed weight for more upset potential
    # Seed history goes from 15% in R64 down to 3% in Championship
    seed_weight = max(0.03, 0.15 - (round_number - 1) * 0.025)
    market_weight = 0.20
    if p_ml is not None:
        ml_weight = 0.35
        logistic_weight = 1.0 - seed_weight - market_weight - ml_weight
    else:
        ml_weight = 0.0
        logistic_weight = 1.0 - seed_weight - market_weight

    p_team1 = (
        seed_weight * p_seed +
        logistic_weight * p_logistic +
        ml_weight * (p_ml if p_ml is not None else 0.5) +
        market_weight * p_market
    )

    # Compute 3PT X-factor for reporting
    three_xf = compute_three_pt_xfactor(team1, team2) - compute_three_pt_xfactor(team2, team1)

    return p_team1, {
        "seed": round(p_seed, 3),
        "logistic": round(p_logistic, 3),
        "ml": round(p_ml, 3) if p_ml is not None else None,
        "market": round(p_market, 3),
        "three_pt_xfactor": round(three_xf, 3),
        "weights": {
            "seed": round(seed_weight, 2),
            "logistic": round(logistic_weight, 2),
            "ml": round(ml_weight, 2),
            "market": round(market_weight, 2),
        },
    }


# ============================================================
# ML Training
# ============================================================

def load_training_data(filepath):
    """
    Load historical tournament results for training.

    Expected CSV format:
    year,round,seed1,team1,adj_eff1,adj_off1,adj_def1,barthag1,...,seed2,team2,...,winner

    You can build this from:
    - kaggle.com/datasets (search "march madness" or "ncaa tournament")
    - sports-reference.com historical brackets
    - barttorvik.com historical data
    """
    if not os.path.exists(filepath):
        print(f"Training data not found: {filepath}")
        print("To train the model, create data/historical_games.csv")
        print("See README for format details.")
        return [], []

    X, y = [], []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Build team objects from CSV columns
                t1 = Team(
                    name=row["team1"], seed=int(row["seed1"]), region="",
                    adj_efficiency=float(row.get("adj_eff1", 0)),
                    adj_offense=float(row.get("adj_off1", 0)),
                    adj_defense=float(row.get("adj_def1", 0)),
                    barthag=float(row.get("barthag1", 0)),
                    effective_fg_pct=float(row.get("efg1", 0)),
                    turnover_pct=float(row.get("to_pct1", 0)),
                    off_rebound_pct=float(row.get("orb_pct1", 0)),
                    wins=int(row.get("wins1", 0)),
                    losses=int(row.get("losses1", 0)),
                    three_pt_pct=float(row.get("three_pct1", 0)),
                    opp_three_pt_pct=float(row.get("opp_three_pct1", 0)),
                )
                t2 = Team(
                    name=row["team2"], seed=int(row["seed2"]), region="",
                    adj_efficiency=float(row.get("adj_eff2", 0)),
                    adj_offense=float(row.get("adj_off2", 0)),
                    adj_defense=float(row.get("adj_def2", 0)),
                    barthag=float(row.get("barthag2", 0)),
                    effective_fg_pct=float(row.get("efg2", 0)),
                    turnover_pct=float(row.get("to_pct2", 0)),
                    off_rebound_pct=float(row.get("orb_pct2", 0)),
                    wins=int(row.get("wins2", 0)),
                    losses=int(row.get("losses2", 0)),
                    three_pt_pct=float(row.get("three_pct2", 0)),
                    opp_three_pt_pct=float(row.get("opp_three_pct2", 0)),
                )
                round_num = int(row.get("round", 1))
                features = build_features(t1, t2, round_num)
                label = 1 if row["winner"] == row["team1"] else 0

                X.append(features)
                y.append(label)
            except (KeyError, ValueError) as e:
                continue

    return X, y


def train_model(data_path=None):
    """
    Train the gradient boosted model on historical data.
    Saves the trained model to models/bracket_model.pkl
    """
    if not HAS_SKLEARN or not HAS_NUMPY:
        print("ERROR: scikit-learn and numpy required for training")
        print("Run: pip install scikit-learn numpy")
        return None

    if data_path is None:
        data_path = DATA_DIR / "historical_games.csv"

    X, y = load_training_data(data_path)
    if not X:
        return None

    X = np.array(X)
    y = np.array(y)
    print(f"Training on {len(X)} historical games...")

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train gradient boosted classifier
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_leaf=10,
        random_state=42,
    )

    # Cross-validate
    scores = cross_val_score(model, X_scaled, y, cv=5, scoring="accuracy")
    print(f"Cross-validation accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

    # Fit on full data
    model.fit(X_scaled, y)

    # Feature importances
    print("\nTop features:")
    importances = sorted(
        zip(FEATURE_NAMES, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )
    for name, imp in importances[:10]:
        print(f"  {name}: {imp:.3f}")

    # Save model
    MODEL_DIR.mkdir(exist_ok=True)
    model_path = MODEL_DIR / "bracket_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"model": model, "scaler": scaler}, f)
    print(f"\nModel saved to {model_path}")

    return model


def load_trained_model():
    """Load a previously trained model."""
    model_path = MODEL_DIR / "bracket_model.pkl"
    if not model_path.exists():
        return None
    if not HAS_SKLEARN:
        return None

    try:
        with open(model_path, "rb") as f:
            data = pickle.load(f)
        return data["model"]
    except Exception:
        return None


# ============================================================
# Bracket Simulation
# ============================================================

ROUND_NAMES = {
    1: "Round of 64",
    2: "Round of 32",
    3: "Sweet 16",
    4: "Elite Eight",
    5: "Final Four",
    6: "Championship",
}


def predict_game(team1, team2, round_name="Round of 64", round_number=1, trained_model=None):
    """Predict a single game using the ensemble model."""
    build_raptor_rating(team1)
    build_raptor_rating(team2)

    p_team1, factors = ensemble_predict(team1, team2, round_number, trained_model)

    winner = team1 if p_team1 > 0.5 else team2
    confidence = max(p_team1, 1 - p_team1)

    # Estimate spread from probability
    if p_team1 != 0.5:
        log_odds = math.log(p_team1 / (1 - p_team1)) if 0 < p_team1 < 1 else 0
        estimated_spread = round(-log_odds / 0.15, 1)
    else:
        estimated_spread = 0.0

    return Game(
        team1=team1,
        team2=team2,
        round_name=round_name,
        round_number=round_number,
        predicted_winner=winner.name,
        win_probability=round(p_team1, 3),
        predicted_spread=estimated_spread,
        confidence=round(confidence, 3),
        model_factors=factors,
    )


def simulate_bracket(teams, trained_model=None):
    """Simulate an entire 64-team bracket, round by round."""
    all_games = []
    current_teams = list(teams)

    for round_num in range(1, 7):
        round_name = ROUND_NAMES[round_num]
        next_round = []

        for i in range(0, len(current_teams), 2):
            if i + 1 >= len(current_teams):
                next_round.append(current_teams[i])
                continue

            game = predict_game(
                current_teams[i], current_teams[i + 1],
                round_name, round_num, trained_model,
            )
            all_games.append(game)

            winner = current_teams[i] if game.predicted_winner == current_teams[i].name else current_teams[i + 1]
            next_round.append(winner)

        current_teams = next_round
        if len(current_teams) <= 1:
            break

    return all_games


def populate_teams_from_data(teams, kenpom_data, spreads, futures):
    """Enrich team objects with data from all sources."""
    for team in teams:
        # Match KenPom/Barttorvik data
        kp = kenpom_data.get(team.name, {})
        if kp:
            team.adj_efficiency = kp.get("adj_efficiency", team.adj_efficiency)
            team.adj_offense = kp.get("adj_offense", team.adj_offense)
            team.adj_defense = kp.get("adj_defense", team.adj_defense)
            team.adj_tempo = kp.get("adj_tempo", team.adj_tempo)
            team.barthag = kp.get("barthag", team.barthag)
            team.elite_sos = kp.get("elite_sos", team.elite_sos)
            team.effective_fg_pct = kp.get("effective_fg_pct", team.effective_fg_pct)
            team.turnover_pct = kp.get("turnover_pct", team.turnover_pct)
            team.off_rebound_pct = kp.get("off_rebound_pct", team.off_rebound_pct)
            team.ft_rate = kp.get("ft_rate", team.ft_rate)
            team.opp_effective_fg_pct = kp.get("opp_effective_fg_pct", team.opp_effective_fg_pct)
            team.opp_turnover_pct = kp.get("opp_turnover_pct", team.opp_turnover_pct)
            team.opp_off_rebound_pct = kp.get("opp_off_rebound_pct", team.opp_off_rebound_pct)
            team.opp_ft_rate = kp.get("opp_ft_rate", team.opp_ft_rate)
            team.wins = kp.get("wins", team.wins)
            team.losses = kp.get("losses", team.losses)

        # Match spread data
        if team.name in spreads:
            team.spread = spreads[team.name]

        # Match futures data
        if team.name in futures:
            team.futures_odds = futures[team.name]

        # Build Raptor rating from all available data
        build_raptor_rating(team)


# ============================================================
# Output
# ============================================================

def print_predictions(games):
    """Print bracket predictions with model details."""
    current_round = ""
    for game in games:
        if game.round_name != current_round:
            current_round = game.round_name
            print(f"\n{'='*60}")
            print(f"  {current_round}")
            print(f"{'='*60}")

        conf = game.confidence
        marker = ">>>" if conf > 0.75 else ">>" if conf > 0.65 else ">"
        spread_str = f"({game.predicted_spread:+.1f})" if game.predicted_spread else ""

        print(
            f"  ({game.team1.seed}) {game.team1.name:<20} vs "
            f"({game.team2.seed}) {game.team2.name:<20} "
            f"{marker} {game.predicted_winner} {conf:.0%} {spread_str}"
        )

        # Show model breakdown for close games
        if conf < 0.70 and game.model_factors:
            f = game.model_factors
            parts = []
            if f.get("seed") is not None:
                parts.append(f"seed:{f['seed']:.0%}")
            if f.get("logistic") is not None:
                parts.append(f"stats:{f['logistic']:.0%}")
            if f.get("ml") is not None:
                parts.append(f"ml:{f['ml']:.0%}")
            if f.get("market") is not None and f["market"] != 0.5:
                parts.append(f"market:{f['market']:.0%}")
            if f.get("three_pt_xfactor") is not None and abs(f["three_pt_xfactor"]) > 0.01:
                sign = "+" if f["three_pt_xfactor"] > 0 else ""
                parts.append(f"3PT:{sign}{f['three_pt_xfactor']:.2f}")
            print(f"      Factors: {' | '.join(parts)}")


def save_bracket(games, filepath=BRACKET_FILE):
    """Save predictions to JSON."""
    output = []
    for g in games:
        output.append({
            "round": g.round_name,
            "round_number": g.round_number,
            "team1": {"name": g.team1.name, "seed": g.team1.seed, "region": g.team1.region},
            "team2": {"name": g.team2.name, "seed": g.team2.seed, "region": g.team2.region},
            "predicted_winner": g.predicted_winner,
            "win_probability": g.win_probability,
            "confidence": g.confidence,
            "predicted_spread": g.predicted_spread,
            "model_factors": g.model_factors,
        })
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nBracket saved to {filepath}")


# ============================================================
# Main / Demo
# ============================================================

def demo():
    """Demo the model with sample matchups showing all model components."""
    print("MARCH MADNESS BRACKET PREDICTOR")
    print("=" * 60)
    print("Multi-factor ensemble model")
    print(f"ML libraries: {'sklearn + numpy' if HAS_SKLEARN else 'not installed (using baseline)'}")
    print()

    # Sample teams with full stat profiles
    duke = Team(
        name="Duke", seed=1, region="East",
        wins=29, losses=4,
        adj_efficiency=30.5, adj_offense=120.3, adj_defense=89.8, adj_tempo=68.5,
        barthag=0.97, elite_sos=8.5,
        effective_fg_pct=0.555, turnover_pct=0.16, off_rebound_pct=0.33, ft_rate=0.38,
        opp_effective_fg_pct=0.44, opp_turnover_pct=0.20, opp_off_rebound_pct=0.25, opp_ft_rate=0.28,
        last_10_wins=9, last_10_losses=1, win_streak=7,
        conference="ACC", conference_strength=7.5, conf_tournament_champ=True,
        spread=-8.5, futures_odds=0.12,
        experience=2.8,
    )
    vermont = Team(
        name="Vermont", seed=16, region="East",
        wins=25, losses=8,
        adj_efficiency=5.2, adj_offense=105.1, adj_defense=99.9, adj_tempo=65.2,
        barthag=0.62, elite_sos=-5.2,
        effective_fg_pct=0.50, turnover_pct=0.19, off_rebound_pct=0.28, ft_rate=0.30,
        opp_effective_fg_pct=0.48, opp_turnover_pct=0.17, opp_off_rebound_pct=0.30, opp_ft_rate=0.32,
        last_10_wins=7, last_10_losses=3, win_streak=2,
        conference="AEC", conference_strength=2.1, conf_tournament_champ=True,
        spread=8.5, futures_odds=0.001,
        experience=3.2,
    )
    michigan_st = Team(
        name="Michigan St", seed=7, region="East",
        wins=22, losses=11,
        adj_efficiency=15.8, adj_offense=112.5, adj_defense=96.7, adj_tempo=67.1,
        barthag=0.82, elite_sos=6.8,
        effective_fg_pct=0.52, turnover_pct=0.17, off_rebound_pct=0.31, ft_rate=0.33,
        opp_effective_fg_pct=0.47, opp_turnover_pct=0.18, opp_off_rebound_pct=0.28, opp_ft_rate=0.30,
        last_10_wins=6, last_10_losses=4, win_streak=1,
        conference="Big Ten", conference_strength=8.2,
        spread=-1.5, futures_odds=0.02,
        experience=2.5,
    )
    usc = Team(
        name="USC", seed=10, region="East",
        wins=21, losses=12,
        adj_efficiency=12.3, adj_offense=110.8, adj_defense=98.5, adj_tempo=69.3,
        barthag=0.76, elite_sos=5.1,
        effective_fg_pct=0.51, turnover_pct=0.18, off_rebound_pct=0.29, ft_rate=0.31,
        opp_effective_fg_pct=0.48, opp_turnover_pct=0.17, opp_off_rebound_pct=0.29, opp_ft_rate=0.31,
        last_10_wins=5, last_10_losses=5, loss_streak=2,
        conference="Big Ten", conference_strength=8.2,
        spread=1.5, futures_odds=0.008,
        experience=2.2,
    )

    trained_model = load_trained_model()

    games = [
        predict_game(duke, vermont, "Round of 64", 1, trained_model),
        predict_game(michigan_st, usc, "Round of 64", 1, trained_model),
    ]

    print("Demo: Sample First Round Matchups")
    print_predictions(games)

    # Simulate second round
    w1 = duke if games[0].predicted_winner == "Duke" else vermont
    w2 = michigan_st if games[1].predicted_winner == "Michigan St" else usc

    r2 = predict_game(w1, w2, "Round of 32", 2, trained_model)
    print_predictions([r2])

    print("\n" + "-" * 60)
    print("To use with real data:")
    print("  1. pip install scikit-learn numpy")
    print("  2. Add training data to data/historical_games.csv")
    print("  3. python bracket_model.py --train")
    print("  4. Set ODDS_API_KEY env var for live market data")
    print("  5. Update teams list with actual tournament field")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--train":
        train_model()
    elif len(sys.argv) > 1 and sys.argv[1] == "--fetch":
        print("Fetching data from all sources...")
        kenpom = fetch_kenpom_data()
        spreads, futures = fetch_odds_data()
        print(f"Got efficiency data for {len(kenpom)} teams")
        print(f"Got spreads for {len(spreads)} teams")
        print(f"Got futures for {len(futures)} teams")
        DATA_DIR.mkdir(exist_ok=True)
        with open(DATA_DIR / "kenpom_latest.json", "w") as f:
            json.dump(kenpom, f, indent=2)
        print(f"Data saved to {DATA_DIR}")
    else:
        demo()
