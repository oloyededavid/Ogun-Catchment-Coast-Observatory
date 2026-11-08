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
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False})
C_RAIN, C_SOIL, C_SAR, C_DW, C_NDTI = "#2d6cb0", "#3c8d6e", "#c0501a", "#7a5aa6", "#8a6d1f"


def _compiler():
    spec = importlib.util.spec_from_file_location("compile_observatory", ROOT / "src" / "02_compile_observatory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _source(fig, text):
    import textwrap
    lines = textwrap.wrap(f"Source: {text}", width=105)
    fig.text(0.02, 0.012, "\n".join(lines), fontsize=6.5, color=INK2, va="bottom", linespacing=1.3)


def fig2_series(df):
    fig, axes = plt.subplots(5, 1, figsize=(6.0, 7.4), sharex=True, dpi=200, gridspec_kw={"hspace": 0.25})
    t = pd.to_datetime(df["year_month"], format="%Y-%m")
    spec = [("rain_mm", "Rain (mm/month)", C_RAIN), ("shallow_sm_m3m3", "Soil moisture (m³/m³)", C_SOIL),
            ("sar_flood_km2", "Radar index (km²)", C_SAR), ("dw_flood_km2", "Dynamic World (km²)", C_DW),
            ("estuary_ndti", "Lagoon NDTI", C_NDTI)]
    for ax, (col, label, colour) in zip(axes, spec):
        ax.plot(t, df[col], color=colour, lw=1.0)
        ax.set_ylabel(label, fontsize=7.5)
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
        ax.text(0.62, yi, f"q = {q:.3f}" if q >= 0.001 else "q < 0.001", va="center", fontsize=10, color=INK2)
    ax.axvline(0, color=INK2, lw=0.6)
    ax.set_yticks(y, [f"{lab}  ({kind})" for lab, kind, _, _ in rows], fontsize=10)
    ax.tick_params(axis="x", labelsize=10)
    ax.set_xlim(-0.6, 0.85)
    ax.set_xlabel("Spearman ρ (recommended estimator)", fontsize=10)
    ax.grid(axis="x", color=RULE, lw=0.4)
    fig.subplots_adjust(left=0.56, right=0.97, bottom=0.2, top=0.97)
    _source(fig, "cascade_diagnostics.json. Hollow: raw values; filled: anomalies. Blue: q < 0.05; grey: not significant")
    return fig


def _scatter(ax, x, y, xl, yl, colour, rho, q):
    ax.scatter(x, y, s=14, color=colour, alpha=0.8, lw=0)
    ax.axhline(0, color=RULE, lw=0.6)
    ax.axvline(0, color=RULE, lw=0.6)
    ax.set_xlabel(xl, fontsize=10)
    ax.set_ylabel(yl, fontsize=10)
    ax.tick_params(labelsize=10)
    ax.text(0.03, 0.04, f"ρ = {rho:+.2f}\nq = {q:.2f}", transform=ax.transAxes, va="bottom", fontsize=10)
    ax.grid(color=RULE, lw=0.4)


def fig4_scatter(comp, anom):
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 3.6), dpi=200)
    m = anom[["sar_flood_km2_anom", "estuary_ndti_anom"]].dropna()
    r = [f for f in comp["key_findings"] if "NDTI" in f["relationship"]][0]
    _scatter(axes[0], m["sar_flood_km2_anom"], m["estuary_ndti_anom"], "Radar index anomaly (km²)", "Lagoon NDTI anomaly",
             C_NDTI, r["spearman_rho"], r["p_value"])
    axes[0].set_title("Lagoon turbidity", fontsize=11, loc="left")
    m2 = anom[["sar_flood_km2_anom", "dw_flood_km2_anom"]].dropna()
    r2 = [f for f in comp["key_findings"] if "Dynamic World" in f["relationship"]][0]
    _scatter(axes[1], m2["dw_flood_km2_anom"], m2["sar_flood_km2_anom"], "Dynamic World anomaly (km²)", "Radar index anomaly (km²)",
             C_SAR, r2["spearman_rho"], r2["p_value"])
    axes[1].set_title("Optical reference", fontsize=11, loc="left")
    fig.subplots_adjust(left=0.16, right=0.98, bottom=0.22, top=0.88, wspace=0.5)
    _source(fig, f"Monthly anomalies from the 2019–2024 export; n = {len(m)} and {len(m2)} pairs")
    return fig


def fig_study_map_print():
    """Print version of the study-area map: units coloured by mean rainfall, terrain and land cover as context,
    with legend, scale bar and north arrow. The live map is the interactive version on the page."""
    import matplotlib.image as mpimg
    from matplotlib.patches import Polygon as MPoly
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    units = json.loads((DATA / "unit_summary.json").read_text())["units"]
    rj = json.loads((DATA / "rasters" / "rasters.json").read_text())
    b = rj["bounds"]
    extent = (b["west"], b["east"], b["south"], b["north"])
    fig, ax = plt.subplots(figsize=(6.0, 6.4), dpi=220)
    ax.imshow(mpimg.imread(DATA / "rasters" / "terrain.png"), extent=extent, alpha=0.55, zorder=1)
    ax.imshow(mpimg.imread(DATA / "rasters" / "landcover.png"), extent=extent, alpha=0.5, zorder=2)
    rain = {z: units[z]["rain"]["mean"] for z in units}
    lo, hi = min(rain.values()), max(rain.values())
    cmap = plt.get_cmap("Blues")
    for f in gj["features"]:
        z = f["properties"]["zone_id"]
        ring = np.array(f["geometry"]["coordinates"][0]) if f["geometry"]["type"] == "Polygon" else np.array(f["geometry"]["coordinates"][0][0])
        t = (rain[z] - lo) / max(hi - lo, 1e-9)
        ax.add_patch(MPoly(ring, closed=True, facecolor=cmap(0.25 + 0.6 * t), alpha=0.6, edgecolor=f["properties"]["role_color"], lw=1.6, zorder=3,
                           linestyle="--" if z == "Z5" else "-"))
        c = ring.mean(axis=0)
        ax.text(c[0], c[1], z, ha="center", va="center", fontsize=11, fontweight="bold", zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1.5))
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
    ax.set_aspect(1 / np.cos(np.radians((extent[2] + extent[3]) / 2)))
    ax.set_xlabel("Longitude (°E), WGS 84", fontsize=10); ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.tick_params(labelsize=9); ax.grid(color="#ffffff", lw=0.6, alpha=0.6)
    # scale bar (20 km) and north arrow
    km_deg = 1 / (111.32 * np.cos(np.radians((extent[2] + extent[3]) / 2)))
    x0, y0 = extent[0] + 0.08 * (extent[1] - extent[0]), extent[2] + 0.06 * (extent[3] - extent[2])
    ax.plot([x0, x0 + 20 * km_deg], [y0, y0], color="#111", lw=3, solid_capstyle="butt", zorder=5)
    ax.text(x0 + 10 * km_deg, y0 + 0.012, "20 km", ha="center", fontsize=9, zorder=5)
    ax.annotate("N", xy=(extent[1] - 0.08 * (extent[1] - extent[0]), extent[3] - 0.04 * (extent[3] - extent[2])),
                xytext=(extent[1] - 0.08 * (extent[1] - extent[0]), extent[3] - 0.12 * (extent[3] - extent[2])),
                ha="center", fontsize=11, fontweight="bold", arrowprops=dict(arrowstyle="-|>", color="#111", lw=1.5), zorder=5)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(lo, hi))
    cb = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02, shrink=0.7)
    cb.set_label("Mean rainfall, mm per month (2019–2024)", fontsize=9); cb.ax.tick_params(labelsize=8)
    ax.set_title("Ogun catchment and lagoon zone: units, mean rainfall, terrain and land cover", fontsize=11, loc="left")
    fig.subplots_adjust(left=0.1, right=0.9, top=0.93, bottom=0.17)
    _source(fig, f"Unit boundaries: WWF HydroBASINS level 9 (Z1–Z4), Z5 lagoon zone; rainfall: CHIRPS via Google Earth Engine; terrain: Copernicus DEM GLO-30 and land cover: ESA WorldCover 2021 (accuracy for Africa {rj['landcover']['accuracy_africa_pct']}%), via Microsoft Planetary Computer")
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    diag = json.loads((DATA / "cascade_diagnostics.json").read_text())
    comp = diag
    df = load_monthly_series_safe()
    df["cal_month"] = pd.to_datetime(df["year_month"], format="%Y-%m").dt.month
    anom = pd.DataFrame(index=df.index)
    for col in _compiler().SERIES_COLUMNS:
        anom[f"{col}_anom"] = df[col] - df.groupby("cal_month")[col].transform("mean")
    figs = {
        "fig2_series": fig2_series(df),
        "fig3_association": fig3_association(diag),
        "fig4_scatter": fig4_scatter(comp, anom),
        "study_map_print": fig_study_map_print(),
    }
    for name, fig in figs.items():
        fig.savefig(OUT / f"{name}.png", dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.12)
        plt.close(fig)
        print("wrote", OUT / f"{name}.png")


def load_monthly_series_safe():
    return _compiler().load_monthly_series(DATA / "ogun_monthly_timeseries.csv")


if __name__ == "__main__":
    main()
