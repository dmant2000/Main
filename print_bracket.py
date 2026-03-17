#!/usr/bin/env python3
"""Visual ASCII bracket display for 2026 March Madness predictions."""

import json

def load_bracket():
    with open("bracket_2026.json") as f:
        return json.load(f)

def fmt_team(name, seed, prob=None, spread=None, winner=False):
    """Format a team line."""
    marker = ">>>" if winner else "   "
    s = f"{marker} ({seed:>2}) {name:<22}"
    if prob is not None:
        s += f" {prob*100:4.0f}%"
    if spread is not None:
        s += f" [{spread:+.1f}]"
    return s

def get_games_by_region_round(games):
    """Organize games by region and round."""
    result = {}
    for g in games:
        region = g["team1"].get("region", "Final Four")
        rnd = g["round"]
        key = (region, rnd)
        if key not in result:
            result[key] = []
        result[key].append(g)
    return result

def print_region_bracket(region, games_by_rr):
    rounds = ["Round of 64", "Round of 32", "Sweet 16", "Elite Eight"]

    print(f"\n{'='*70}")
    print(f"  {region.upper()} REGION")
    print(f"{'='*70}")

    for rnd in rounds:
        key = (region, rnd)
        if key not in games_by_rr:
            continue
        games = games_by_rr[key]

        print(f"\n  {rnd}")
        print(f"  {'─'*66}")

        for g in games:
            t1 = g["team1"]
            t2 = g["team2"]
            winner = g["predicted_winner"]
            prob = g["win_probability"]
            spread = g["predicted_spread"]

            w1 = winner == t1["name"]
            w2 = winner == t2["name"]

            wp = prob if w1 else 1 - prob
            sp = spread if w1 else -spread

            line1 = fmt_team(t1["name"], t1["seed"], wp if w1 else None, sp if w1 else None, w1)
            line2 = fmt_team(t2["name"], t2["seed"], wp if w2 else None, sp if w2 else None, w2)

            print(f"  │ {line1}")
            print(f"  │ {line2}")
            print(f"  │{'─'*65}")

def print_final_four(games_by_rr):
    ff_games = []
    champ_game = None

    for (region, rnd), games in games_by_rr.items():
        if rnd == "Final Four":
            ff_games.extend(games)
        elif rnd == "Championship":
            champ_game = games[0]

    print(f"\n{'='*70}")
    print(f"  FINAL FOUR")
    print(f"{'='*70}")
    print(f"  {'─'*66}")

    for g in ff_games:
        t1 = g["team1"]
        t2 = g["team2"]
        winner = g["predicted_winner"]
        prob = g["win_probability"]
        spread = g["predicted_spread"]

        w1 = winner == t1["name"]
        w2 = winner == t2["name"]
        wp = prob if w1 else 1 - prob
        sp = spread if w1 else -spread

        line1 = fmt_team(t1["name"], t1["seed"], wp if w1 else None, sp if w1 else None, w1)
        line2 = fmt_team(t2["name"], t2["seed"], wp if w2 else None, sp if w2 else None, w2)

        print(f"  │ {line1}")
        print(f"  │ {line2}")
        print(f"  │{'─'*65}")

    if champ_game:
        g = champ_game
        t1 = g["team1"]
        t2 = g["team2"]
        winner = g["predicted_winner"]
        prob = g["win_probability"]
        spread = g["predicted_spread"]

        w1 = winner == t1["name"]
        wp = prob if w1 else 1 - prob
        sp = spread if w1 else -spread

        print(f"\n{'='*70}")
        print(f"  NATIONAL CHAMPIONSHIP")
        print(f"{'='*70}")
        print(f"  {'─'*66}")

        w2 = not w1
        line1 = fmt_team(t1["name"], t1["seed"], wp if w1 else None, sp if w1 else None, w1)
        line2 = fmt_team(t2["name"], t2["seed"], wp if w2 else None, sp if w2 else None, w2)

        print(f"  │ {line1}")
        print(f"  │ {line2}")
        print(f"  │{'─'*65}")

        print(f"\n  {'★'*30}")
        print(f"  ★  PREDICTED CHAMPION: ({t1['seed'] if w1 else t2['seed']}) {winner:<16} ★")
        print(f"  ★  Confidence: {wp*100:.0f}%{' '*24}★")
        print(f"  {'★'*30}")

def print_summary(games):
    """Print upset picks and summary stats."""
    upsets = []
    for g in games:
        t1 = g["team1"]
        t2 = g["team2"]
        winner = g["predicted_winner"]
        if winner == t1["name"] and t1["seed"] > t2["seed"]:
            upsets.append((g["round"], t1["seed"], t1["name"], t2["seed"], t2["name"], g["win_probability"]))
        elif winner == t2["name"] and t2["seed"] > t1["seed"]:
            upsets.append((g["round"], t2["seed"], t2["name"], t1["seed"], t1["name"], g["win_probability"]))

    if upsets:
        print(f"\n{'='*70}")
        print(f"  UPSET PICKS")
        print(f"{'='*70}")
        for rnd, ws, wname, ls, lname, prob in sorted(upsets, key=lambda x: x[1], reverse=True):
            print(f"  ({ws:>2}) {wname:<20} over ({ls:>2}) {lname:<20} [{rnd}]")

def main():
    games = load_bracket()
    games_by_rr = get_games_by_region_round(games)

    regions = ["East", "West", "South", "Midwest"]
    for region in regions:
        print_region_bracket(region, games_by_rr)

    print_final_four(games_by_rr)
    print_summary(games)
    print()

if __name__ == "__main__":
    main()
