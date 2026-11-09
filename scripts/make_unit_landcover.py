"""Land-cover share of each unit, decoded from docs/data/rasters/landcover.png (ESA WorldCover 2021, 900-px grid).

The PNG stores each WorldCover class as one exact RGB colour (scripts/make_terrain_landcover.py), so each pixel
maps back to its class by exact colour match. Shares are computed over the valid pixels inside each unit.
Output: docs/data/unit_landcover.json. Checks: the pixel-weighted catchment shares (Z1 to Z4) must match the
catchment legend in docs/data/rasters/rasters.json to within 0.2 percentage points.

    python scripts/make_unit_landcover.py
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"


def main() -> None:
    rj = json.loads((DATA / "rasters" / "rasters.json").read_text())
    b = rj["bounds"]
    lc = np.array(Image.open(DATA / "rasters" / "landcover.png").convert("RGBA"))
    H, W = lc.shape[:2]
    tr = from_bounds(b["west"], b["south"], b["east"], b["north"], W, H)
    classes = {tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)): (leg["label"], leg["code"] if "code" in leg else None)
               for leg in rj["landcover"]["legend"] for c in [leg["colour"]]}
    keys = np.array(list(classes.keys()))
    labels = [classes[tuple(k)][0] for k in keys]
    flat = lc[..., :3].reshape(-1, 3).astype(int)
    dist = ((flat[:, None, :] - keys[None, :, :]) ** 2).sum(-1)
    idx = dist.argmin(1)
    exact = dist.min(1) == 0
    valid = (lc[..., 3].reshape(-1) > 0) & exact
    g = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    out = {"script": "scripts/make_unit_landcover.py", "source": rj["landcover"]["source"], "classes": labels, "units": {}}
    pixels = {z: 0 for z in ("Z1", "Z2", "Z3", "Z4")}
    counts = {z: np.zeros(len(labels)) for z in pixels}
    for f in g["features"]:
        z = f["properties"]["zone_id"]
        if z not in pixels:
            continue
        m = rasterize([(shape(f["geometry"]), 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool).reshape(-1)
        sel = m & valid
        pixels[z] = int(sel.sum())
        counts[z] = np.bincount(idx[sel], minlength=len(labels)).astype(float)
        share = 100 * counts[z] / max(pixels[z], 1)
        out["units"][z] = {"valid_pixels": pixels[z], "share_pct": {lab: round(float(s), 2) for lab, s in zip(labels, share)}}
    total = sum(counts.values())
    cat_pixels = sum(pixels.values())
    check = {}
    for leg in rj["landcover"]["legend"]:
        lab = leg["label"]
        i = labels.index(lab)
        got = 100 * total[i] / cat_pixels
        check[lab] = {"from_pixels": round(float(got), 2), "from_rasters_json": leg["share_pct"], "diff_pp": round(float(got - leg["share_pct"]), 2)}
    worst = max(abs(v["diff_pp"]) for v in check.values())
    out["catchment_check"] = {"max_abs_diff_pp": round(float(worst), 2), "classes": check}
    if worst > 0.2:
        raise SystemExit(f"land-cover shares disagree with rasters.json by {worst:.2f} points; not written")
    (DATA / "unit_landcover.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", DATA / "unit_landcover.json", "| max catchment difference", round(float(worst), 2), "points")


if __name__ == "__main__":
    main()
