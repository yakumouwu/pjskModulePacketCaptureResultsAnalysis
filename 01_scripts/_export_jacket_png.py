from pathlib import Path
import re
import json

SRC_DIR = Path(r"d:\\reverse\sssekai\bundles_cn_jacket\music\jacket")
OUT_DIR = Path(r"d:\\reverse\sssekai\jacket_png")
REPORT = Path(r"d:\\reverse\sssekai\jacket_png_export_report.json")

OUT_DIR.mkdir(parents=True, exist_ok=True)

import UnityPy
from UnityPy.enums import ClassIDType

# PJSK >= 3.6.0 uses Unity 2022.3.21f1
UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.21f1"

safe = re.compile(r"[^0-9A-Za-z._-]+")


def norm(name: str) -> str:
    name = (name or "").strip()
    name = safe.sub("_", name)
    name = name.strip("._")
    return name or "noname"


bundles = sorted([p for p in SRC_DIR.rglob("*") if p.is_file()])

stats = {
    "source_dir": str(SRC_DIR),
    "output_dir": str(OUT_DIR),
    "fallback_unity_version": UnityPy.config.FALLBACK_UNITY_VERSION,
    "bundle_files": len(bundles),
    "exported_png": 0,
    "bundle_with_texture": 0,
    "errors_count": 0,
    "errors_sample": [],
}

for b in bundles:
    try:
        env = UnityPy.load(str(b))
    except Exception as e:
        stats["errors_count"] += 1
        if len(stats["errors_sample"]) < 20:
            stats["errors_sample"].append(
                {"bundle": str(b), "error": f"load_failed: {e}"}
            )
        continue

    exported_this_bundle = 0
    for obj in env.objects:
        if obj.type != ClassIDType.Texture2D:
            continue
        try:
            data = obj.read()
            image = data.image
            if image is None:
                continue

            base = f"{norm(b.name)}__{norm(getattr(data, 'name', 'texture'))}"
            out_path = OUT_DIR / f"{base}.png"
            suffix = 1
            while out_path.exists():
                out_path = OUT_DIR / f"{base}_{suffix}.png"
                suffix += 1

            image.save(out_path)
            exported_this_bundle += 1
            stats["exported_png"] += 1
        except Exception as e:
            stats["errors_count"] += 1
            if len(stats["errors_sample"]) < 20:
                stats["errors_sample"].append(
                    {"bundle": str(b), "error": f"texture_failed: {e}"}
                )

    if exported_this_bundle > 0:
        stats["bundle_with_texture"] += 1

REPORT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(stats, ensure_ascii=False))
