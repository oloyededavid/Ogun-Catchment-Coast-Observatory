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
    lines = textwrap.wrap(f"{text}  ·  {AUTHOR}, {DATE}", width=105)
    fig.text(0.02, 0.012, "\n".join(lines), fontsize=6.5, color=INK2, va="bottom", linespacing=1.3)


def fig1_study_area(gj):
    fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=200)
    for f in sorted(gj["features"], key=lambda f: -f["properties"]["area_km2"]):
        p = f["properties"]
        for ring in (f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]):
            xy = np.array(ring[0])
            ax.fill(xy[:, 0], xy[:, 1], color=p["role_color"], alpha=0.35, lw=0)
            ax.plot(xy[:, 0], xy[:, 1], color=p["role_color"], lw=0.8)
            c = xy.mean(axis=0)
            dy = -0.05 if p["zone_id"] == "Z5" else 0
            ax.text(c[0], c[1] + dy, p["zone_id"], fontsize=9, fontweight="bold", ha="center", va="center", color=INK,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.6, pad=0.5) if p["zone_id"] == "Z5" else None)
    ax.set_aspect(1 / np.cos(np.radians(7.5)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.grid(color=RULE, lw=0.4)
    handles = [plt.Rectangle((0, 0), 1, 1, color=f["properties"]["role_color"], alpha=0.5) for f in gj["features"]]
    labels = [f"{f['properties']['zone_id']} {f['properties']['zone_name']} ({f['properties']['area_km2']:,.0f} km²)" for f in gj["features"]]
    ax.legend(handles, labels, fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.subplots_adjust(right=0.6, bottom=0.12, top=0.96, left=0.12)
    _source(fig, "Units: WWF HydroBASINS level 9 (Z1–Z4); Z5 is a rectangular lagoon zone, not a watershed")
    return fig


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


def fig3_lags(diag):
    fig, ax = plt.subplots(figsize=(6.0, 3.6), dpi=200)
    seas, deseas = diag["rain_to_sar_inundation_lags_seasonal"], diag["rain_to_sar_inundation_lags_deseasonalized"]
    lags = ["lag_0_month", "lag_1_month", "lag_2_month"]
    x = np.arange(3)
    for k, (res, name, colour) in enumerate([(seas, "Raw monthly values", "#9fb9d6"), (deseas, "Seasonal cycle removed", C_RAIN)]):
        rho = [res[l]["spearman_rho"] for l in lags]
        ax.bar(x + (k - 0.5) * 0.36, rho, width=0.34, color=colour, label=name)
        for xi, l, r in zip(x + (k - 0.5) * 0.36, lags, rho):
            ax.text(xi, r + (0.02 if r >= 0 else -0.05), f"{r:+.2f}", ha="center", fontsize=7.5)
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xticks(x, ["same month", "one month later", "two months later"])
    ax.set_ylabel("Spearman ρ, rain → inundation")
    ax.set_ylim(-0.6, 0.4)
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    ax.grid(axis="y", color=RULE, lw=0.4)
    sig = [f"lag {l.split('_')[1]}: q = {seas[l]['p_value_bh_fdr']:.3f}" for l in lags if seas[l]["p_value_bh_fdr"] < 0.05]
    note = "significant (raw values): " + "; ".join(sig) if sig else "no raw-value lag significant"
    _source(fig, f"cascade_diagnostics.json; n = 70–72 pairs per lag; {note}")
    return fig


def fig4_relationships(diag):
    fig, ax = plt.subplots(figsize=(6.0, 3.6), dpi=200)
    rows = diag["key_findings"]
    short = {
        "Rain -> floodplain SAR inundation (same month, deseasonalized)": "Rain → inundation, same month",
        "Rain -> floodplain SAR inundation (1-month lag, deseasonalized)": "Rain → inundation, one month later",
        "Soil moisture -> floodplain SAR inundation (same month, deseasonalized)": "Soil moisture → inundation, same month",
        "Floodplain SAR inundation -> estuary NDTI (deseasonalized)": "Inundation → lagoon turbidity",
        "SAR inundation vs Dynamic World flooding (deseasonalized)": "Radar index vs Dynamic World",
    }
    labels = [short.get(r["relationship"], r["relationship"]) for r in rows]
    rho = np.array([r["spearman_rho"] for r in rows])
    q = np.array([r["p_value"] for r in rows])
    y = np.arange(len(rows))[::-1]
    ax.axvline(0, color=INK2, lw=0.6)
    for yi, r, qi, lab in zip(y, rho, q, labels):
        colour = C_RAIN if qi < 0.05 else "#9a9a9a"
        ax.plot([0, r], [yi, yi], color=colour, lw=1.2)
        ax.plot(r, yi, "o", color=colour, ms=5)
        ax.text(0.64, yi, f"q = {qi:.2f}", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, labels, fontsize=9)
    ax.set_xlim(-0.2, 0.75)
    ax.set_xlabel("Spearman ρ (recommended estimator)", fontsize=8)
    ax.grid(axis="x", color=RULE, lw=0.4)
    fig.subplots_adjust(left=0.5, right=0.97, bottom=0.2, top=0.96)
    _source(fig, "cascade_diagnostics.json, key_findings; q = BH-adjusted p; grey = q ≥ 0.05")
    return fig


def fig5_reservoir(diag):
    fig, ax = plt.subplots(figsize=(6.0, 3.6), dpi=200)
    base = diag["rain_to_sar_inundation_lags_deseasonalized"]
    ctl = diag["rain_to_sar_inundation_controlling_for_oyan_reservoir"]["deseasonalized"]
    lags = ["lag_0_month", "lag_1_month", "lag_2_month"]
    x = np.arange(3)
    for k, (res, name, colour) in enumerate([(base, "Rain only", "#9fb9d6"), (ctl, "Rain, controlling for reservoir area", C_RAIN)]):
        rho = [res[l]["spearman_rho"] for l in lags]
        ax.bar(x + (k - 0.5) * 0.36, rho, width=0.34, color=colour, label=name)
        for xi, r in zip(x + (k - 0.5) * 0.36, rho):
            ax.text(xi, r + (0.02 if r >= 0 else -0.05), f"{r:+.2f}", ha="center", fontsize=7.5)
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xticks(x, ["same month", "one month later", "two months later"])
    ax.set_ylabel("Spearman ρ, deseasonalised")
    ax.set_ylim(-0.6, 0.4)
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    ax.grid(axis="y", color=RULE, lw=0.4)
    _source(fig, "cascade_diagnostics.json; reservoir control = Sentinel-1 open-water area of Oyan Reservoir; dam releases unavailable")
    return fig


def _scatter(ax, x, y, xl, yl, colour, rho, q):
    ax.scatter(x, y, s=14, color=colour, alpha=0.8, lw=0)
    ax.axhline(0, color=RULE, lw=0.6)
    ax.axvline(0, color=RULE, lw=0.6)
    ax.set_xlabel(xl, fontsize=8)
    ax.set_ylabel(yl, fontsize=8)
    ax.text(0.03, 0.96, f"ρ = {rho:+.2f}\nq = {q:.2f}", transform=ax.transAxes, va="top", fontsize=8)
    ax.grid(color=RULE, lw=0.4)


def fig6_turbidity(comp, df, anom):
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=200)
    m = anom[["sar_flood_km2_anom", "estuary_ndti_anom"]].dropna()
    r = [f for f in comp["key_findings"] if "NDTI" in f["relationship"]][0]
    _scatter(ax, m["sar_flood_km2_anom"], m["estuary_ndti_anom"], "Radar index anomaly (km²)", "Lagoon NDTI anomaly",
             C_NDTI, r["spearman_rho"], r["p_value"])
    fig.subplots_adjust(left=0.16, bottom=0.16, right=0.97, top=0.97)
    _source(fig, f"Monthly anomalies, n = {len(m)} pairs")
    return fig


def fig7_dynamic_world(comp, anom):
    fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=200)
    m = anom[["sar_flood_km2_anom", "dw_flood_km2_anom"]].dropna()
    r = [f for f in comp["key_findings"] if "Dynamic World" in f["relationship"]][0]
    _scatter(ax, m["dw_flood_km2_anom"], m["sar_flood_km2_anom"], "Dynamic World anomaly (km²)", "Radar index anomaly (km²)",
             C_SAR, r["spearman_rho"], r["p_value"])
    fig.subplots_adjust(left=0.16, bottom=0.16, right=0.97, top=0.97)
    _source(fig, f"Monthly anomalies, n = {len(m)} pairs")
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    diag = json.loads((DATA / "cascade_diagnostics.json").read_text())
    comp = _compiler()
    df = comp.load_monthly_series(DATA / "ogun_monthly_timeseries.csv")
    df["cal_month"] = pd.to_datetime(df["year_month"], format="%Y-%m").dt.month
    anom = pd.DataFrame(index=df.index)
    for col in comp.SERIES_COLUMNS:
        anom[f"{col}_anom"] = df[col] - df.groupby("cal_month")[col].transform("mean")
    figs = {
        "fig1_study_area": fig1_study_area(gj),
        "fig2_series": fig2_series(df),
        "fig3_lags": fig3_lags(diag),
        "fig4_relationships": fig4_relationships(diag),
        "fig5_reservoir": fig5_reservoir(diag),
        "fig6_turbidity": fig6_turbidity(diag, df, anom),
        "fig7_dynamic_world": fig7_dynamic_world(diag, anom),
    }
    for name, fig in figs.items():
        fig.savefig(OUT / f"{name}.png", dpi=200, facecolor="white")
        plt.close(fig)
        print("wrote", OUT / f"{name}.png")


if __name__ == "__main__":
    main()
