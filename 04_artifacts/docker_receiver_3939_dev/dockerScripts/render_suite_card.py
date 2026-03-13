import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont


DIFF_ORDER = ["easy", "normal", "hard", "expert", "master", "append"]
DIFF_COLOR = {
    "easy": (93, 205, 101),
    "normal": (87, 175, 238),
    "hard": (245, 188, 61),
    "expert": (237, 96, 143),
    "master": (174, 106, 220),
    "append": (153, 123, 208),
}


def _load_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _extract_stats(suite: dict) -> Tuple[dict, List[str]]:
    missing = []
    user = suite.get("userGamedata") or {}
    profile = suite.get("userProfile") or {}

    if not user:
        missing.append("userGamedata")
    if not profile:
        missing.append("userProfile")

    name = user.get("name", "Unknown")
    rank = user.get("rank", 0)
    twitter = profile.get("twitterId", "")
    word = profile.get("word", "")

    # MVP/SUPER STAR from compact results
    compact = suite.get("compactUserMusicResults") or {}
    if not compact:
        missing.append("compactUserMusicResults")
    mvp_total = sum(compact.get("mvpCount", []) or [])
    superstar_total = sum(compact.get("superStarCount", []) or [])

    # Challenge live best
    challenge = suite.get("userChallengeLiveSoloResults") or []
    if challenge == []:
        missing.append("userChallengeLiveSoloResults")
    challenge_best = max((x.get("highScore", 0) for x in challenge), default=0)

    # Character rank
    chars = suite.get("userCharacters") or []
    if chars == []:
        missing.append("userCharacters")
    top_chars = sorted(
        [
            (x.get("characterId", 0), x.get("characterRank", 0))
            for x in chars
            if isinstance(x, dict)
        ],
        key=lambda t: (-t[1], t[0]),
    )[:12]

    # Clear/FC/AP counts by difficulty from userMusics
    user_musics = suite.get("userMusics") or []
    if user_musics == []:
        missing.append("userMusics")

    clear = defaultdict(int)
    fc = defaultdict(int)
    ap = defaultdict(int)
    for music in user_musics:
        if not isinstance(music, dict):
            continue
        statuses = music.get("userMusicDifficultyStatuses") or []
        for st in statuses:
            diff = st.get("musicDifficulty")
            if diff not in DIFF_ORDER:
                continue
            results = st.get("userMusicResults") or []
            if not results:
                continue
            # Any result means cleared at least once in practice for this dataset.
            clear[diff] += 1
            if any(r.get("fullComboFlg") for r in results if isinstance(r, dict)):
                fc[diff] += 1
            if any(r.get("fullPerfectFlg") for r in results if isinstance(r, dict)):
                ap[diff] += 1

    # Fallback: compactUserMusicResults (some suite payloads only have compact music info)
    if sum(clear.values()) == 0:
        compact_results = suite.get("compactUserMusicResults") or {}
        enum = compact_results.get("__ENUM__", {})
        diff_enum = enum.get("musicDifficultyType", [])
        play_result_enum = enum.get("playResult", [])
        music_ids = compact_results.get("musicId", []) or []
        diff_codes = compact_results.get("musicDifficultyType", []) or []
        play_results = compact_results.get("playResult", []) or []
        fc_flags = compact_results.get("fullComboFlg", []) or []
        ap_flags = compact_results.get("fullPerfectFlg", []) or []

        clear_set = {k: set() for k in DIFF_ORDER}
        fc_set = {k: set() for k in DIFF_ORDER}
        ap_set = {k: set() for k in DIFF_ORDER}

        n = min(
            len(music_ids),
            len(diff_codes),
            len(play_results),
            len(fc_flags),
            len(ap_flags),
        )
        for i in range(n):
            diff_code = diff_codes[i]
            if not isinstance(diff_code, int) or diff_code >= len(diff_enum):
                continue
            diff = diff_enum[diff_code]
            if diff not in clear_set:
                continue

            music_id = music_ids[i]
            pr_code = play_results[i]
            play_result = None
            if isinstance(pr_code, int) and pr_code < len(play_result_enum):
                play_result = play_result_enum[pr_code]

            if play_result in ("clear", "full_combo", "full_perfect"):
                clear_set[diff].add(music_id)
            if fc_flags[i]:
                fc_set[diff].add(music_id)
            if ap_flags[i]:
                ap_set[diff].add(music_id)

        for diff in DIFF_ORDER:
            clear[diff] = len(clear_set[diff])
            fc[diff] = len(fc_set[diff])
            ap[diff] = len(ap_set[diff])

    return (
        {
            "name": name,
            "rank": rank,
            "twitter": twitter,
            "word": word,
            "mvp_total": mvp_total,
            "superstar_total": superstar_total,
            "challenge_best": challenge_best,
            "top_chars": top_chars,
            "clear": clear,
            "fc": fc,
            "ap": ap,
        },
        sorted(set(missing)),
    )


def render_suite_card(json_path: str, output_path: str) -> List[str]:
    with open(json_path, "r", encoding="utf-8") as f:
        suite = json.load(f)
    stats, missing = _extract_stats(suite)

    w, h = 1500, 900
    img = Image.new("RGB", (w, h), (245, 248, 252))
    d = ImageDraw.Draw(img)

    # Background accents
    d.rounded_rectangle((24, 24, w - 24, h - 24), radius=28, fill=(255, 255, 255), outline=(220, 230, 240), width=2)
    d.ellipse((1000, -150, 1550, 400), fill=(231, 248, 255))
    d.ellipse((-150, 650, 350, 1100), fill=(239, 249, 255))

    font_title = _load_font(54, bold=True)
    font_h2 = _load_font(34, bold=True)
    font_text = _load_font(26)
    font_small = _load_font(21)
    font_num = _load_font(36, bold=True)

    # Header
    d.text((60, 50), str(stats["name"]), font=font_title, fill=(20, 30, 45))
    d.text((60, 125), f"Rank {stats['rank']}", font=font_h2, fill=(47, 93, 135))
    if stats["twitter"]:
        d.text((60, 175), f"@{stats['twitter']}", font=font_text, fill=(70, 80, 95))
    if stats["word"]:
        d.text((60, 215), stats["word"][:48], font=font_small, fill=(90, 100, 120))

    # Right summary chips
    d.rounded_rectangle((860, 60, 1410, 120), radius=28, fill=(42, 197, 191))
    d.text((1065, 75), "MULTI LIVE", font=_load_font(34, bold=True), fill=(255, 255, 255))
    d.rounded_rectangle((880, 145, 1130, 208), radius=28, fill=(54, 201, 196))
    d.text((900, 162), f"MVP  {stats['mvp_total']}", font=font_h2, fill=(255, 255, 255))
    d.rounded_rectangle((1150, 145, 1410, 208), radius=28, fill=(54, 201, 196))
    d.text((1173, 162), f"SUPER  {stats['superstar_total']}", font=font_h2, fill=(255, 255, 255))

    d.rounded_rectangle((860, 240, 1410, 300), radius=28, fill=(42, 197, 191))
    d.text((1030, 255), "CHALLENGE", font=_load_font(34, bold=True), fill=(255, 255, 255))
    d.rounded_rectangle((880, 322, 1410, 390), radius=30, fill=(232, 246, 255))
    d.text((900, 340), "SOLO BEST", font=font_h2, fill=(66, 126, 170))
    d.text((1180, 336), f"{stats['challenge_best']}", font=font_num, fill=(22, 34, 52))

    # Difficulty rows
    section_y = 310
    for idx, (label, key) in enumerate([("CLEAR", "clear"), ("FULL COMBO", "fc"), ("ALL PERFECT", "ap")]):
        y0 = section_y + idx * 155
        d.rounded_rectangle((60, y0, 790, y0 + 48), radius=24, fill=(42, 197, 191))
        d.text((355, y0 + 8), label, font=font_h2, fill=(255, 255, 255))
        x = 70
        for diff in DIFF_ORDER:
            color = DIFF_COLOR[diff]
            d.rounded_rectangle((x, y0 + 65, x + 110, y0 + 102), radius=12, fill=color)
            d.text((x + 12, y0 + 72), diff.upper(), font=_load_font(18, bold=True), fill=(255, 255, 255))
            val = stats[key].get(diff, 0)
            d.text((x + 34, y0 + 108), str(val), font=font_num, fill=(20, 30, 45))
            x += 118

    # Character rank area
    d.rounded_rectangle((860, 430, 1410, 490), radius=28, fill=(42, 197, 191))
    d.text((985, 445), "CHARACTER RANK", font=_load_font(34, bold=True), fill=(255, 255, 255))

    gx, gy = 875, 510
    cell_w, cell_h = 255, 78
    for i, (cid, crank) in enumerate(stats["top_chars"]):
        row = i // 2
        col = i % 2
        x0 = gx + col * (cell_w + 20)
        y0 = gy + row * (cell_h + 14)
        d.rounded_rectangle((x0, y0, x0 + cell_w, y0 + cell_h), radius=34, fill=(104, 202, 242))
        d.ellipse((x0 + 10, y0 + 10, x0 + 58, y0 + 58), fill=(219, 244, 255))
        d.text((x0 + 20, y0 + 20), str(cid), font=_load_font(18, bold=True), fill=(43, 121, 163))
        d.text((x0 + 86, y0 + 18), f"Rank {crank}", font=_load_font(30, bold=True), fill=(12, 27, 43))

    # Missing data notice
    if missing:
        d.rounded_rectangle((60, 805, 790, 860), radius=12, fill=(255, 243, 227), outline=(236, 173, 89), width=2)
        d.text((74, 820), "Missing fields: " + ", ".join(missing[:6]), font=_load_font(20), fill=(156, 93, 20))
    else:
        d.rounded_rectangle((60, 805, 420, 860), radius=12, fill=(230, 250, 239), outline=(86, 188, 121), width=2)
        d.text((74, 820), "Data completeness: OK", font=_load_font(22, bold=True), fill=(38, 125, 68))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    return missing


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render suite card image from suite json")
    parser.add_argument("infile", help="suite json file")
    parser.add_argument("outfile", help="output png path")
    args = parser.parse_args()

    missing = render_suite_card(args.infile, args.outfile)
    if missing:
        print("Rendered with missing fields:", ", ".join(missing))
    else:
        print("Rendered with complete core fields")
