"""Raster context layers for the Ogun map: terrain (hillshade with elevation tint) and land cover (ESA WorldCover 2021).

Sources, read through Microsoft Planetary Computer (anonymous signed access):
  - Copernicus DEM GLO-30 (cop-dem-glo-30), 30 m.
  - ESA WorldCover 2021 v200 (esa-worldcover), 10 m; accuracy 76.5% for Africa (Zanaga et al., 2022).

Outputs (docs/data/rasters/):
  terrain.png, landcover.png  - RGBA overlays, transparent outside the catchment (units Z1 to Z4)
  rasters.json                - bounds, grid, legend classes, sources and processing notes

    python scripts/make_terrain_landcover.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = DATA / "rasters"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/"
WIDTH = 900
PAD = 0.05  # degrees around the catchment
WORLDCOVER = [(10, "Tree cover", "#006400"), (20, "Shrubland", "#ffbb22"), (30, "Grassland", "#ffff4c"),
              (40, "Cropland", "#f096ff"), (50, "Built-up", "#fa0000"), (60, "Bare or sparse vegetation", "#b4b4b4"),
              (70, "Snow and ice", "#f0f0f0"), (80, "Permanent water", "#0064c8"),
              (90, "Herbaceous wetland", "#0096a0"), (95, "Mangroves", "#00cf75"), (100, "Moss and lichen", "#fae6a0")]
_tok: dict[str, tuple[str, float]] = {}


def token(collection: str) -> str:
    tok, exp = _tok.get(collection, ("", 0.0))
    if time.time() > exp:
        tok = json.load(urllib.request.urlopen(SAS + collection, timeout=60))["token"]
        _tok[collection] = (tok, time.time() + 40 * 60)
    return _tok[collection][0]


def search(collection: str, bbox: list[float]) -> list[dict]:
    body = json.dumps({"collections": [collection], "bbox": bbox, "limit": 100}).encode()
    req = urllib.request.Request(f"{STAC}/search", data=body, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))["features"]


def catchment() -> tuple[object, list[float]]:
    g = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    geoms = [shape(f["geometry"]) for f in g["features"] if f["properties"]["zone_id"] in ("Z1", "Z2", "Z3", "Z4")]
    cat = unary_union(geoms)
    return cat, list(cat.bounds)


def warp_into(href: str, dst: np.ndarray, transform, nodata_src=None, resampling=Resampling.nearest):
    with rasterio.Env(GDAL_HTTP_MAX_RETRY=4, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(href) as src:
            reproject(source=rasterio.band(src, 1), destination=dst, dst_transform=transform,
                      dst_crs="EPSG:4326", resampling=resampling, src_nodata=nodata_src,
                      dst_nodata=0 if dst.dtype != np.float32 else np.nan)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cat, cb = catchment()
    minx, miny, maxx, maxy = cb[0] - PAD, cb[1] - PAD, cb[2] + PAD, cb[3] + PAD
    height = int(round(WIDTH * (maxy - miny) / (maxx - minx)))
    transform = from_bounds(minx, miny, maxx, maxy, WIDTH, height)
    mask = rasterize([(cat, 1)], out_shape=(height, WIDTH), transform=transform, fill=0, dtype="uint8").astype(bool)
    bbox = [minx, miny, maxx, maxy]

    # Terrain
    dem = np.full((height, WIDTH), np.nan, "float32")
    for it in search("cop-dem-glo-30", bbox):
        href = it["assets"]["data"]["href"] + "?" + token("cop-dem-glo-30")
        tile = np.full((height, WIDTH), np.nan, "float32")
        warp_into(href, tile, transform, resampling=Resampling.bilinear)
        dem = np.where(np.isnan(dem), tile, dem)
    dem = np.where(mask, dem, np.nan)
    lat_mid = (miny + maxy) / 2
    dy = (maxy - miny) / height * 111_320.0
    dx = (maxx - minx) / WIDTH * 111_320.0 * np.cos(np.radians(lat_mid))
    gy, gx = np.gradient(np.nan_to_num(dem, nan=0.0), dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    shade = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    lo, hi = np.nanpercentile(dem, 2), np.nanpercentile(dem, 98)
    t = np.clip((dem - lo) / max(hi - lo, 1e-6), 0, 1)
    low, high = np.array([0xF3, 0xEF, 0xE2]), np.array([0x6B, 0x4F, 0x2A])
    tint = low[None, None, :] + (high - low)[None, None, :] * t[..., None]
    rgb = np.clip(np.nan_to_num(tint * (0.45 + 0.55 * shade[..., None])), 0, 255).astype("uint8")
    alpha = np.where(mask & np.isfinite(dem), 235, 0).astype("uint8")
    Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(OUT / "terrain.png", optimize=True)

    # Land cover
    lc = np.zeros((height, WIDTH), "uint8")
    for it in search("esa-worldcover", bbox):
        href = it["assets"]["map"]["href"] + "?" + token("esa-worldcover")
        tile = np.zeros((height, WIDTH), "uint8")
        warp_into(href, tile, transform, resampling=Resampling.nearest)
        lc = np.where(lc == 0, tile, lc)
    lut = np.zeros((256, 4), "uint8")
    for code, _, hexc in WORLDCOVER:
        lut[code] = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)] + [215]
    rgba = lut[lc]
    rgba[~mask] = 0
    rgba[lc == 0] = 0
    Image.fromarray(rgba, "RGBA").save(OUT / "landcover.png", optimize=True)

    present = {int(c): int(((lc == c) & mask).sum()) for c, _, _ in WORLDCOVER}
    total = int(mask.sum())
    legend = [{"code": c, "label": lab, "colour": col, "share_pct": round(100 * present[c] / total, 1)}
              for c, lab, col in WORLDCOVER if present[c] > 0]
    meta = {
        "script": "scripts/make_terrain_landcover.py",
        "bounds": {"west": minx, "south": miny, "east": maxx, "north": maxy},
        "grid": {"width_px": WIDTH, "height_px": height, "crs": "EPSG:4326"},
        "clip": "union of units Z1 to Z4 (catchment)",
        "terrain": {"source": "Copernicus DEM GLO-30 via Microsoft Planetary Computer (cop-dem-glo-30)",
                    "resolution_m": 30, "display": "hillshade (azimuth 315°, altitude 45°) with elevation tint",
                    "elevation_min_m": round(float(np.nanmin(dem)), 1), "elevation_max_m": round(float(np.nanmax(dem)), 1),
                    "note": "The Copernicus DEM gives 0 m over water; the minimum may be a lagoon or river cell, not land."},
        "landcover": {"source": "ESA WorldCover 2021 v200 via Microsoft Planetary Computer (esa-worldcover)",
                      "resolution_m": 10, "accuracy_africa_pct": 76.5,
                      "citation": "Zanaga et al. (2022), doi:10.5281/zenodo.7254221",
                      "legend": legend},
    }
    (OUT / "rasters.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT, "| terrain elevation", meta["terrain"]["elevation_min_m"], "to", meta["terrain"]["elevation_max_m"], "m")


if __name__ == "__main__":
    main()
