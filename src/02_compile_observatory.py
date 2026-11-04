"""
Statistical Coupling & Lag Correlation Audit for Ogun Catchment-to-Coast Observatory
Computes standardized anomalies, Spearman rank correlations, and hydrological lags.
"""
import json
import pandas as pd
from scipy import stats


def evaluate_cascade_coupling(csv_path: str, output_json: str) -> dict:
    df = pd.read_csv(csv_path)
    for drop_col in ["system:index", ".geo"]:
        if drop_col in df.columns:
            df = df.drop(columns=[drop_col])

    df = df.sort_values("year_month").reset_index(drop=True)
    df["estuary_ndti"] = pd.to_numeric(df["estuary_ndti"], errors="coerce").interpolate(method="linear").bfill().ffill()
    df["sar_flood_km2"] = pd.to_numeric(df["sar_flood_km2"], errors="coerce").fillna(0.0)
    df["rain_mm"] = pd.to_numeric(df["rain_mm"], errors="coerce").fillna(0.0)

    df["cal_month"] = pd.to_datetime(df["year_month"]).dt.month
    df["rain_zscore"] = df.groupby("cal_month")["rain_mm"].transform(
        lambda x: (x - x.mean()) / (x.std(ddof=1) + 1e-6)
    ).round(3)

    lags = {}
    for lag in [0, 1, 2]:
        shifted_flood = df["sar_flood_km2"].shift(-lag).dropna()
        valid_rain = df["rain_mm"].iloc[:len(shifted_flood)]
        r_val, p_val = stats.pearsonr(valid_rain, shifted_flood)
        rho_val, _ = stats.spearmanr(valid_rain, shifted_flood)
        lags[f"lag_{lag}_month"] = {
            "pearson_r": round(float(r_val), 3),
            "p_value": float(f"{p_val:.2e}"),
            "spearman_rho": round(float(rho_val), 3)
        }

    r_turb, p_turb = stats.pearsonr(df["sar_flood_km2"], df["estuary_ndti"])
    rho_turb, _ = stats.spearmanr(df["sar_flood_km2"], df["estuary_ndti"])

    summary = {
        "n_months": int(len(df)),
        "period": f"{df['year_month'].min()} to {df['year_month'].max()}",
        "peak_flood_km2": round(float(df["sar_flood_km2"].max()), 1),
        "peak_flood_month": str(df.loc[df["sar_flood_km2"].idxmax(), "year_month"]),
        "rain_to_flood_lags": lags,
        "flood_to_estuary_turbidity": {
            "pearson_r": round(float(r_turb), 3),
            "spearman_rho": round(float(rho_turb), 3),
            "p_value": float(f"{p_turb:.2e}")
        }
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    evaluate_cascade_coupling("docs/data/ogun_monthly_timeseries.csv", "docs/data/cascade_diagnostics.json")
