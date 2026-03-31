import argparse
import json
import math
import os
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

SUPPORTED_RESOURCE_TYPES = {
    "mysekai_material",
    "mysekai_item",
    "mysekai_music_record",
    "material",
    "mysekai_fixture",
}

SKIP_UNMAPPED_RESOURCE_TYPES = {
    "mysekai_music_record",
    "material",
    "mysekai_fixture",
}

DYNAMIC_ICON_PATTERNS = {
    "material": ["material_{id}.png"],
    "mysekai_fixture": [
        "mysekai_fixture_{id}.png",
        "fixture_{id}.png",
    ],
}

TYPE_FALLBACK_ICON_FILES = {
    "mysekai_music_record": "Extra_Record.png",
}

_RESOURCE_ICON_MAP_CACHE = None
_RESOURCE_ASSET_KEY_CACHE = None
_ICON_CACHE_BY_DIR = {}

SITE_CONFIG = {
    5: {
        "name": "Map 1",
        "bg": "grassland.png",
        "transform": "zx_neg",
        "world_bounds": (-30.0, 29.0, -23.0, 75.0),
        "scale_add": (25.5, 25.5),
        "offset_add": (0.0, -90.0),
    },
    6: {
        "name": "Map 2",
        "bg": "beach.png",
        "transform": "x_negz",
        "world_bounds": (-30.0, 29.0, -20.0, 68.0),
        "scale_add": (16.6, 16.2),
        "offset_add": (20.0, 120.0),
    },
    7: {
        "name": "Map 3",
        "bg": "flowergarden.png",
        "transform": "zx_neg",
        "world_bounds": (-30.0, 29.0, -28.0, 75.0),
        "scale_add": (19.0, 19.0),
        "offset_add": (-60.0, 20.0),
    },
    8: {
        "name": "Map 4",
        "bg": "memorialplace.png",
        "transform": "x_negz",
        "world_bounds": (-30.0, 29.0, -29.0, 70.0),
        "scale_add": (16.6, 16.2),
        "offset_add": (20.0, -120.0),
    },
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
}

# Same-coordinate icon priority for rendering.
# Earlier entries have higher priority.
DEFAULT_SAME_COORD_PRIORITY = [
    ("mysekai_material", 12),
]


def _env_float(name, default):
    v = os.environ.get(name)
    if v is None or v == "":
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)


def _env_int(name, default):
    v = os.environ.get(name)
    if v is None or v == "":
        return int(default)
    try:
        return int(v)
    except Exception:
        return int(default)


def _env_bool(name, default):
    v = os.environ.get(name)
    if v is None or v == "":
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _parse_same_coord_priority():
    """
    Parse env MYSEKAI_SAME_COORD_PRIORITY:
    Example: "mysekai_material:12,mysekai_item:7,mysekai_material:10"
    """
    text = os.environ.get("MYSEKAI_SAME_COORD_PRIORITY", "").strip()
    if not text:
        return list(DEFAULT_SAME_COORD_PRIORITY)

    parsed = []
    for part in text.split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        rtype, rid_text = item.split(":", 1)
        rtype = rtype.strip()
        rid_text = rid_text.strip()
        if not rtype:
            continue
        try:
            rid = int(rid_text)
        except Exception:
            continue
        parsed.append((rtype, rid))

    return parsed if parsed else list(DEFAULT_SAME_COORD_PRIORITY)


def _same_coord_sort_key(key, priority_map):
    # Unknown keys keep deterministic fallback ordering after prioritized keys.
    return (priority_map.get(key, 10**9), key[0], key[1])


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
        os.path.abspath(
            os.path.join(
                here, "..", "..", "..", "01_scripts", "mysekai_resource_map.json"
            )
        ),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def _load_resource_icon_map():
    global _RESOURCE_ICON_MAP_CACHE
    if _RESOURCE_ICON_MAP_CACHE is not None:
        return dict(_RESOURCE_ICON_MAP_CACHE)

    mapping = dict(FALLBACK_ICON_MAP)
    map_json = _find_map_json()
    if not map_json:
        _RESOURCE_ICON_MAP_CACHE = dict(mapping)
        return dict(_RESOURCE_ICON_MAP_CACHE)

    try:
        with open(map_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        _RESOURCE_ICON_MAP_CACHE = dict(mapping)
        return dict(_RESOURCE_ICON_MAP_CACHE)

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

    _RESOURCE_ICON_MAP_CACHE = dict(mapping)
    return dict(_RESOURCE_ICON_MAP_CACHE)


def _load_resource_asset_keys():
    global _RESOURCE_ASSET_KEY_CACHE
    if _RESOURCE_ASSET_KEY_CACHE is not None:
        return dict(_RESOURCE_ASSET_KEY_CACHE)

    asset_keys = {}
    map_json = _find_map_json()
    if not map_json:
        _RESOURCE_ASSET_KEY_CACHE = dict(asset_keys)
        return dict(_RESOURCE_ASSET_KEY_CACHE)

    try:
        with open(map_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        _RESOURCE_ASSET_KEY_CACHE = dict(asset_keys)
        return dict(_RESOURCE_ASSET_KEY_CACHE)

    for rtype, section in (
        ("mysekai_material", "material_meta"),
        ("mysekai_item", "item_meta"),
        ("mysekai_music_record", "music_record_meta"),
    ):
        for k, meta in cfg.get(section, {}).items():
            try:
                rid = int(k)
            except Exception:
                continue
            asset_key = str(meta.get("icon", "")).strip()
            if asset_key:
                asset_keys[(rtype, rid)] = asset_key

    _RESOURCE_ASSET_KEY_CACHE = dict(asset_keys)
    return dict(_RESOURCE_ASSET_KEY_CACHE)


def _load_icons(icon_dir, resource_icon_map):
    cache = _ICON_CACHE_BY_DIR.setdefault(icon_dir, {})
    for key, fname in resource_icon_map.items():
        if key in cache:
            continue
        path = os.path.join(icon_dir, fname)
        if os.path.isfile(path):
            cache[key] = Image.open(path).convert("RGBA")
    return cache


def _try_load_dynamic_icon(icon_dir, cache, key):
    if key in cache:
        return cache[key]

    rtype, rid = key
    candidates = DYNAMIC_ICON_PATTERNS.get(rtype)
    if not candidates:
        return None

    for pattern in candidates:
        fname = pattern.format(id=rid)
        path = os.path.join(icon_dir, fname)
        if os.path.isfile(path):
            cache[key] = Image.open(path).convert("RGBA")
            return cache[key]
    cache[key] = None
    return None


def _get_icon(icon_dir, cache, key):
    icon = cache.get(key)
    if key in cache:
        return icon

    asset_key = _load_resource_asset_keys().get(key)
    if asset_key:
        path = os.path.join(icon_dir, f"{asset_key}.png")
        if os.path.isfile(path):
            cache[key] = Image.open(path).convert("RGBA")
            return cache[key]

    fallback_file = TYPE_FALLBACK_ICON_FILES.get(key[0])
    if fallback_file:
        path = os.path.join(icon_dir, fallback_file)
        if os.path.isfile(path):
            cache[key] = Image.open(path).convert("RGBA")
            return cache[key]

    return _try_load_dynamic_icon(icon_dir, cache, key)


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
            if resource_type not in SUPPORTED_RESOURCE_TYPES:
                continue
            x = drop.get("positionX")
            z = drop.get("positionZ")
            if x is None or z is None:
                continue
            rx, rz = _transform(site_id, float(x), float(z))
            k = (rx, rz)
            lst = coords.setdefault(k, [])
            lst.append(
                {
                    "resourceType": resource_type,
                    "resourceId": int(drop.get("resourceId", -1)),
                    "qty": int(drop.get("quantity", 1)),
                }
            )
    return points_by_site


def _filter_same_coord_base_materials(stat):
    """
    Hide base materials at the same coordinate when upgraded variants exist.
    Rules (mysekai_material only):
    - if id=1 and any id in [2,5] coexist, hide id=1
    - if id=6 and any id in [7,12] coexist, hide id=6
    """
    return stat


def _filter_unmapped_special_entries(entries, icons, icon_dir):
    filtered = []
    for key, qty in entries:
        icon = _get_icon(icon_dir, icons, key)
        if icon is None and key[0] in SKIP_UNMAPPED_RESOURCE_TYPES:
            continue
        filtered.append((key, qty))
    return filtered


def _resize_to_target_width(img, target_width):
    w, h = img.size
    out_w = max(1, int(target_width))
    out_h = max(1, int(round(out_w * (h / float(w)))))
    return img.resize((out_w, out_h), Image.LANCZOS)


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
    icon_size = max(16, _env_int("MYSEKAI_ICON_SIZE", 36))
    font_size = max(10, _env_int("MYSEKAI_COUNT_FONT_SIZE", 18))
    side_gap = max(0, _env_int("MYSEKAI_SIDE_COLUMN_GAP", 2))
    column_vgap = max(0, _env_int("MYSEKAI_SIDE_COLUMN_VGAP", 2))
    font_count = _get_font(font_size)
    same_coord_priority = _parse_same_coord_priority()
    priority_map = {key: i for i, key in enumerate(same_coord_priority)}

    img = Image.open(bg_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    bg_w, bg_h = img.size

    min_x, max_x, min_z, max_z = cfg.get("world_bounds", (-30.0, 30.0, -30.0, 30.0))
    half_world_x_default = max(abs(float(min_x)), abs(float(max_x)))
    half_world_z_default = max(abs(float(min_z)), abs(float(max_z)))
    half_world_x = max(
        1.0, _env_float(f"SITE{site_id}_WORLD_HALF_X", half_world_x_default)
    )
    half_world_z = max(
        1.0, _env_float(f"SITE{site_id}_WORLD_HALF_Z", half_world_z_default)
    )
    world_span_x = (half_world_x * 2.0) + 1.0
    world_span_z = (half_world_z * 2.0) + 1.0
    usable_w = bg_w * 0.70
    usable_h = bg_h * 0.70
    base_scale = min(usable_w / world_span_x, usable_h / world_span_z)
    scale_x = base_scale + cfg["scale_add"][0]
    scale_z = base_scale + cfg["scale_add"][1]
    scale_x += _env_float(f"SITE{site_id}_SCALE_X_DELTA", 0.0)
    scale_z += _env_float(f"SITE{site_id}_SCALE_Z_DELTA", 0.0)
    offset_x = (bg_w / 2.0) + cfg["offset_add"][0]
    offset_z = (bg_h / 2.0) + cfg["offset_add"][1]
    offset_x += _env_float(f"SITE{site_id}_OFFSET_X_DELTA", 0.0)
    offset_z += _env_float(f"SITE{site_id}_OFFSET_Z_DELTA", 0.0)

    def coord_to_px(cx, cz):
        px = offset_x + (cx * scale_x)
        pz = offset_z + (cz * scale_z)
        return int(px), int(pz)

    def draw_one_icon(center_x, center_y, key, qty):
        icon = _get_icon(icon_dir, icons, key)
        if icon is not None:
            icon_img = icon.resize((icon_size, icon_size), Image.LANCZOS)
            img.paste(
                icon_img,
                (center_x - icon_size // 2, center_y - icon_size // 2),
                icon_img,
            )
        else:
            draw.ellipse(
                [center_x - 8, center_y - 8, center_x + 8, center_y + 8],
                fill=(120, 120, 120, 90),
                outline=(220, 220, 220, 180),
            )

        text = str(qty)
        tx = center_x + (icon_size // 2) - 2
        ty = center_y + max(2, icon_size // 6)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((tx + dx, ty + dy), text, fill=(0, 0, 0), font=font_count)
        draw.text((tx, ty), text, fill=(255, 255, 255), font=font_count)

    for (cx, cz), drops in coords.items():
        px, py = coord_to_px(cx, cz)

        stat = {}
        for d in drops:
            key = (d["resourceType"], d["resourceId"])
            stat[key] = stat.get(key, 0) + int(d["qty"])
        stat = _filter_same_coord_base_materials(stat)
        # Keep deterministic order with configurable priority first.
        entries = sorted(
            stat.items(), key=lambda t: _same_coord_sort_key(t[0], priority_map)
        )
        entries = _filter_unmapped_special_entries(entries, icons, icon_dir)

        if not entries:
            continue

        if len(entries) == 1:
            main_key, main_qty = entries[0]
            draw_one_icon(px, py, main_key, main_qty)
        else:
            # First priority icon stays centered.
            main_key, main_qty = entries[0]
            draw_one_icon(px, py, main_key, main_qty)

            # Remaining icons are stacked as one right-side vertical column.
            # Ratio rule from design:
            # - 1 icon on the right: 1/2 size
            # - 2 icons on the right: each 1/2 size
            # - 3 icons on the right: each 1/3 size
            rest = entries[1:]
            rest_count = len(rest)
            if rest_count <= 2:
                right_icon_size = max(10, int(round(icon_size / 2.0)))
            else:
                right_icon_size = max(8, int(round(icon_size / float(rest_count))))

            right_font_size = max(
                9, int(round(font_size * (right_icon_size / float(icon_size))))
            )
            right_font = _get_font(right_font_size)
            right_x = px + (icon_size // 2) + side_gap + (right_icon_size // 2)
            start_y = py - (icon_size // 2) + (right_icon_size // 2)
            step_y = right_icon_size + column_vgap

            for idx, (key, qty) in enumerate(rest):
                iy = start_y + (idx * step_y)
                icon = _get_icon(icon_dir, icons, key)
                if icon is not None:
                    icon_img = icon.resize((right_icon_size, right_icon_size), Image.LANCZOS)
                    img.paste(
                        icon_img,
                        (right_x - right_icon_size // 2, iy - right_icon_size // 2),
                        icon_img,
                    )
                else:
                    draw.ellipse(
                        [right_x - 6, iy - 6, right_x + 6, iy + 6],
                        fill=(120, 120, 120, 90),
                        outline=(220, 220, 220, 180),
                    )

                text = str(qty)
                tx = right_x + (right_icon_size // 2) - 2
                ty = iy + max(1, right_icon_size // 8)
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    draw.text((tx + dx, ty + dy), text, fill=(0, 0, 0), font=right_font)
                draw.text((tx, ty), text, fill=(255, 255, 255), font=right_font)

    # Keep source map aspect ratio instead of forcing square output.
    panel = _resize_to_target_width(img, target_size)
    return panel, "ok"


def render_single_site_image(
    json_path, out_path, assets_dir, site_id, target_size=1024
):
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

    panel_h = next(iter(rendered.values())).height
    grid = Image.new("RGBA", (target * 2, panel_h * 2 + 48), (18, 22, 30, 255))
    title = ImageDraw.Draw(grid)
    title.text(
        (16, 10), "MySekai Resource Map", fill=(240, 240, 245), font=_get_font(20)
    )
    panel_pos = {
        5: (0, 48),
        7: (target, 48),
        6: (0, panel_h + 48),
        8: (target, panel_h + 48),
    }
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
        ok, msg = render_mysekai_map_image(
            args.json_path, args.out_path, args.assets_dir
        )
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
