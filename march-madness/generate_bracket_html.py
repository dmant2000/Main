#!/usr/bin/env python3
"""Generate a visual HTML bracket for 2026 March Madness predictions."""

import json

def load_bracket():
    with open("bracket_2026.json") as f:
        return json.load(f)

def organize_games(games):
    regions = {}
    final_four = []
    championship = None
    for g in games:
        rnd = g["round"]
        if rnd == "Championship":
            championship = g
        elif rnd == "Final Four":
            final_four.append(g)
        else:
            region = g["team1"]["region"]
            if region not in regions:
                regions[region] = {}
            if rnd not in regions[region]:
                regions[region][rnd] = []
            regions[region][rnd].append(g)
    return regions, final_four, championship

def team_html(name, seed, is_winner, prob=None, spread=None):
    cls = "team winner" if is_winner else "team"
    prob_str = f'<span class="prob">{prob*100:.0f}%</span>' if prob and is_winner else ''
    spread_str = f'<span class="spread">[{spread:+.1f}]</span>' if spread and is_winner else ''
    return f'<div class="{cls}"><span class="seed">({seed})</span> {name} {prob_str} {spread_str}</div>'

def matchup_html(g):
    t1, t2 = g["team1"], g["team2"]
    winner = g["predicted_winner"]
    prob = g["win_probability"]
    spread = g["predicted_spread"]
    w1 = winner == t1["name"]
    wp = prob if w1 else 1 - prob
    sp = spread if w1 else -spread

    return f'''<div class="matchup">
        {team_html(t1["name"], t1["seed"], w1, wp, sp)}
        {team_html(t2["name"], t2["seed"], not w1, wp, sp)}
    </div>'''

def generate_html(regions, final_four, championship):
    round_order = ["Round of 64", "Round of 32", "Sweet 16", "Elite Eight"]
    region_order = ["East", "West", "South", "Midwest"]

    # Find champion
    champ = championship["predicted_winner"]
    champ_seed = championship["team1"]["seed"] if championship["predicted_winner"] == championship["team1"]["name"] else championship["team2"]["seed"]
    champ_prob = championship["win_probability"]
    if championship["predicted_winner"] != championship["team1"]["name"]:
        champ_prob = 1 - champ_prob

    region_sections = ""
    for region in region_order:
        if region not in regions:
            continue
        rounds_html = ""
        for rnd in round_order:
            if rnd not in regions[region]:
                continue
            games_html = "".join(matchup_html(g) for g in regions[region][rnd])
            rounds_html += f'''
            <div class="round">
                <h3>{rnd}</h3>
                {games_html}
            </div>'''

        region_sections += f'''
        <div class="region">
            <h2>{region} Region</h2>
            {rounds_html}
        </div>'''

    ff_html = "".join(matchup_html(g) for g in final_four)
    champ_html = matchup_html(championship)

    # Build upset list
    upsets = []
    games = list(load_bracket())
    for g in games:
        t1, t2 = g["team1"], g["team2"]
        w = g["predicted_winner"]
        if w == t1["name"] and t1["seed"] > t2["seed"]:
            upsets.append((g["round"], t1["seed"], t1["name"], t2["seed"], t2["name"]))
        elif w == t2["name"] and t2["seed"] > t1["seed"]:
            upsets.append((g["round"], t2["seed"], t2["name"], t1["seed"], t1["name"]))

    upset_rows = "".join(
        f'<tr><td>({ws}) {wn}</td><td>over</td><td>({ls}) {ln}</td><td>{rnd}</td></tr>'
        for rnd, ws, wn, ls, ln in upsets
    )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 March Madness Bracket Predictions</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: #fff;
        min-height: 100vh;
        padding: 20px;
    }}
    h1 {{
        text-align: center;
        font-size: 2.2em;
        margin-bottom: 10px;
        background: linear-gradient(90deg, #ff6b35, #f7c948, #ff6b35);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-transform: uppercase;
        letter-spacing: 3px;
    }}
    .subtitle {{
        text-align: center;
        color: #8892b0;
        margin-bottom: 30px;
        font-size: 0.95em;
    }}
    .champion-banner {{
        text-align: center;
        background: linear-gradient(135deg, #f7c948 0%, #ff6b35 100%);
        color: #1a1a2e;
        padding: 20px 40px;
        border-radius: 12px;
        margin: 0 auto 30px;
        max-width: 500px;
        box-shadow: 0 8px 32px rgba(247, 201, 72, 0.3);
    }}
    .champion-banner h2 {{ font-size: 1.6em; margin-bottom: 5px; }}
    .champion-banner .champ-details {{ font-size: 1.1em; font-weight: 600; }}
    .region {{
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
        border: 1px solid rgba(255,255,255,0.1);
    }}
    .region h2 {{
        font-size: 1.4em;
        margin-bottom: 15px;
        color: #f7c948;
        border-bottom: 2px solid rgba(247,201,72,0.3);
        padding-bottom: 8px;
    }}
    .round {{
        margin-bottom: 20px;
    }}
    .round h3 {{
        color: #8892b0;
        font-size: 0.95em;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }}
    .matchup {{
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        margin-bottom: 8px;
        overflow: hidden;
    }}
    .team {{
        padding: 8px 14px;
        font-size: 0.92em;
        display: flex;
        align-items: center;
        gap: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        color: #8892b0;
    }}
    .team:last-child {{ border-bottom: none; }}
    .team.winner {{
        background: rgba(72, 199, 142, 0.15);
        color: #48c78e;
        font-weight: 600;
    }}
    .seed {{
        color: #f7c948;
        font-weight: 700;
        font-size: 0.85em;
        min-width: 30px;
    }}
    .winner .seed {{ color: #f7c948; }}
    .prob {{
        margin-left: auto;
        background: rgba(72,199,142,0.2);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: 700;
    }}
    .spread {{
        font-size: 0.8em;
        color: #48c78e;
        opacity: 0.8;
    }}
    .final-four-section {{
        background: rgba(247,201,72,0.08);
        border: 2px solid rgba(247,201,72,0.3);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
    }}
    .final-four-section h2 {{
        color: #f7c948;
        text-align: center;
        font-size: 1.5em;
        margin-bottom: 15px;
    }}
    .championship-section {{
        background: rgba(255,107,53,0.08);
        border: 2px solid rgba(255,107,53,0.3);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
    }}
    .championship-section h2 {{
        color: #ff6b35;
        text-align: center;
        font-size: 1.5em;
        margin-bottom: 15px;
    }}
    .upsets {{
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(255,107,53,0.3);
    }}
    .upsets h2 {{
        color: #ff6b35;
        margin-bottom: 15px;
        font-size: 1.3em;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
    }}
    table td {{
        padding: 8px 12px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        font-size: 0.92em;
    }}
    table tr td:nth-child(2) {{
        color: #8892b0;
        text-align: center;
        font-style: italic;
    }}
    table tr td:last-child {{
        color: #8892b0;
        text-align: right;
        font-size: 0.85em;
    }}
    .footer {{
        text-align: center;
        color: #4a5568;
        margin-top: 30px;
        font-size: 0.8em;
    }}
</style>
</head>
<body>
    <h1>2026 March Madness</h1>
    <p class="subtitle">ML-Powered Bracket Predictions &middot; GBM Model &middot; 67.9% CV Accuracy</p>

    <div class="champion-banner">
        <h2>Predicted Champion</h2>
        <div class="champ-details">({champ_seed}) {champ} &mdash; {champ_prob*100:.0f}% Confidence</div>
    </div>

    {region_sections}

    <div class="final-four-section">
        <h2>Final Four</h2>
        {ff_html}
    </div>

    <div class="championship-section">
        <h2>National Championship</h2>
        {champ_html}
    </div>

    <div class="upsets">
        <h2>Upset Picks</h2>
        <table>
            {upset_rows}
        </table>
    </div>

    <div class="footer">
        Generated by March Madness Bot &middot; Data: 630 historical games (2015-2025)
    </div>
</body>
</html>'''
    return html

def main():
    games = load_bracket()
    regions, final_four, championship = organize_games(games)
    html = generate_html(regions, final_four, championship)
    with open("bracket_2026.html", "w") as f:
        f.write(html)
    print("Bracket saved to bracket_2026.html")
    print("Open it in your browser: open bracket_2026.html")

if __name__ == "__main__":
    main()
