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
    """Spearman rho for the same relationships, raw (seasonal) and anomaly (seasonal cycle removed)."""
    rows = []
    for lag in ("lag_0_month", "lag_1_month", "lag_2_month"):
        r = diag["rain_to_sar_inundation_lags_seasonal"][lag]
        rows.append((f"Rain → inundation, {['same month', 'one month later', 'two months later'][int(lag[4])]}", "raw", r))
    for lag in ("lag_0_month", "lag_1_month", "lag_2_month"):
        r = diag["rain_to_sar_inundation_lags_deseasonalized"][lag]
        rows.append((f"Rain → inundation, {['same month', 'one month later', 'two months later'][int(lag[4])]}", "anomaly", r))
    r = diag["soil_moisture_to_sar_inundation_lags_seasonal"]["lag_0_month"]
    rows.append(("Soil moisture → inundation, same month", "raw", r))
    r = diag["soil_moisture_to_sar_inundation_lags_deseasonalized"]["lag_0_month"]
    rows.append(("Soil moisture → inundation, same month", "anomaly", r))
    fig, ax = plt.subplots(figsize=(6.0, 4.4), dpi=200)
    y = np.arange(len(rows))[::-1]
    for yi, (lab, kind, r) in zip(y, rows):
        rho, q = r["spearman_rho"], r["p_value_bh_fdr"]
        colour = (C_RAIN if kind == "raw" else "#2a6f4f") if q < 0.05 else "#9a9a9a"
        ax.plot([0, rho], [yi, yi], color=colour, lw=1.4)
        ax.plot(rho, yi, "o", color=colour, ms=5, mfc=colour if kind == "anomaly" else "white")
        ax.text(0.62, yi, f"q = {q:.3f}" if q >= 0.001 else "q < 0.001", va="center", fontsize=8, color=INK2)
    ax.axvline(0, color=INK2, lw=0.6)
    ax.set_yticks(y, [f"{lab}  ({'raw' if k == 'raw' else 'anomaly'})" for lab, k, _ in rows], fontsize=7.5)
    ax.set_xlim(-0.6, 0.85)
    ax.set_xlabel("Spearman ρ (recommended estimator)", fontsize=8)
    ax.grid(axis="x", color=RULE, lw=0.4)
    fig.subplots_adjust(left=0.5, right=0.97, bottom=0.2, top=0.97)
    _source(fig, "cascade_diagnostics.json. Filled dot: significant after BH correction (q < 0.05), in colour; open or grey: not significant")
    return fig


def _scatter(ax, x, y, xl, yl, colour, rho, q):
    ax.scatter(x, y, s=14, color=colour, alpha=0.8, lw=0)
    ax.axhline(0, color=RULE, lw=0.6)
    ax.axvline(0, color=RULE, lw=0.6)
    ax.set_xlabel(xl, fontsize=8)
    ax.set_ylabel(yl, fontsize=8)
    ax.text(0.03, 0.04, f"ρ = {rho:+.2f}\nq = {q:.2f}", transform=ax.transAxes, va="bottom", fontsize=8)
    ax.grid(color=RULE, lw=0.4)


def fig4_scatter(comp, anom):
    fig, axes = plt.subplots(1, 2, figsize=(6.0, 3.3), dpi=200)
    m = anom[["sar_flood_km2_anom", "estuary_ndti_anom"]].dropna()
    r = [f for f in comp["key_findings"] if "NDTI" in f["relationship"]][0]
    _scatter(axes[0], m["sar_flood_km2_anom"], m["estuary_ndti_anom"], "Radar index anomaly (km²)", "Lagoon NDTI anomaly",
             C_NDTI, r["spearman_rho"], r["p_value"])
    axes[0].set_title("Lagoon turbidity", fontsize=8.5, loc="left")
    m2 = anom[["sar_flood_km2_anom", "dw_flood_km2_anom"]].dropna()
    r2 = [f for f in comp["key_findings"] if "Dynamic World" in f["relationship"]][0]
    _scatter(axes[1], m2["dw_flood_km2_anom"], m2["sar_flood_km2_anom"], "Dynamic World anomaly (km²)", "Radar index anomaly (km²)",
             C_SAR, r2["spearman_rho"], r2["p_value"])
    axes[1].set_title("Optical reference", fontsize=8.5, loc="left")
    fig.subplots_adjust(left=0.13, right=0.98, bottom=0.2, top=0.88, wspace=0.42)
    _source(fig, f"Monthly anomalies from the 2019–2024 Google Earth Engine export; n = {len(m)} and {len(m2)} pairs")
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
    }
    for name, fig in figs.items():
        fig.savefig(OUT / f"{name}.png", dpi=200, facecolor="white")
        plt.close(fig)
        print("wrote", OUT / f"{name}.png")


def load_monthly_series_safe():
    return _compiler().load_monthly_series(DATA / "ogun_monthly_timeseries.csv")


if __name__ == "__main__":
    main()
