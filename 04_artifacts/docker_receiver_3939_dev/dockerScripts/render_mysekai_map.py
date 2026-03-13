import argparse
import json
import math
import os
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

SITE_CONFIG = {
    5: {"name": "Map 1", "bg": "grassland.png", "transform": "zx_neg", "scale_add": (8.5, 8.5), "offset_add": (30.0, 0.0)},
    6: {"name": "Map 2", "bg": "beach.png", "transform": "x_negz", "scale_add": (4.6, 4.2), "offset_add": (-70.0, 85.0)},
    7: {"name": "Map 3", "bg": "flowergarden.png", "transform": "zx_neg", "scale_add": (5.0, 3.0), "offset_add": (55.0, -70.0)},
    8: {"name": "Map 4", "bg": "memorialplace.png", "transform": "x_negz", "scale_add": (3.0, 0.0), "offset_add": (-185.0, 35.0)},
}

ASSET_ICON_TO_FILE = {
    "item_wood_1": "Wood_of_Feelings.png",
    "item_wood_2": "Heavy_Wood.png",
    "item_wood_3": "Light_Wood.png",
    "item_wood_4": "Sticky_Sap.png",
    "item_wood_5": "Evening_Paulownia.png",
    "item_mineral_1": "Pebble_of_Feelings.png",
    "item_mineral_2": "Copper.png",
    "item_mineral_3": "Iron.png",
    "item_mineral_4": "Clay.png",
    "item_mineral_5": "Clear_Glass.png",
    "item_mineral_6": "Sparkly_Quartz.png",
    "item_mineral_7": "Diamond.png",
    "item_mineral_8": "Moonlight_Stone.png",
    "item_mineral_9": "Lightning_Stone.png",
    "item_mineral_10": "Rainbow_Glass.png",
    "item_junk_1": "Screw.png",
    "item_junk_2": "Nail.png",
    "item_junk_3": "Plastic.png",
    "item_junk_4": "Motor.png",
    "item_junk_5": "Battery.png",
    "item_junk_6": "Lightbulb.png",
    "item_junk_7": "Circuit_Board.png",
    "item_junk_8": "Blue_Sky_Sea_Glass.png",
    "item_junk_9": "Fragment_of_Shooting_Star.png",
    "item_junk_10": "Snowflake.png",
    "item_junk_11": "Best_Axe_Blade.png",
    "item_junk_12": "Best_Pickaxe_Tip.png",
    "item_junk_13": "Fluffy_Cloud.png",
    "item_junk_14": "SEKAI_Bits.png",
    "item_plant_1": "Four-Leaf_Clover.png",
    "item_plant_2": "Smooth_Linen.png",
    "item_plant_3": "Fluffy_Cotton.png",
    "item_plant_4": "Petal.png",
    "item_tone_8": "Pure_Tone.png",
    "item_blank_blueprint": "Blank_Blueprint.png",
    "item_surplus_blueprint": "Extra_Blueprint.png",
    "item_surplus_music_record": "Extra_Record.png",
    "item_blueprint_fragment": "Blueprint_Scrap.png",
}

FALLBACK_ICON_MAP = {
    ("mysekai_material", 12): "Diamond.png",
    ("mysekai_item", 7): "Blueprint_Scrap.png",
    ("mysekai_music_record", 79): "Extra_Record.png",
}


def _env_float(name, default):
    v = os.environ.get(name)
    if v is None or v == "":
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)


def _get_font(size):
    font_paths = [
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyh.ttc"),
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for p in font_paths:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _transform(site_id, x, z):
    cfg = SITE_CONFIG.get(site_id, {})
    if cfg.get("transform") == "x_negz":
        return x, -z
    return -z, -x


def _find_map_json():
    env_path = os.environ.get("MYSEKAI_RESOURCE_MAP_JSON", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path

    here = os.path.dirname(__file__)
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..", "..", "01_scripts", "mysekai_resource_map.json")),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def _load_resource_icon_map():
    mapping = dict(FALLBACK_ICON_MAP)
    map_json = _find_map_json()
    if not map_json:
        return mapping

    try:
        with open(map_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return mapping

    for k, meta in cfg.get("material_meta", {}).items():
        try:
            rid = int(k)
        except Exception:
            continue
        icon_key = str(meta.get("icon", ""))
        icon_file = ASSET_ICON_TO_FILE.get(icon_key)
        if icon_file:
            mapping[("mysekai_material", rid)] = icon_file

    for k, meta in cfg.get("item_meta", {}).items():
        try:
            rid = int(k)
        except Exception:
            continue
        icon_key = str(meta.get("icon", ""))
        icon_file = ASSET_ICON_TO_FILE.get(icon_key)
        if icon_file:
            mapping[("mysekai_item", rid)] = icon_file

    for k, meta in cfg.get("music_record_meta", {}).items():
        try:
            rid = int(k)
        except Exception:
            continue
        icon_key = str(meta.get("icon", ""))
        icon_file = ASSET_ICON_TO_FILE.get(icon_key)
        if icon_file:
            mapping[("mysekai_music_record", rid)] = icon_file

    return mapping


def _load_icons(icon_dir, resource_icon_map):
    cache = {}
    for key, fname in resource_icon_map.items():
        path = os.path.join(icon_dir, fname)
        if os.path.isfile(path):
            cache[key] = Image.open(path).convert("RGBA")
    return cache


def _extract_points(mysekai_json):
    points_by_site = {}
    maps = mysekai_json.get("updatedResources", {}).get("userMysekaiHarvestMaps", [])
    for hm in maps:
        site_id = hm.get("mysekaiSiteId")
        if site_id not in SITE_CONFIG:
            continue
        coords = points_by_site.setdefault(site_id, {})
        for drop in hm.get("userMysekaiSiteHarvestResourceDrops", []):
            resource_type = str(drop.get("resourceType", ""))
            if resource_type not in ("mysekai_material", "mysekai_item", "mysekai_music_record"):
                continue
            x = drop.get("positionX")
            z = drop.get("positionZ")
            if x is None or z is None:
                continue
            rx, rz = _transform(site_id, float(x), float(z))
            k = (rx, rz)
            lst = coords.setdefault(k, [])
            lst.append({
                "resourceType": resource_type,
                "resourceId": int(drop.get("resourceId", -1)),
                "qty": int(drop.get("quantity", 1)),
            })
    return points_by_site


def _render_site(points_by_site, site_id, assets_dir, target_size):
    coords = points_by_site.get(site_id, {})
    if not coords:
        return None, "no_points_for_site"

    icon_dir = os.path.join(assets_dir, "icon")
    map_dir = os.path.join(assets_dir, "map")
    cfg = SITE_CONFIG.get(site_id)
    if not cfg:
        return None, "invalid_site_id"
    bg_path = os.path.join(map_dir, cfg["bg"])
    if not os.path.isfile(bg_path):
        return None, "background_not_found"

    resource_icon_map = _load_resource_icon_map()
    icons = _load_icons(icon_dir, resource_icon_map)
    font_count = _get_font(12)

    img = Image.open(bg_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    bg_w, bg_h = img.size

    all_x = [p[0] for p in coords]
    all_z = [p[1] for p in coords]
    min_x, max_x = min(all_x) - 1.0, max(all_x) + 1.0
    min_z, max_z = min(all_z) - 1.0, max(all_z) + 1.0
    range_x = max(1.0, max_x - min_x + 1.0)
    range_z = max(1.0, max_z - min_z + 1.0)

    usable_w = bg_w * 0.70
    usable_h = bg_h * 0.70
    base_scale = min(usable_w / range_x, usable_h / range_z)
    scale_x = base_scale + cfg["scale_add"][0]
    scale_z = base_scale + cfg["scale_add"][1]
    scale_x += _env_float(f"SITE{site_id}_SCALE_X_DELTA", 0.0)
    scale_z += _env_float(f"SITE{site_id}_SCALE_Z_DELTA", 0.0)

    offset_x = (bg_w - range_x * scale_x) / 2.0 + cfg["offset_add"][0]
    offset_z = (bg_h - range_z * scale_z) / 2.0 + cfg["offset_add"][1]
    offset_x += _env_float(f"SITE{site_id}_OFFSET_X_DELTA", 0.0)
    offset_z += _env_float(f"SITE{site_id}_OFFSET_Z_DELTA", 0.0)

    def coord_to_px(cx, cz):
        px = offset_x + (cx - min_x) * scale_x + scale_x / 2.0
        pz = offset_z + (cz - min_z) * scale_z + scale_z / 2.0
        return int(px), int(pz)

    item_pixels = []
    for (cx, cz), drops in coords.items():
        px, py = coord_to_px(cx, cz)
        item_pixels.append((px, py))

        stat = {}
        for d in drops:
            key = (d["resourceType"], d["resourceId"])
            stat[key] = stat.get(key, 0) + int(d["qty"])
        entries = sorted(stat.items(), key=lambda t: t[1], reverse=True)

        if len(entries) == 1:
            main_key, main_qty = entries[0]
            icon = icons.get(main_key)
            if icon is not None:
                icon_size = 24
                icon_img = icon.resize((icon_size, icon_size), Image.LANCZOS)
                img.paste(icon_img, (px - icon_size // 2, py - icon_size // 2), icon_img)
            else:
                draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(120, 120, 120, 90), outline=(220, 220, 220, 180))
            text = str(main_qty)
            tx = px + 10
            ty = py + 6
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((tx + dx, ty + dy), text, fill=(0, 0, 0), font=font_count)
            draw.text((tx, ty), text, fill=(255, 255, 255), font=font_count)
        else:
            spread = 15
            for i, (key, qty) in enumerate(entries):
                angle = (2 * math.pi * i / len(entries)) - math.pi / 2
                ix = int(px + math.cos(angle) * spread)
                iy = int(py + math.sin(angle) * spread)
                icon = icons.get(key)
                if icon is not None:
                    icon_size = 24
                    icon_img = icon.resize((icon_size, icon_size), Image.LANCZOS)
                    img.paste(icon_img, (ix - icon_size // 2, iy - icon_size // 2), icon_img)
                else:
                    draw.ellipse([ix - 6, iy - 6, ix + 6, iy + 6], fill=(120, 120, 120, 90), outline=(220, 220, 220, 180))
                text = str(qty)
                tx = ix + 7
                ty = iy + 4
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    draw.text((tx + dx, ty + dy), text, fill=(0, 0, 0), font=font_count)
                draw.text((tx, ty), text, fill=(255, 255, 255), font=font_count)

    # Keep full-map output so alerts always show complete site context.
    panel = img.resize((int(target_size), int(target_size)), Image.LANCZOS)
    return panel, "ok"


def render_single_site_image(json_path, out_path, assets_dir, site_id, target_size=1024):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    points_by_site = _extract_points(data)
    panel, status = _render_site(points_by_site, site_id, assets_dir, target_size)
    if panel is None:
        return False, status
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    panel.save(out_path)
    return True, "ok"


def render_mysekai_map_image(json_path, out_path, assets_dir):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    points_by_site = _extract_points(data)
    if not points_by_site:
        return False, "no_points"

    target = 768
    rendered = OrderedDict()
    for sid in (5, 7, 6, 8):
        panel, status = _render_site(points_by_site, sid, assets_dir, target)
        if panel is not None:
            rendered[sid] = panel

    if not rendered:
        return False, "no_site_image"

    grid = Image.new("RGBA", (target * 2, target * 2 + 48), (18, 22, 30, 255))
    title = ImageDraw.Draw(grid)
    title.text((16, 10), "MySekai Resource Map", fill=(240, 240, 245), font=_get_font(20))
    panel_pos = {5: (0, 48), 7: (target, 48), 6: (0, target + 48), 8: (target, target + 48)}
    for sid, pos in panel_pos.items():
        if sid in rendered:
            grid.paste(rendered[sid], pos, rendered[sid])

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    grid.save(out_path)
    return True, "ok"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("out_path")
    ap.add_argument("assets_dir")
    ap.add_argument("--site-id", type=int, default=None)
    ap.add_argument("--target-size", type=int, default=1024)
    args = ap.parse_args()

    if args.site_id is None:
        ok, msg = render_mysekai_map_image(args.json_path, args.out_path, args.assets_dir)
    else:
        ok, msg = render_single_site_image(
            args.json_path,
            args.out_path,
            args.assets_dir,
            args.site_id,
            args.target_size,
        )
    if not ok:
        raise SystemExit(msg)
