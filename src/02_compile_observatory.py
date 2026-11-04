
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def _fisher_z_ci(r: float, n: int, alpha: float = 0.05) -> list[float | None]:
    """Compute two-sided 95% confidence interval for Pearson r using Fisher z-transform."""
    if n <= 4 or np.isnan(r) or abs(r) >= 1.0:
        return [None, None]
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(n - 3)
    z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
    lo, hi = np.tanh(z - z_crit * se), np.tanh(z + z_crit * se)
    return [round(float(lo), 3), round(float(hi), 3)]


def _lag1_autocorr(series: pd.Series) -> float:
    """Compute lag-1 serial autocorrelation on contiguous non-null pairs."""
    s = series.dropna()
    if len(s) < 6:
        return 0.0
    r1, _ = stats.pearsonr(s.iloc[:-1], s.iloc[1:])
    return float(r1) if not np.isnan(r1) else 0.0


def _effective_n(x: pd.Series, y: pd.Series, n_raw: int) -> float:
    """
    Bretherton et al. (1999) effective sample size adjustment for serially
    correlated hydro-climatic time series: n_eff = n * (1 - r1x*r1y) / (1 + r1x*r1y).
    """
    r1x = _lag1_autocorr(x)
    r1y = _lag1_autocorr(y)
    denom = 1.0 + (r1x * r1y)
    if denom <= 0:
        return float(n_raw)
    n_eff = n_raw * (1.0 - (r1x * r1y)) / denom
    return max(4.0, min(float(n_raw), float(n_eff)))


def _benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Adjust p-values for multiple lag comparisons via Benjamini-Hochberg FDR."""
    m = len(p_values)
    if m == 0:
        return []
    order = np.argsort(p_values)
    ranked = np.empty(m, dtype=float)
    prev = 1.0
    for i in range(m - 1, -1, -1):
        idx = order[i]
        adj = min(prev, p_values[idx] * m / (i + 1))
        ranked[idx] = adj
        prev = adj
    return [round(float(v), 6) for v in ranked]


def _bivariate_test(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    """Run pairwise complete-case bivariate correlation with autocorrelation adjustment."""
    pair = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    n = len(pair)
    if n < 8:
        return {
            "n_pairs": int(n),
            "status": "INSUFFICIENT_OBSERVATIONS",
            "pearson_r": None,
            "pearson_ci95": [None, None],
            "p_value_raw": None,
            "p_value_autocorr_adj": None,
            "n_effective": None,
            "spearman_rho": None,
            "spearman_p_raw": None,
            "recommended_estimator": None
        }

    _, shapiro_px = stats.shapiro(pair["x"])
    _, shapiro_py = stats.shapiro(pair["y"])
    prefer_spearman = bool(shapiro_px < 0.05 or shapiro_py < 0.05)

    r_val, p_raw = stats.pearsonr(pair["x"], pair["y"])
    rho_val, rho_p = stats.spearmanr(pair["x"], pair["y"])

    n_eff = _effective_n(pair["x"], pair["y"], n)
    df_eff = max(2.0, n_eff - 2.0)
    t_eff = abs(r_val) * np.sqrt(df_eff / max(1e-12, 1.0 - r_val**2))
    p_adj_autocorr = float(2.0 * (1.0 - stats.t.cdf(t_eff, df=df_eff)))

    return {
        "n_pairs": int(n),
        "n_effective": round(float(n_eff), 1),
        "shapiro_p_x": round(float(shapiro_px), 4),
        "shapiro_p_y": round(float(shapiro_py), 4),
        "recommended_estimator": "spearman_rho" if prefer_spearman else "pearson_r",
        "pearson_r": round(float(r_val), 3),
        "pearson_ci95": _fisher_z_ci(float(r_val), int(round(n_eff))),
        "p_value_raw": round(float(p_raw), 6),
        "p_value_autocorr_adj": round(float(p_adj_autocorr), 6),
        "spearman_rho": round(float(rho_val), 3),
        "spearman_p_raw": round(float(rho_p), 6),
        "status": "VALID"
    }


def _detect_synthetic_template(df: pd.DataFrame) -> bool:
    """Detect whether the loaded CSV is a demonstration preview rather than a verified GEE export."""
    if "data_status" in df.columns:
        statuses = set(df["data_status"].dropna().astype(str).unique())
        if "VERIFIED_GEE_EXPORT" not in statuses:
            return True
    df_check = df.copy()
    df_check["yr"] = df_check["year_month"].str.slice(0, 4)
    df_check["mo"] = df_check["year_month"].str.slice(5, 7)
    piv = df_check.pivot(index="mo", columns="yr", values="rain_mm").dropna(axis=1)
    if piv.shape[1] >= 2:
        c = piv.corr().values
        off_diag = c[np.triu_indices_from(c, k=1)]
        if len(off_diag) > 0 and np.nanmean(off_diag) > 0.998:
            return True
    return False


def evaluate_cascade_coupling(csv_path: str, output_json: str) -> dict[str, Any]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Input time-series CSV not found: {csv_path}")

    df = pd.read_csv(path)
    for drop_col in ["system:index", ".geo"]:
        if drop_col in df.columns:
            df = df.drop(columns=[drop_col])

    df = df.sort_values("year_month").reset_index(drop=True)
    for col in ["rain_mm", "shallow_sm_m3m3", "sar_flood_km2", "estuary_ndti"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    is_demo = _detect_synthetic_template(df)

    df["cal_month"] = pd.to_datetime(df["year_month"], format="%Y-%m").dt.month
    for col in ["rain_mm", "sar_flood_km2", "estuary_ndti"]:
        clim_mean = df.groupby("cal_month")[col].transform("mean")
        clim_std = df.groupby("cal_month")[col].transform(lambda s: s.std(ddof=1))
        df[f"{col}_anom"] = df[col] - clim_mean
        df[f"{col}_zscore"] = np.where(clim_std > 1e-6, (df[col] - clim_mean) / clim_std, np.nan)

    raw_lags: dict[str, Any] = {}
    anom_lags: dict[str, Any] = {}
    raw_p_list: list[float] = []
    anom_p_list: list[float] = []
    lag_keys = [0, 1, 2]

    for lag in lag_keys:
        flood_future = df["sar_flood_km2"].shift(-lag) if lag > 0 else df["sar_flood_km2"]
        flood_anom_future = df["sar_flood_km2_anom"].shift(-lag) if lag > 0 else df["sar_flood_km2_anom"]

        res_raw = _bivariate_test(df["rain_mm"], flood_future)
        res_anom = _bivariate_test(df["rain_mm_anom"], flood_anom_future)

        raw_lags[f"lag_{lag}_month"] = res_raw
        anom_lags[f"lag_{lag}_month"] = res_anom

        raw_p_list.append(res_raw["p_value_autocorr_adj"] if res_raw["p_value_autocorr_adj"] is not None else 1.0)
        anom_p_list.append(res_anom["p_value_autocorr_adj"] if res_anom["p_value_autocorr_adj"] is not None else 1.0)

    bh_raw = _benjamini_hochberg(raw_p_list)
    bh_anom = _benjamini_hochberg(anom_p_list)
    for idx, lag in enumerate(lag_keys):
        raw_lags[f"lag_{lag}_month"]["p_value_bh_fdr"] = bh_raw[idx]
        anom_lags[f"lag_{lag}_month"]["p_value_bh_fdr"] = bh_anom[idx]

    turb_raw = _bivariate_test(df["sar_flood_km2"], df["estuary_ndti"])
    turb_anom = _bivariate_test(df["sar_flood_km2_anom"], df["estuary_ndti_anom"])

    valid_flood = df["sar_flood_km2"].dropna()
    peak_flood_val = round(float(valid_flood.max()), 1) if len(valid_flood) > 0 else None
    peak_flood_ym = str(df.loc[valid_flood.idxmax(), "year_month"]) if len(valid_flood) > 0 else None

    summary = {
        "provenance": {
            "status": "DEMONSTRATION_PREVIEW" if is_demo else "VERIFIED_GEE_EXPORT",
            "is_demonstration_data": bool(is_demo),
            "warning": (
                "Current CSV contains demonstration preview values awaiting overwrite by authenticated "
                "Google Earth Engine export (gee/01_extract_real_ogun_data.js). Do not cite statistical "
                "metrics below as empirical research findings until provenance.status == VERIFIED_GEE_EXPORT."
                if is_demo else
                "Verified Google Earth Engine multi-sensor export."
            )
        },
        "coverage": {
            "n_total_months": int(len(df)),
            "period_start": str(df["year_month"].min()),
            "period_end": str(df["year_month"].max()),
            "valid_rain_months": int(df["rain_mm"].notna().sum()),
            "valid_sm_months": int(df["shallow_sm_m3m3"].notna().sum()),
            "valid_sar_months": int(df["sar_flood_km2"].notna().sum()),
            "valid_ndti_months": int(df["estuary_ndti"].notna().sum()),
            "missing_ndti_months": int(df["estuary_ndti"].isna().sum())
        },
        "extremes": {
            "peak_sar_inundation_km2": peak_flood_val,
            "peak_sar_inundation_month": peak_flood_ym
        },
        "rain_to_sar_inundation_lags_seasonal": raw_lags,
        "rain_to_sar_inundation_lags_deseasonalized": anom_lags,
        "sar_inundation_to_estuary_ndti": {
            "seasonal": turb_raw,
            "deseasonalized": turb_anom
        },
        "methodological_notes": [
            "Missing observations (e.g., cloud-obscured Sentinel-2 monsoon months) are preserved as NaN and excluded pairwise.",
            "Monthly resolution (Delta t = 1 month) is coarser than typical upland kinematic wave travel times; lag-0 and lag-1 associations reflect seasonal soil-wetting and floodplain storage memory rather than direct flood-wave routing.",
            "Sentinel-2 NDTI is an uncalibrated spectral turbidity indicator over open water (MNDWI > 0, JRC >= 50%), not gravimetric TSS (mg/L) or NTU."
        ]
    }

    out_path = Path(output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    evaluate_cascade_coupling(
        "docs/data/ogun_monthly_timeseries.csv",
        "docs/data/cascade_diagnostics.json"
    )
