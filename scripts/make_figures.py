"""Draw the figures of the study page from the published data files.

Inputs (all in docs/data/):
  ogun_subbasins.geojson, ogun_monthly_timeseries.csv, cascade_diagnostics.json

Outputs: docs/assets/figures/fig1_study_area.png ... fig7_dynamic_world.png

    python scripts/make_figures.py

Anomalies use the same calendar-month climatology as src/02_compile_observatory.py, which is
imported so the two cannot drift apart.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "docs" / "assets" / "figures"
INK, INK2, RULE = "#111111", "#4a4a4a", "#d7d6d0"
DATE = "8 November 2026"
AUTHOR = "D. O. Oloyede"
import matplotlib.font_manager as _fm
_FONT_DIR = Path.home() / ".cache" / "ogun-fonts"  # Satoshi TTF from Fontshare, kept outside the repository
for _f in _FONT_DIR.glob("Satoshi-*.ttf"):
    _fm.fontManager.addfont(str(_f))
_FAMILY = "Satoshi" if any(f.name == "Satoshi" for f in _fm.fontManager.ttflist) else "DejaVu Sans"
plt.rcParams.update({"font.family": _FAMILY, "font.size": 10.5, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False})
C_RAIN, C_SOIL, C_SAR, C_DW, C_NDTI = "#2d6cb0", "#3c8d6e", "#c0501a", "#7a5aa6", "#8a6d1f"


def _compiler():
    spec = importlib.util.spec_from_file_location("compile_observatory", ROOT / "src" / "02_compile_observatory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _source(fig, text, size=6.5, color=None):
    import textwrap
    lines = textwrap.wrap(f"Source: {text}", width=105)
    fig.text(0.02, 0.012, "\n".join(lines), fontsize=size, color=color or INK2, va="bottom", linespacing=1.3)


def fig2_series(df):
    fig, axes = plt.subplots(5, 1, figsize=(6.0, 8.8), sharex=True, dpi=200, gridspec_kw={"hspace": 0.55})
    t = pd.to_datetime(df["year_month"], format="%Y-%m")
    spec = [("rain_mm", "Rain (mm/month)", C_RAIN), ("shallow_sm_m3m3", "Soil moisture (m³/m³)", C_SOIL),
            ("sar_flood_km2", "Radar index (km²)", C_SAR), ("dw_flood_km2", "Dynamic World (km²)", C_DW),
            ("estuary_ndti", "Lagoon NDTI", C_NDTI)]
    for ax, (col, label, colour) in zip(axes, spec):
        ax.plot(t, df[col], color=colour, lw=1.0)
        ax.set_ylabel(label, fontsize=10)
        ax.grid(axis="y", color=RULE, lw=0.4)
    axes[-1].set_xlabel("Month")
    _source(fig, "Catchment-wide monthly values, Google Earth Engine export v2.4.0; gaps are missing months")
    return fig


def fig3_association(diag):
    """Spearman rho, raw values and anomalies. Raw rows carry q from the correction across each pair's three lags;
    anomaly rows carry q from the correction across the five headline relationships (key_findings), as in the text."""
    fam = {f["relationship"]: f for f in diag["key_findings"]}
    lag_names = ["same month", "one month later", "two months later"]
    rows = []
    for i, lag in enumerate(("lag_0_month", "lag_1_month", "lag_2_month")):
        r = diag["rain_to_sar_inundation_lags_seasonal"][lag]
        rows.append((f"Rain → inundation, {lag_names[i]}", "raw", r["spearman_rho"], r["p_value_bh_fdr"]))
    rows.append(("Soil moisture → inundation, same month", "raw", diag["soil_moisture_to_sar_inundation_lags_seasonal"]["lag_0_month"]["spearman_rho"], diag["soil_moisture_to_sar_inundation_lags_seasonal"]["lag_0_month"]["p_value_bh_fdr"]))
    for label, key in (("Rain → inundation, same month", "Rain -> floodplain SAR inundation (same month, deseasonalized)"),
                       ("Rain → inundation, one month later", "Rain -> floodplain SAR inundation (1-month lag, deseasonalized)"),
                       ("Soil moisture → inundation, same month", "Soil moisture -> floodplain SAR inundation (same month, deseasonalized)")):
        rows.append((label, "anomaly", fam[key]["spearman_rho"], fam[key]["p_value"]))
    fig, ax = plt.subplots(figsize=(5.0, 4.8), dpi=200)
    y = np.arange(len(rows))[::-1]
    for yi, (lab, kind, rho, q) in zip(y, rows):
        colour = C_RAIN if q < 0.05 else "#9a9a9a"
        ax.plot([0, rho], [yi, yi], color=colour, lw=1.4)
        ax.plot(rho, yi, "o", color=colour, ms=5, mfc="white" if kind == "raw" else colour)
        ax.text(0.62, yi, f"q = {q:.3f}" if q >= 0.001 else "q < 0.001", va="center", fontsize=13, color=INK2)
    ax.axvline(0, color=INK2, lw=0.6)
    ax.set_yticks(y, [f"{lab}  ({kind})" for lab, kind, _, _ in rows], fontsize=13)
    ax.tick_params(axis="x", labelsize=10)
    ax.set_xlim(-0.6, 0.85)
    ax.set_xlabel("Spearman ρ (recommended estimator)", fontsize=13)
    ax.grid(axis="x", color=RULE, lw=0.4)
    fig.subplots_adjust(left=0.56, right=0.97, bottom=0.2, top=0.97)
    _source(fig, "cascade_diagnostics.json. Hollow: raw values; filled: anomalies. Blue: q < 0.05; grey: not significant")
    return fig


def _scatter(ax, x, y, xl, yl, colour, rho, q):
    ax.scatter(x, y, s=14, color=colour, alpha=0.8, lw=0)
    ax.axhline(0, color=RULE, lw=0.6)
    ax.axvline(0, color=RULE, lw=0.6)
    ax.set_xlabel(f"{xl}\nρ = {rho:+.2f}, q = {q:.2f}", fontsize=13, linespacing=1.6)
    ax.set_ylabel(yl, fontsize=13)
    ax.tick_params(labelsize=10)
    ax.grid(color=RULE, lw=0.4)


def fig4_scatter(comp, anom):
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 4.2), dpi=200)
    m = anom[["sar_flood_km2_anom", "estuary_ndti_anom"]].dropna()
    r = [f for f in comp["key_findings"] if "NDTI" in f["relationship"]][0]
    _scatter(axes[0], m["sar_flood_km2_anom"], m["estuary_ndti_anom"], "Radar index (km²)", "Lagoon NDTI",
             C_NDTI, r["spearman_rho"], r["p_value"])
    axes[0].set_title("Lagoon turbidity", fontsize=13, loc="left")
    m2 = anom[["sar_flood_km2_anom", "dw_flood_km2_anom"]].dropna()
    r2 = [f for f in comp["key_findings"] if "Dynamic World" in f["relationship"]][0]
    _scatter(axes[1], m2["dw_flood_km2_anom"], m2["sar_flood_km2_anom"], "Dynamic World (km²)", "Radar index (km²)",
             C_SAR, r2["spearman_rho"], r2["p_value"])
    axes[1].set_title("Optical reference", fontsize=13, loc="left")
    fig.subplots_adjust(left=0.16, right=0.98, bottom=0.34, top=0.88, wspace=0.5)
    _source(fig, f"Monthly anomalies from the 2019-2024 export; n = {len(m)} and {len(m2)} pairs")
    return fig


# Maps are drawn in UTM zone 31N (EPSG:32631), the standard metric grid for this area (central meridian 3°E).
# Distances, the scale bar and the grid are therefore true, and north is grid north (within about 1° of true north here).
UTM = "EPSG:32631"


def _utm_rings(gj):
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, UTM, always_xy=True)
    out = []
    for f in gj["features"]:
        z = f["properties"]["zone_id"]
        ring = np.array(f["geometry"]["coordinates"][0]) if f["geometry"]["type"] == "Polygon" else np.array(f["geometry"]["coordinates"][0][0])
        x, y = tr.transform(ring[:, 0], ring[:, 1])
        out.append((z, np.column_stack([x, y])))
    return out


def _utm_bounds(rings, pad=15000):
    xs = np.concatenate([r[:, 0] for _, r in rings]); ys = np.concatenate([r[:, 1] for _, r in rings])
    return (xs.min() - pad, xs.max() + pad, ys.min() - pad, ys.max() + pad)


def _reproject_png(png, geo_bounds, utm_bounds):
    from PIL import Image
    """Reproject a lon/lat RGBA PNG (rasters.json bounds) onto the UTM grid used by the maps, nearest neighbour."""
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling
    arr = np.array(Image.open(png).convert("RGBA"))
    H, W = arr.shape[:2]
    src_t = from_bounds(geo_bounds["west"], geo_bounds["south"], geo_bounds["east"], geo_bounds["north"], W, H)
    w, e, s_, n = utm_bounds
    h = int(round(W * (n - s_) / (e - w)))
    dst_t = from_bounds(w, s_, e, n, W, h)
    out = np.zeros((h, W, 4), dtype=np.uint8)
    for k in range(4):
        reproject(source=arr[..., k], destination=out[..., k], src_transform=src_t, src_crs="EPSG:4326",
                  dst_transform=dst_t, dst_crs=UTM, resampling=Resampling.nearest)
    return out


def _carto(ax, bounds, bar=False, north=False, ticks=True, scale_km=20, step_km=20, fs=6.5, bar_pos="top"):
    """Map furniture for a UTM map (metres): neatline, grid ticks in km, a two-tone scale bar of exact length and a
    north arrow. bounds = (west, east, south, north) in metres."""
    from matplotlib.patches import Polygon as MPoly, Rectangle
    import matplotlib.patheffects as pe
    w, e, s_, n = bounds
    ax.set_xlim(w, e); ax.set_ylim(s_, n)
    ax.set_aspect("equal")
    for sp in ax.spines.values():
        sp.set_visible(True); sp.set_linewidth(0.7); sp.set_color("#111")
    if ticks:
        xt = np.arange(np.ceil(w / (step_km * 1000)) * step_km * 1000, e, step_km * 1000)
        yt = np.arange(np.ceil(s_ / (step_km * 1000)) * step_km * 1000, n, step_km * 1000)
        ax.set_xticks(xt); ax.set_yticks(yt)
        ax.set_xticklabels([f"{x / 1000:.0f}" for x in xt], fontsize=fs, color="#222")
        ax.set_yticklabels([f"{y / 1000:.0f}" for y in yt], fontsize=fs, color="#222")
        ax.tick_params(length=2.5, width=0.5, colors="#222", pad=2)
        ax.set_xlabel("Easting, km (UTM 31N)", fontsize=fs + 0.5, color="#222", labelpad=2)
        ax.set_ylabel("Northing, km", fontsize=fs + 0.5, color="#222", labelpad=2)
        # graticule drawn above the unit shading so it is visible: dotted lines at every tick
        for x_ in xt:
            ax.plot([x_, x_], [s_, n], color="#333333", lw=0.5, ls=(0, (1.5, 2)), alpha=0.7, zorder=4)
        for y_ in yt:
            ax.plot([w, e], [y_, y_], color="#333333", lw=0.5, ls=(0, (1.5, 2)), alpha=0.7, zorder=4)
    else:
        ax.set_xticks([]); ax.set_yticks([])
    halo = [pe.withStroke(linewidth=2, foreground="white")]
    if bar:
        L = scale_km * 1000; h = 0.010 * (n - s_)
        x0, y0 = w + 0.06 * (e - w), (n - 0.09 * (n - s_)) if bar_pos == "top" else (s_ + 0.06 * (n - s_))
        ax.add_patch(Rectangle((x0, y0), L / 2, h, fc="#111", ec="#111", lw=0.5, zorder=8))
        ax.add_patch(Rectangle((x0 + L / 2, y0), L / 2, h, fc="#fff", ec="#111", lw=0.5, zorder=8))
        ax.text(x0, y0 + 1.6 * h, "0", ha="center", va="bottom", fontsize=fs, color="#111", zorder=9, path_effects=halo)
        if fs >= 6:
            ax.text(x0 + L / 2, y0 + 1.6 * h, f"{scale_km // 2}", ha="center", va="bottom", fontsize=fs, color="#111", zorder=9, path_effects=halo)
        ax.text(x0 + L + 0.015 * (e - w), y0 + 1.6 * h, f"{scale_km} km", ha="left", va="bottom", fontsize=fs, color="#111", zorder=9, path_effects=halo)
    if north:
        ww = 0.018 * (e - w); H = 0.075 * (n - s_)
        x = e - 0.07 * (e - w); top = n - 0.09 * (n - s_); base = top - H
        ax.add_patch(MPoly([(x, top), (x - ww, base), (x, base)], closed=True, fc="#111", ec="#111", lw=0.4, zorder=8))
        ax.add_patch(MPoly([(x, top), (x, base), (x + ww, base)], closed=True, fc="#fff", ec="#111", lw=0.4, zorder=8))
        ax.text(x, top + 0.012 * (n - s_), "N", ha="center", va="bottom", fontsize=fs + 1, fontweight="bold", color="#111", zorder=9, path_effects=halo)


def _unit_key(fig, y=0.005, ncol=5, fs=5.5):
    from matplotlib.patches import Patch
    names = {"Z1": "Z1 Upper Ogun headwaters", "Z2": "Z2 Oyan-Ofiki tributary", "Z3": "Z3 Middle Ogun mainstem",
             "Z4": "Z4 Lower Ogun alluvial corridor", "Z5": "Z5 Lagoon zone (outside catchment, dashed)"}
    handles = [Patch(facecolor="#ffffff", edgecolor="#3d3d3d", lw=0.8, label=v) for v in names.values()]
    fig.legend(handles=handles, loc="lower center", ncol=ncol, fontsize=fs, frameon=False, bbox_to_anchor=(0.5, y), handlelength=1.0, columnspacing=1.0)


def _panel_letters(axes):
    for k, ax in enumerate(axes):
        ax.text(0.02, 0.97, f"({chr(97 + k)})", transform=ax.transAxes, ha="left", va="top", fontsize=7, fontweight="bold", color="#111", zorder=12)


def _label(ax, z, c, txt, x_out, fs=8):
    """Unit label. Large units (Z1, Z2) carry their label inside. Small units (Z3 to Z5) get a label outside the
    catchment on the right, joined to the unit by a leader line, so it never sits across a unit edge."""
    if z in ("Z3", "Z4", "Z5"):
        ax.annotate(txt, xy=(c[0], c[1]), xytext=(x_out, c[1]), ha="left", va="center", fontsize=fs, fontweight="bold",
                    color="#111", arrowprops=dict(arrowstyle="-", color="#333", lw=0.6), path_effects=[pe_halo()], annotation_clip=False)
    else:
        ax.text(c[0], c[1], txt, ha="center", va="center", fontsize=fs, fontweight="bold", color="#111", path_effects=[pe_halo()])


def fig_study_map_print():
    """Print map in UTM 31N: units coloured by mean rainfall over the reprojected terrain and land cover, legend,
    metric scale bar, north arrow and grid. The live map on the page is the interactive version."""
    from matplotlib.patches import Patch, Polygon as MPoly
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    units = json.loads((DATA / "unit_summary.json").read_text())["units"]
    rj = json.loads((DATA / "rasters" / "rasters.json").read_text())
    names = {"Z1": "Upper Ogun headwaters", "Z2": "Oyan-Ofiki tributary", "Z3": "Middle Ogun mainstem",
             "Z4": "Lower Ogun alluvial corridor", "Z5": "Lagoon zone (outside catchment)"}
    rings = _utm_rings(gj)
    bounds = _utm_bounds(rings)
    terr = _reproject_png(DATA / "rasters" / "terrain.png", rj["bounds"], bounds)
    land = _reproject_png(DATA / "rasters" / "landcover.png", rj["bounds"], bounds)
    fig, ax = plt.subplots(figsize=(4.6, 5.4), dpi=220)
    ax.imshow(terr, extent=bounds, alpha=0.55, zorder=1, interpolation="nearest")
    ax.imshow(land, extent=bounds, alpha=0.5, zorder=2, interpolation="nearest")
    rain = {z: units[z]["rain"]["mean"] for z in units}
    lo, hi = min(rain.values()), max(rain.values())
    cmap = plt.get_cmap("Blues")
    role = {f["properties"]["zone_id"]: f["properties"]["role_color"] for f in gj["features"]}
    for z, ring in rings:
        t = (rain[z] - lo) / max(hi - lo, 1e-9)
        ax.add_patch(MPoly(ring, closed=True, facecolor=cmap(0.25 + 0.6 * t), alpha=0.6, edgecolor=role[z], lw=1.2, zorder=3,
                           linestyle="--" if z == "Z5" else "-"))
        c = ring.mean(axis=0)
        if z == "Z5":
            _label(ax, z, c, z, ring[:, 0].max() + 0.12 * (bounds[1] - bounds[0]), fs=8)
        else:
            ax.text(c[0], c[1], z, ha="center", va="center", fontsize=8, fontweight="bold", zorder=4, color="#111", path_effects=[pe_halo()])
    _carto(ax, bounds, bar=True, north=True, ticks=True, scale_km=20, step_km=20, fs=6)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(lo, hi))
    cb = fig.colorbar(sm, ax=ax, fraction=0.05, pad=0.03, shrink=0.55)
    cb.set_label("Mean rainfall, mm per month, 2019-2024", fontsize=6.5, color="#222"); cb.ax.tick_params(labelsize=6, colors="#222")
    handles = [Patch(facecolor=cmap(0.25 + 0.6 * ((rain[z] - lo) / max(hi - lo, 1e-9))), alpha=0.6, edgecolor=role[z], lw=1.0,
                     label=f"{z}  {names[z]}") for z in ["Z1", "Z2", "Z3", "Z4", "Z5"]]
    handles.append(Patch(facecolor="#d9d4c4", edgecolor="#8a7f66", label=f"Terrain, elevation {rj['terrain']['elevation_min_m']:.0f}-{rj['terrain']['elevation_max_m']:.0f} m"))
    for lc in rj["landcover"]["legend"]:
        handles.append(Patch(facecolor=lc["colour"], edgecolor="#555", lw=0.4, label=f"Land cover: {lc['label']} ({lc['share_pct']:.1f}%)"))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, -0.12), ncol=2, fontsize=5.8, frameon=False,
              handlelength=1.2, columnspacing=1.0, labelcolor="#222")
    ax.set_title("Ogun catchment and lagoon zone, 2019-2024", fontsize=8, loc="left", color="#111")
    fig.subplots_adjust(left=0.13, right=0.84, top=0.94, bottom=0.42)
    fig.text(0.02, 0.012, f"Units: WWF HydroBASINS level 9 (Z1-Z4) and lagoon zone (Z5). Rainfall: CHIRPS via Google Earth Engine. Terrain: Copernicus DEM GLO-30. Land cover: ESA WorldCover 2021 (accuracy for Africa {rj['landcover']['accuracy_africa_pct']}%), via Microsoft Planetary Computer. Projection: UTM zone 31N (EPSG:32631).",
             fontsize=5.5, color="#222", va="bottom", wrap=True)
    return fig


def fig_seasonal_maps():
    """Six maps in UTM 31N, three rows (rainfall, soil moisture, Dynamic World water) by two columns (wet and dry season).
    Each row shares one colour scale, shown beside it. Values are the unit means from docs/data/unit_summary.json."""
    from matplotlib.patches import Polygon as MPoly
    from matplotlib.colors import Normalize
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    seas = {z: v["seasonal"] for z, v in json.loads((DATA / "unit_summary.json").read_text())["units"].items()}
    rows = [("rain", "Rainfall\nmm per month", "Blues", "mm per month"),
            ("soil", "Soil moisture, 0-7 cm\nm³ per m³", "YlGn", "m³ per m³"),
            ("dw", "Dynamic World water\nkm² per month", "Purples", "km²")]
    cols = [("wet_mean", "Wet season (April-October)"), ("dry_mean", "Dry season (November-March)")]
    rings = _utm_rings(gj)
    bounds = _utm_bounds(rings)
    x_out = max(r[:, 0].max() for _, r in rings) + 0.08 * (bounds[1] - bounds[0])
    fig, axes = plt.subplots(3, 2, figsize=(5.8, 8.6), dpi=220)
    fig.subplots_adjust(left=0.13, right=0.84, top=0.91, bottom=0.13, wspace=0.07, hspace=0.1)
    for r, (var, row_label, cmap_name, cb_label) in enumerate(rows):
        vals = [seas[z][var][k] for z in seas for k, _ in cols if seas[z].get(var, {}).get(k) is not None]
        lo, hi = min(vals), max(vals)
        cmap = plt.get_cmap(cmap_name); norm = Normalize(lo, hi)
        dec = 0 if var == "rain" else 2 if var == "soil" else 1
        for c_, (key, col_label) in enumerate(cols):
            ax = axes[r][c_]
            for z, ring in rings:
                v = seas[z].get(var, {}).get(key)
                fc = cmap(0.15 + 0.75 * norm(v)) if v is not None else "#d9d9d3"
                ax.add_patch(MPoly(ring, closed=True, facecolor=fc, edgecolor="#1a1a1a", lw=1.1, linestyle="--" if z == "Z5" else "-", zorder=3))
                cen = ring.mean(axis=0)
                txt = z if v is None else (f"{z}  {v:.{dec}f}" if z in ("Z3", "Z4", "Z5") else f"{z}\n{v:.{dec}f}")
                _label(ax, z, cen, txt, x_out, fs=7.5)
            _carto(ax, bounds, bar=(r == 2 and c_ == 0), north=(r == 0 and c_ == 0), ticks=True, scale_km=20, step_km=40, fs=6, bar_pos="bottom")
            ax.set_xlim(bounds[0], x_out + 0.6 * (bounds[1] - bounds[0]))
            if c_ != 0: ax.set_yticklabels([]); ax.set_ylabel("")
            if r != 2: ax.set_xticklabels([]); ax.set_xlabel("")
            ax.text(0.03, 0.97, f"({chr(97 + 2 * r + c_)})", transform=ax.transAxes, ha="left", va="top", fontsize=7, fontweight="bold", color="#111", zorder=12)
            if r == 0: ax.set_title(col_label, fontsize=7.5, color="#111", pad=4)
            if c_ == 0: ax.set_ylabel(row_label, fontsize=7.5, color="#111", labelpad=4)
        pos = axes[r][1].get_position()
        cax = fig.add_axes([pos.x1 + 0.025, pos.y0, 0.018, pos.height])
        cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax, orientation="vertical")
        cb.ax.tick_params(labelsize=6.5, colors="#222", length=2)
        cb.set_label(cb_label, fontsize=6.5, color="#222", labelpad=3)
    _unit_key(fig, y=0.012)
    return fig


def fig_unit_landcover_maps():
    """Two maps in UTM 31N from docs/data/unit_landcover.json: built-up and cropland share of each unit's area (WorldCover 2021)."""
    from matplotlib.patches import Polygon as MPoly
    from matplotlib.colors import Normalize
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    lc = json.loads((DATA / "unit_landcover.json").read_text())["units"]
    specs = [("Built-up", "Built-up share of unit area, %", "Reds"), ("Cropland", "Cropland share of unit area, %", "YlOrBr")]
    rings = _utm_rings(gj)
    bounds = _utm_bounds(rings)
    x_out = max(r[:, 0].max() for _, r in rings) + 0.08 * (bounds[1] - bounds[0])
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 4.2), dpi=200)
    for k, (ax, (cls, title, cmap_name)) in enumerate(zip(axes, specs)):
        vals = {z: lc[z]["share_pct"][cls] for z in lc}
        cmap = plt.get_cmap(cmap_name); norm = Normalize(0.0, max(vals.values()))
        for z, ring in rings:
            v = vals.get(z)
            fc = cmap(0.1 + 0.75 * norm(v)) if v is not None else "#e9e9e4"
            ax.add_patch(MPoly(ring, closed=True, facecolor=fc, edgecolor="#3d3d3d", lw=0.7, linestyle="--" if z == "Z5" else "-"))
            c = ring.mean(axis=0)
            txt = z if v is None else (f"{z}  {v:.1f}%" if z in ("Z3", "Z4", "Z5") else f"{z}\n{v:.1f}%")
            _label(ax, z, c, txt, x_out, fs=7.5)
        _carto(ax, bounds, bar=(k == 0), north=(k == 0), ticks=(k == 0), scale_km=20, step_km=40, fs=6, bar_pos="bottom")
        ax.set_xlim(bounds[0], x_out + 0.6 * (bounds[1] - bounds[0]))
        ax.set_title(title, fontsize=7.5, loc="left", color="#111")
    fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.2, wspace=0.14)
    _panel_letters(axes)
    _unit_key(fig, y=0.02)
    return fig


def pe_halo():
    import matplotlib.patheffects as pe
    return pe.withStroke(linewidth=2, foreground="white")


def phone_variants():
    """Single-column versions of the two multi-panel maps for phone widths (no sideways scrolling)."""
    return {"study_seasonal_maps_phone": _seasonal_phone(), "study_landcover_maps_phone": _landcover_phone()}


def _seasonal_phone():
    from matplotlib.patches import Polygon as MPoly
    from matplotlib.colors import Normalize
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    seas = {z: v["seasonal"] for z, v in json.loads((DATA / "unit_summary.json").read_text())["units"].items()}
    rows = [("rain", "Rainfall, mm per month", "Blues", "mm per month"),
            ("soil", "Soil moisture, 0-7 cm, m³ per m³", "YlGn", "m³ per m³"),
            ("dw", "Dynamic World water, km² per month", "Purples", "km²")]
    cols = [("wet_mean", "Wet season (April-October)"), ("dry_mean", "Dry season (November-March)")]
    rings = _utm_rings(gj); bounds = _utm_bounds(rings)
    x_out = max(r[:, 0].max() for _, r in rings) + 0.08 * (bounds[1] - bounds[0])
    fig, axes = plt.subplots(6, 1, figsize=(3.9, 12.4), dpi=220)
    fig.subplots_adjust(left=0.2, right=0.8, top=0.97, bottom=0.1, hspace=0.22)
    for r, (var, row_label, cmap_name, cb_label) in enumerate(rows):
        vals = [seas[z][var][k] for z in seas for k, _ in cols if seas[z].get(var, {}).get(k) is not None]
        lo, hi = min(vals), max(vals)
        cmap = plt.get_cmap(cmap_name); norm = Normalize(lo, hi)
        dec = 0 if var == "rain" else 2 if var == "soil" else 1
        for c_, (key, col_label) in enumerate(cols):
            ax = axes[2 * r + c_]
            for z, ring in rings:
                v = seas[z].get(var, {}).get(key)
                fc = cmap(0.15 + 0.75 * norm(v)) if v is not None else "#d9d9d3"
                ax.add_patch(MPoly(ring, closed=True, facecolor=fc, edgecolor="#1a1a1a", lw=1.1, linestyle="--" if z == "Z5" else "-", zorder=3))
                cen = ring.mean(axis=0)
                txt = z if v is None else (f"{z}  {v:.{dec}f}" if z in ("Z3", "Z4", "Z5") else f"{z}\n{v:.{dec}f}")
                _label(ax, z, cen, txt, x_out, fs=8)
            _carto(ax, bounds, bar=(r == 0 and c_ == 0), north=(r == 0 and c_ == 0), ticks=(r == 2 and c_ == 1), scale_km=20, step_km=40, fs=6.5, bar_pos="bottom")
            ax.set_xlim(bounds[0], x_out + 0.6 * (bounds[1] - bounds[0]))
            ax.set_title(f"({chr(97 + 2 * r + c_)}) {col_label}", fontsize=8, loc="left", color="#111", pad=3)
            if not (r == 2 and c_ == 1):
                ax.set_xticklabels([]); ax.set_yticklabels([]); ax.set_xlabel(""); ax.set_ylabel("")
        if r == 0 or True:
            axes[2 * r].set_ylabel(row_label, fontsize=7.5, color="#111", labelpad=4)
        pos = axes[2 * r + 1].get_position()
        cax = fig.add_axes([pos.x1 + 0.04, pos.y0, 0.04, pos.height])
        cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=norm), cax=cax, orientation="vertical")
        cb.ax.tick_params(labelsize=6.5, colors="#222", length=2)
        cb.set_label(cb_label, fontsize=6.5, color="#222", labelpad=3)
    _unit_key(fig, y=0.003, ncol=2, fs=7)
    return fig


def _landcover_phone():
    from matplotlib.patches import Polygon as MPoly
    from matplotlib.colors import Normalize
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    lc = json.loads((DATA / "unit_landcover.json").read_text())["units"]
    specs = [("Built-up", "Built-up share of unit area, %", "Reds"), ("Cropland", "Cropland share of unit area, %", "YlOrBr")]
    rings = _utm_rings(gj); bounds = _utm_bounds(rings)
    x_out = max(r[:, 0].max() for _, r in rings) + 0.08 * (bounds[1] - bounds[0])
    fig, axes = plt.subplots(2, 1, figsize=(3.9, 7.4), dpi=220)
    fig.subplots_adjust(left=0.2, right=0.96, top=0.95, bottom=0.08, hspace=0.25)
    for k, (ax, (cls, title, cmap_name)) in enumerate(zip(axes, specs)):
        vals = {z: lc[z]["share_pct"][cls] for z in lc}
        cmap = plt.get_cmap(cmap_name); norm = Normalize(0.0, max(vals.values()))
        for z, ring in rings:
            v = vals.get(z)
            fc = cmap(0.1 + 0.75 * norm(v)) if v is not None else "#e9e9e4"
            ax.add_patch(MPoly(ring, closed=True, facecolor=fc, edgecolor="#1a1a1a", lw=1.1, linestyle="--" if z == "Z5" else "-", zorder=3))
            c = ring.mean(axis=0)
            txt = z if v is None else (f"{z}  {v:.1f}%" if z in ("Z3", "Z4", "Z5") else f"{z}\n{v:.1f}%")
            _label(ax, z, c, txt, x_out, fs=8)
        _carto(ax, bounds, bar=(k == 1), north=(k == 0), ticks=(k == 1), scale_km=20, step_km=40, fs=6.5, bar_pos="bottom")
        ax.set_xlim(bounds[0], x_out + 0.6 * (bounds[1] - bounds[0]))
        ax.set_title(f"({chr(97 + k)}) {title}", fontsize=8, loc="left", color="#111", pad=3)
        if k == 0:
            ax.set_xticklabels([]); ax.set_xlabel("")
    _unit_key(fig, y=0.003, ncol=2, fs=7)
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for _name, _fig in phone_variants().items():
        _fig.savefig(OUT / f"{_name}.png", dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.12)
        plt.close(_fig)
        print("wrote", OUT / f"{_name}.png")
    diag = json.loads((DATA / "cascade_diagnostics.json").read_text())
    comp = diag
    df = load_monthly_series_safe()
    df["cal_month"] = pd.to_datetime(df["year_month"], format="%Y-%m").dt.month
    anom = pd.DataFrame(index=df.index)
    for col in _compiler().SERIES_COLUMNS:
        anom[f"{col}_anom"] = df[col] - df.groupby("cal_month")[col].transform("mean")
    figs = {
        "fig3_series": fig2_series(df),
        "fig4_association": fig3_association(diag),
        "fig5_scatter": fig4_scatter(comp, anom),
        "study_map_print": fig_study_map_print(),
        "study_seasonal_maps": fig_seasonal_maps(),
        "study_landcover_maps": fig_unit_landcover_maps(),
    }
    for name, fig in figs.items():
        fig.savefig(OUT / f"{name}.png", dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.12)
        plt.close(fig)
        print("wrote", OUT / f"{name}.png")


def load_monthly_series_safe():
    return _compiler().load_monthly_series(DATA / "ogun_monthly_timeseries.csv")


if __name__ == "__main__":
    main()
