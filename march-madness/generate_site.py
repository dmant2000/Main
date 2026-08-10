#!/usr/bin/env python3
"""Generate GitHub Pages site for 2026 March Madness bracket."""

import json
import shutil

def load_bracket():
    with open("bracket_2026.json") as f:
        return json.load(f)

def load_stats():
    with open("data/team_stats_2026.json") as f:
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

def get_upsets(games):
    upsets = []
    for g in games:
        t1, t2 = g["team1"], g["team2"]
        w = g["predicted_winner"]
        if w == t1["name"] and t1["seed"] > t2["seed"]:
            upsets.append(g)
        elif w == t2["name"] and t2["seed"] > t1["seed"]:
            upsets.append(g)
    return upsets

def matchup_html(g):
    t1, t2 = g["team1"], g["team2"]
    winner = g["predicted_winner"]
    prob = g["win_probability"]
    spread = g["predicted_spread"]

    def team_row(team, is_winner, wp, sp):
        cls = "team winner" if is_winner else "team loser"
        prob_badge = f'<span class="prob">{wp*100:.0f}%</span>' if is_winner else ''
        spread_badge = f'<span class="spread">{sp:+.1f}</span>' if is_winner else ''
        return f'''<div class="{cls}">
            <span class="seed">{team["seed"]}</span>
            <span class="name">{team["name"]}</span>
            {prob_badge}{spread_badge}
        </div>'''

    w1 = winner == t1["name"]
    wp = prob if w1 else 1 - prob
    sp = spread if w1 else -spread

    return f'''<div class="matchup">
        {team_row(t1, w1, wp, sp)}
        {team_row(t2, not w1, wp, sp)}
    </div>'''

def generate_site():
    games = load_bracket()
    stats = load_stats()
    teams = stats["teams"]
    regions, final_four, championship = organize_games(games)

    champ = championship["predicted_winner"]
    cs = championship["team1"]["seed"] if champ == championship["team1"]["name"] else championship["team2"]["seed"]
    cp = championship["win_probability"]
    if champ != championship["team1"]["name"]:
        cp = 1 - cp

    upsets = get_upsets(games)
    upset_html = ""
    for g in upsets:
        t1, t2 = g["team1"], g["team2"]
        w = g["predicted_winner"]
        ws = t1["seed"] if w == t1["name"] else t2["seed"]
        ls = t2["seed"] if w == t1["name"] else t1["seed"]
        ln = t2["name"] if w == t1["name"] else t1["name"]
        upset_html += f'<div class="upset-row"><span class="upset-winner">({ws}) {w}</span> over <span class="upset-loser">({ls}) {ln}</span><span class="upset-round">{g["round"]}</span></div>\n'

    # Injuries
    injury_html = ""
    for team_name in ["North Carolina", "Michigan", "Duke"]:
        if team_name in teams:
            t = teams[team_name]
            imp = t.get("injury_impact", 0)
            notes = t.get("notes", "")
            injury_html += f'<div class="injury-card"><div class="injury-team">{team_name}</div><div class="injury-impact">{imp:+.1f} pts</div><div class="injury-notes">{notes}</div></div>\n'

    # 3pt leaders
    shooters = sorted(
        [(name, d["three_pt_pct"], d.get("has_elite_shooter", False), d.get("three_pt_rate", 0))
         for name, d in teams.items()],
        key=lambda x: x[1], reverse=True
    )
    shooter_html = ""
    for name, pct, elite, rate in shooters[:10]:
        tag = ' <span class="elite-tag">ELITE</span>' if elite else ''
        bar_w = (pct - 0.30) / 0.12 * 100  # scale 30%-42% to 0-100%
        shooter_html += f'''<div class="shooter-row">
            <span class="shooter-name">{name}{tag}</span>
            <div class="bar-bg"><div class="bar-fill" style="width:{bar_w:.0f}%"></div></div>
            <span class="shooter-pct">{pct:.1%}</span>
        </div>\n'''

    region_order = ["East", "West", "South", "Midwest"]
    round_order = ["Round of 64", "Round of 32", "Sweet 16", "Elite Eight"]

    regions_html = ""
    for region in region_order:
        if region not in regions:
            continue
        rounds_html = ""
        for rnd in round_order:
            if rnd not in regions[region]:
                continue
            games_html = "".join(matchup_html(g) for g in regions[region][rnd])
            short_name = rnd.replace("Round of ", "R")
            rounds_html += f'<div class="round"><div class="round-label">{short_name}</div><div class="round-games">{games_html}</div></div>'

        regions_html += f'''
        <div class="region" id="{region.lower()}">
            <div class="region-header">{region}</div>
            <div class="region-rounds">{rounds_html}</div>
        </div>'''

    ff_html = "".join(matchup_html(g) for g in final_four)
    champ_html = matchup_html(championship)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta property="og:title" content="2026 March Madness Bracket Predictions">
<meta property="og:description" content="ML-powered bracket picks. Predicted champion: ({cs}) {champ}">
<meta property="og:type" content="website">
<title>2026 March Madness Bracket Predictions</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
:root {{
    --bg: #0f1123;
    --card: #1a1f3a;
    --card-hover: #222850;
    --gold: #f7c948;
    --green: #48c78e;
    --orange: #ff6b35;
    --white: #e8ecf5;
    --gray: #6b7394;
    --border: #2a3158;
    --winner-bg: #1a3a2a;
}}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--white);
    line-height: 1.5;
    overflow-x: hidden;
}}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}

/* Header */
header {{
    text-align: center;
    padding: 40px 20px 20px;
    background: linear-gradient(180deg, #161938 0%, var(--bg) 100%);
}}
h1 {{
    font-size: clamp(1.6rem, 5vw, 2.8rem);
    background: linear-gradient(90deg, var(--gold), var(--orange), var(--gold));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 8px;
}}
.subtitle {{ color: var(--gray); font-size: 0.95rem; }}

/* Champion Banner */
.champion {{
    text-align: center;
    margin: 30px auto;
    max-width: 520px;
    background: linear-gradient(135deg, rgba(247,201,72,0.15), rgba(255,107,53,0.15));
    border: 2px solid var(--gold);
    border-radius: 16px;
    padding: 24px;
    animation: glow 3s ease-in-out infinite alternate;
}}
@keyframes glow {{
    from {{ box-shadow: 0 0 20px rgba(247,201,72,0.1); }}
    to {{ box-shadow: 0 0 40px rgba(247,201,72,0.25); }}
}}
.champion h2 {{ color: var(--gold); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px; }}
.champion .champ-name {{ font-size: 1.8rem; font-weight: 800; color: var(--white); }}
.champion .champ-conf {{ color: var(--gold); font-size: 1rem; margin-top: 4px; }}

/* Navigation Tabs */
.tabs {{
    display: flex;
    justify-content: center;
    gap: 8px;
    margin: 30px 0 20px;
    flex-wrap: wrap;
    padding: 0 10px;
}}
.tab {{
    padding: 10px 20px;
    border-radius: 8px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--gray);
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    transition: all 0.2s;
}}
.tab:hover, .tab.active {{
    background: var(--card-hover);
    color: var(--gold);
    border-color: var(--gold);
}}

/* Sections */
.section {{ display: none; }}
.section.active {{ display: block; }}

/* Regions */
.region {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 24px;
    overflow: hidden;
}}
.region-header {{
    background: linear-gradient(90deg, rgba(247,201,72,0.1), transparent);
    padding: 14px 20px;
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--gold);
    border-bottom: 1px solid var(--border);
}}
.region-rounds {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1px;
    background: var(--border);
}}
.round {{
    background: var(--bg);
    padding: 12px;
}}
.round-label {{
    color: var(--gray);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
    margin-bottom: 10px;
}}

/* Matchups */
.matchup {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
    transition: transform 0.15s;
}}
.matchup:hover {{ transform: translateY(-1px); border-color: rgba(247,201,72,0.3); }}
.team {{
    display: flex;
    align-items: center;
    padding: 8px 12px;
    gap: 8px;
    font-size: 0.88rem;
}}
.team + .team {{ border-top: 1px solid var(--border); }}
.team.winner {{
    background: var(--winner-bg);
    font-weight: 600;
}}
.team.winner .name {{ color: var(--green); }}
.team.loser .name {{ color: var(--gray); }}
.seed {{
    background: rgba(247,201,72,0.15);
    color: var(--gold);
    font-weight: 700;
    font-size: 0.75rem;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    flex-shrink: 0;
}}
.name {{ flex: 1; }}
.prob {{
    background: rgba(72,199,142,0.2);
    color: var(--green);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
}}
.spread {{
    color: var(--gray);
    font-size: 0.75rem;
}}

/* Final Four */
.ff-section {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    margin: 20px 0;
}}
.ff-label, .champ-label {{
    text-align: center;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--orange);
    margin: 30px 0 10px;
    text-transform: uppercase;
    letter-spacing: 2px;
}}
.champ-matchup {{
    max-width: 400px;
    margin: 0 auto;
}}

/* Insights Cards */
.insights-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
    margin-top: 20px;
}}
.insight-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
}}
.insight-card h3 {{
    color: var(--orange);
    font-size: 1rem;
    margin-bottom: 14px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* Upsets */
.upset-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
}}
.upset-winner {{ color: var(--green); font-weight: 600; }}
.upset-loser {{ color: var(--gray); }}
.upset-round {{ margin-left: auto; color: var(--gray); font-size: 0.8rem; }}

/* Injuries */
.injury-card {{
    background: rgba(255,107,53,0.05);
    border: 1px solid rgba(255,107,53,0.2);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
}}
.injury-team {{ font-weight: 700; color: var(--white); }}
.injury-impact {{ color: var(--orange); font-weight: 700; font-size: 1.1rem; }}
.injury-notes {{ color: var(--gray); font-size: 0.85rem; margin-top: 4px; }}

/* Shooters */
.shooter-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    font-size: 0.88rem;
}}
.shooter-name {{ width: 140px; flex-shrink: 0; }}
.bar-bg {{
    flex: 1;
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
}}
.bar-fill {{
    height: 100%;
    background: linear-gradient(90deg, var(--green), var(--gold));
    border-radius: 4px;
}}
.shooter-pct {{ width: 50px; text-align: right; color: var(--gold); font-weight: 600; }}
.elite-tag {{
    background: var(--gold);
    color: var(--bg);
    font-size: 0.6rem;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 700;
    vertical-align: middle;
}}

/* Footer */
footer {{
    text-align: center;
    color: var(--gray);
    padding: 40px 20px;
    font-size: 0.8rem;
}}

@media (max-width: 600px) {{
    .region-rounds {{ grid-template-columns: 1fr; }}
    .tabs {{ gap: 4px; }}
    .tab {{ padding: 8px 14px; font-size: 0.8rem; }}
    .champion .champ-name {{ font-size: 1.4rem; }}
}}
</style>
</head>
<body>

<header>
    <h1>March Madness 2026</h1>
    <p class="subtitle">ML-Powered Bracket Predictions &bull; GBM Model &bull; 67.9% CV Accuracy</p>
</header>

<div class="container">
    <div class="champion">
        <h2>Predicted Champion</h2>
        <div class="champ-name">({cs}) {champ}</div>
        <div class="champ-conf">{cp*100:.0f}% Championship Probability</div>
    </div>

    <div class="tabs">
        <div class="tab active" data-tab="bracket">Full Bracket</div>
        <div class="tab" data-tab="ff">Final Four</div>
        <div class="tab" data-tab="insights">Insights</div>
        <div class="tab" data-tab="upsets">Upsets</div>
    </div>

    <!-- Bracket Tab -->
    <div class="section active" id="bracket">
        {regions_html}
    </div>

    <!-- Final Four Tab -->
    <div class="section" id="ff">
        <div class="ff-label">Final Four</div>
        <div class="ff-section">{ff_html}</div>
        <div class="champ-label">Championship</div>
        <div class="champ-matchup">{champ_html}</div>
    </div>

    <!-- Insights Tab -->
    <div class="section" id="insights">
        <div class="insights-grid">
            <div class="insight-card">
                <h3>Injury Report</h3>
                {injury_html}
            </div>
            <div class="insight-card">
                <h3>Top 3-Point Shooting</h3>
                {shooter_html}
            </div>
        </div>
    </div>

    <!-- Upsets Tab -->
    <div class="section" id="upsets">
        <div class="insight-card">
            <h3>Predicted Upsets</h3>
            {upset_html}
        </div>
    </div>
</div>

<footer>
    Generated by March Madness Bot &bull; Data: 630 historical games (2015-2025) &bull; Model: Gradient Boosted Machine
</footer>

<script>
document.querySelectorAll('.tab').forEach(tab => {{
    tab.addEventListener('click', () => {{
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    }});
}});
</script>

</body>
</html>'''

    with open("docs/index.html", "w") as f:
        f.write(html)
    print("Site generated at docs/index.html")

    # Copy bracket image to docs
    shutil.copy("bracket_2026.png", "docs/bracket_2026.png")
    print("Copied bracket_2026.png to docs/")

if __name__ == "__main__":
    generate_site()
