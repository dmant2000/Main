#!/usr/bin/env python3
"""Generate a shareable PNG bracket image for 2026 March Madness predictions."""

import json
from PIL import Image, ImageDraw, ImageFont

# Colors
BG = (20, 24, 45)
CARD_BG = (30, 38, 65)
WINNER_BG = (30, 70, 55)
GOLD = (247, 201, 72)
GREEN = (72, 199, 142)
ORANGE = (255, 107, 53)
WHITE = (255, 255, 255)
GRAY = (136, 146, 176)
DARK_LINE = (50, 60, 90)
CHAMP_BG = (60, 40, 15)

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

def get_font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

def get_font_regular(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

def draw_matchup(draw, x, y, game, w=320, h=52):
    """Draw a single matchup box. Returns height used."""
    t1, t2 = game["team1"], game["team2"]
    winner = game["predicted_winner"]
    prob = game["win_probability"]

    font = get_font(13)
    font_sm = get_font_regular(11)
    seed_font = get_font(11)

    row_h = h // 2

    for i, team in enumerate([t1, t2]):
        ty = y + i * row_h
        is_winner = team["name"] == winner

        # Background
        bg = WINNER_BG if is_winner else CARD_BG
        draw.rounded_rectangle([x, ty, x + w, ty + row_h - 1], radius=4 if (i == 0 or i == 1) else 0, fill=bg)

        # Seed
        seed_text = f"({team['seed']})"
        draw.text((x + 8, ty + (row_h - 14) // 2), seed_text, fill=GOLD, font=seed_font)

        # Name
        name_color = GREEN if is_winner else GRAY
        draw.text((x + 42, ty + (row_h - 14) // 2), team["name"], fill=name_color, font=font)

        # Probability for winner
        if is_winner:
            wp = prob if team == t1 else 1 - prob
            prob_text = f"{wp*100:.0f}%"
            bbox = draw.textbbox((0, 0), prob_text, font=font_sm)
            pw = bbox[2] - bbox[0]
            draw.text((x + w - pw - 10, ty + (row_h - 12) // 2), prob_text, fill=GREEN, font=font_sm)

    # Divider line
    draw.line([x, y + row_h, x + w, y + row_h], fill=DARK_LINE, width=1)

    return h

def draw_region(draw, x, y, region_name, region_data, max_width=700):
    """Draw a full region bracket."""
    round_order = ["Round of 64", "Round of 32", "Sweet 16", "Elite Eight"]
    title_font = get_font(18)
    round_font = get_font(12)

    # Region title
    draw.text((x, y), f"{region_name} Region", fill=GOLD, font=title_font)
    y += 30

    col_width = 340
    matchup_h = 54
    gap = 8

    for col, rnd in enumerate(round_order):
        if rnd not in region_data:
            continue
        games = region_data[rnd]

        cx = x + col * col_width
        cy = y

        # Round label
        draw.text((cx, cy), rnd, fill=GRAY, font=round_font)
        cy += 22

        for game in games:
            draw_matchup(draw, cx, cy, game, w=320, h=matchup_h)
            cy += matchup_h + gap

    num_r64 = len(region_data.get("Round of 64", []))
    region_height = 30 + 22 + num_r64 * (matchup_h + gap) + 10
    return region_height

def main():
    games = load_bracket()
    regions, final_four, championship = organize_games(games)

    region_order = ["East", "West", "South", "Midwest"]

    # Calculate layout - 2x2 grid of regions
    img_w = 1500
    region_col_w = 720
    matchup_h = 54
    gap = 8

    # Calculate max region height
    max_r64 = max(len(regions[r].get("Round of 64", [])) for r in region_order if r in regions)
    region_h = 30 + 22 + max_r64 * (matchup_h + gap) + 30

    # Header + 2 rows of regions + Final Four + Championship
    header_h = 120
    ff_h = 200
    img_h = header_h + region_h * 2 + ff_h + 80

    img = Image.new("RGB", (img_w, img_h), BG)
    draw = ImageDraw.Draw(img)

    # Header
    title_font = get_font(32)
    sub_font = get_font_regular(14)

    title = "2026 MARCH MADNESS PREDICTIONS"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((img_w - tw) // 2, 20), title, fill=GOLD, font=title_font)

    subtitle = "ML-Powered Bracket  |  GBM Model  |  67.9% CV Accuracy"
    bbox2 = draw.textbbox((0, 0), subtitle, font=sub_font)
    sw = bbox2[2] - bbox2[0]
    draw.text(((img_w - sw) // 2, 60), subtitle, fill=GRAY, font=sub_font)

    # Champion banner
    champ = championship["predicted_winner"]
    cs = championship["team1"]["seed"] if champ == championship["team1"]["name"] else championship["team2"]["seed"]
    cp = championship["win_probability"]
    if champ != championship["team1"]["name"]:
        cp = 1 - cp
    champ_font = get_font(20)
    champ_text = f"PREDICTED CHAMPION: ({cs}) {champ} — {cp*100:.0f}% Confidence"
    bbox3 = draw.textbbox((0, 0), champ_text, font=champ_font)
    cw = bbox3[2] - bbox3[0]
    ch = bbox3[3] - bbox3[1]
    cx = (img_w - cw) // 2
    # Banner background
    draw.rounded_rectangle([cx - 20, 82, cx + cw + 20, 82 + ch + 16], radius=8, fill=CHAMP_BG, outline=GOLD)
    draw.text((cx, 88), champ_text, fill=GOLD, font=champ_font)

    # Regions in 2x2 grid
    positions = [
        (30, header_h),               # East (top-left)
        (img_w // 2 + 15, header_h),  # West (top-right)
        (30, header_h + region_h),    # South (bottom-left)
        (img_w // 2 + 15, header_h + region_h),  # Midwest (bottom-right)
    ]

    for i, region in enumerate(region_order):
        if region in regions:
            # Only draw Round of 64 and Round of 32 to fit
            limited = {}
            for rnd in ["Round of 64", "Round of 32"]:
                if rnd in regions[region]:
                    limited[rnd] = regions[region][rnd]
            px, py = positions[i]
            draw_region(draw, px, py, region, limited, max_width=region_col_w)

    # Final Four & Championship at bottom
    ff_y = header_h + region_h * 2 + 10
    ff_font = get_font(20)

    draw.text((img_w // 2 - 300, ff_y), "FINAL FOUR", fill=ORANGE, font=ff_font)
    ff_y += 30
    for i, g in enumerate(final_four):
        fx = img_w // 2 - 300 + i * 340
        draw_matchup(draw, fx, ff_y, g, w=320, h=matchup_h)

    # Championship
    champ_y = ff_y + matchup_h + 20
    draw.text((img_w // 2 - 170, champ_y), "CHAMPIONSHIP", fill=ORANGE, font=ff_font)
    champ_y += 30
    draw_matchup(draw, img_w // 2 - 160, champ_y, championship, w=320, h=matchup_h)

    # Upset picks at bottom-right
    upset_font = get_font(14)
    upset_sm = get_font_regular(12)
    uy = header_h + region_h * 2 + 10
    ux = img_w - 420

    draw.text((ux, uy), "KEY UPSETS", fill=ORANGE, font=upset_font)
    uy += 24

    for g in games:
        t1, t2 = g["team1"], g["team2"]
        w = g["predicted_winner"]
        ws = t1["seed"] if w == t1["name"] else t2["seed"]
        ls = t2["seed"] if w == t1["name"] else t1["seed"]
        ln = t2["name"] if w == t1["name"] else t1["name"]
        if ws > ls:
            text = f"({ws}) {w} over ({ls}) {ln}"
            draw.text((ux, uy), text, fill=WHITE, font=upset_sm)
            uy += 18
            if uy > img_h - 20:
                break

    # Footer
    footer_font = get_font_regular(11)
    draw.text((30, img_h - 25), "Generated by March Madness Bot  •  Data: 630 historical games (2015-2025)", fill=(70, 80, 100), font=footer_font)

    img.save("bracket_2026.png", "PNG", quality=95)
    print(f"Saved bracket_2026.png ({img_w}x{img_h})")

if __name__ == "__main__":
    main()
