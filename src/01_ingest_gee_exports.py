"""Validate Google Earth Engine exports and install them into docs/data/.

Usage (after downloading the exports from Google Drive):

    python src/01_ingest_gee_exports.py \
        --monthly ~/Downloads/ogun_monthly_timeseries.csv \
        --units ~/Downloads/ogun_subbasins.geojson \
        --unit-monthly ~/Downloads/ogun_unit_monthly_timeseries.csv

The script refuses to install files that fail validation, then re-runs
src/02_compile_observatory.py so docs/data/cascade_diagnostics.json always
matches the installed time series.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "docs" / "data"

MONTHLY_REQUIRED = ["year_month", "rain_mm", "shallow_sm_m3m3", "sar_flood_km2", "estuary_ndti",
                    "chirps_pentads", "s1_scenes", "s2_clear_scenes", "s2_water_px", "data_status"]
MONTHLY_OPTIONAL = ["sar_flood_max_km2", "dw_flood_km2", "dw_images", "oyan_reservoir_km2", "oyan_release_mcm",
                    "export_utc", "script_version"]
UNIT_MONTHLY_REQUIRED = ["zone_id", "year_month", "rain_mm", "shallow_sm_m3m3", "sar_flood_km2", "estuary_ndti"]
UNIT_PROPS_REQUIRED = ["zone_id", "order", "zone_name", "area_km2"]
EXPECTED_ZONES = ["Z1", "Z2", "Z3", "Z4", "Z5"]

# Physically plausible ranges; values outside them indicate an export problem.
RANGES = {
    "rain_mm": (0.0, 1500.0),
    "shallow_sm_m3m3": (0.0, 1.0),
    "sar_flood_km2": (0.0, 25000.0),
    "sar_flood_max_km2": (0.0, 25000.0),
    "dw_flood_km2": (0.0, 25000.0),
    "oyan_reservoir_km2": (0.0, 500.0),
    "oyan_release_mcm": (0.0, 5000.0),
    "estuary_ndti": (-1.0, 1.0),
}


class ValidationError(Exception):
    pass


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in ["system:index", ".geo"] if c in df.columns])


def _check_ranges(df: pd.DataFrame, label: str) -> list[str]:
    errors = []
    for col, (lo, hi) in RANGES.items():
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        bad = df.loc[vals.notna() & ((vals < lo) | (vals > hi)), "year_month"].tolist()
        if bad:
            errors.append(f"{label}: {col} outside [{lo}, {hi}] in {bad[:5]}")
    return errors


def _check_months(months: pd.Series, label: str) -> list[str]:
    errors = []
    parsed = pd.to_datetime(months, format="%Y-%m", errors="coerce")
    if parsed.isna().any():
        errors.append(f"{label}: malformed year_month values {months[parsed.isna()].tolist()[:5]}")
        return errors
    if months.duplicated().any():
        errors.append(f"{label}: duplicate months {months[months.duplicated()].tolist()[:5]}")
    expected = pd.period_range(parsed.min(), parsed.max(), freq="M").strftime("%Y-%m")
    missing = sorted(set(expected) - set(months))
    if missing:
        errors.append(f"{label}: missing months {missing[:5]}")
    return errors


def validate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    df = _clean(df)
    errors = [f"monthly: missing column '{c}'" for c in MONTHLY_REQUIRED if c not in df.columns]
    if errors:
        raise ValidationError("\n".join(errors))
    df["year_month"] = df["year_month"].astype(str).str.strip()
    errors += _check_months(df["year_month"], "monthly")
    errors += _check_ranges(df, "monthly")
    if errors:
        raise ValidationError("\n".join(errors))
    cols = MONTHLY_REQUIRED + [c for c in MONTHLY_OPTIONAL if c in df.columns]
    return df.sort_values("year_month")[cols].reset_index(drop=True)


def merge_dam_releases(monthly: pd.DataFrame, releases: pd.DataFrame) -> pd.DataFrame:
    """Add Oyan Dam release records (columns: year_month, oyan_release_mcm) to the monthly series."""
    missing = [c for c in ["year_month", "oyan_release_mcm"] if c not in releases.columns]
    if missing:
        raise ValidationError(f"dam-releases: missing columns {missing}")
    releases = releases[["year_month", "oyan_release_mcm"]].copy()
    releases["year_month"] = releases["year_month"].astype(str).str.strip()
    if releases["year_month"].duplicated().any():
        raise ValidationError("dam-releases: duplicate months")
    unknown = sorted(set(releases["year_month"]) - set(monthly["year_month"]))
    if unknown:
        raise ValidationError(f"dam-releases: months outside the study period {unknown[:5]}")
    merged = monthly.drop(columns=["oyan_release_mcm"], errors="ignore").merge(releases, on="year_month", how="left")
    errors = _check_ranges(merged, "dam-releases")
    if errors:
        raise ValidationError("\n".join(errors))
    return merged


def validate_unit_monthly(df: pd.DataFrame) -> pd.DataFrame:
    df = _clean(df)
    errors = [f"unit-monthly: missing column '{c}'" for c in UNIT_MONTHLY_REQUIRED if c not in df.columns]
    if errors:
        raise ValidationError("\n".join(errors))
    df["year_month"] = df["year_month"].astype(str).str.strip()
    zones = sorted(df["zone_id"].astype(str).unique())
    if zones != EXPECTED_ZONES:
        errors.append(f"unit-monthly: expected zones {EXPECTED_ZONES}, found {zones}")
    for zone, grp in df.groupby("zone_id"):
        errors += _check_months(grp["year_month"], f"unit-monthly {zone}")
    errors += _check_ranges(df, "unit-monthly")
    if errors:
        raise ValidationError("\n".join(errors))
    return df.sort_values(["zone_id", "year_month"]).reset_index(drop=True)


def validate_units(geojson: dict) -> dict:
    errors = []
    feats = geojson.get("features") or []
    ids = sorted(str(f.get("properties", {}).get("zone_id")) for f in feats)
    if ids != EXPECTED_ZONES:
        errors.append(f"units: expected zone_ids {EXPECTED_ZONES}, found {ids}")
    for f in feats:
        props = f.get("properties", {})
        zid = props.get("zone_id")
        errors += [f"units {zid}: missing property '{c}'" for c in UNIT_PROPS_REQUIRED if c not in props]
        geom = f.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            errors.append(f"units {zid}: geometry must be Polygon or MultiPolygon, got {geom.get('type')}")
        area = props.get("area_km2")
        if isinstance(area, (int, float)) and not np.isfinite(area):
            errors.append(f"units {zid}: area_km2 is not finite")
    if errors:
        raise ValidationError("\n".join(errors))
    return geojson


def validate_context_layer(geojson: dict, label: str, allowed: tuple[str, ...]) -> dict:
    """Check an optional map context layer (river network or reservoir outline)."""
    feats = geojson.get("features") if isinstance(geojson, dict) else None
    if not feats:
        raise ValidationError(f"{label}: no features")
    bad = sorted({(f.get("geometry") or {}).get("type") for f in feats} - set(allowed))
    if bad:
        raise ValidationError(f"{label}: geometry must be {' or '.join(allowed)}, found {bad}")
    for f in feats:
        f.pop("id", None)
    return {"type": "FeatureCollection", "features": feats}


def _load_compiler():
    spec = importlib.util.spec_from_file_location("compile_observatory", REPO_ROOT / "src" / "02_compile_observatory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ingest(monthly: Path, units: Path | None, unit_monthly: Path | None, out_dir: Path = DATA_DIR,
           dam_releases: Path | None = None, rivers: Path | None = None, reservoir: Path | None = None) -> dict:
    monthly_df = validate_monthly(pd.read_csv(monthly))
    if dam_releases:
        monthly_df = merge_dam_releases(monthly_df, pd.read_csv(dam_releases))
    units_gj = validate_units(json.loads(Path(units).read_text(encoding="utf-8"))) if units else None
    unit_df = validate_unit_monthly(pd.read_csv(unit_monthly)) if unit_monthly else None
    rivers_gj = validate_context_layer(json.loads(Path(rivers).read_text(encoding="utf-8")), "rivers",
                                       ("LineString", "MultiLineString")) if rivers else None
    reservoir_gj = validate_context_layer(json.loads(Path(reservoir).read_text(encoding="utf-8")), "reservoir",
                                          ("Polygon", "MultiPolygon")) if reservoir else None

    out_dir.mkdir(parents=True, exist_ok=True)
    monthly_out = out_dir / "ogun_monthly_timeseries.csv"
    monthly_df.to_csv(monthly_out, index=False)
    if units_gj is not None:
        (out_dir / "ogun_subbasins.geojson").write_text(json.dumps(units_gj, indent=2) + "\n", encoding="utf-8")
    if rivers_gj is not None:
        (out_dir / "ogun_rivers.geojson").write_text(json.dumps(rivers_gj) + "\n", encoding="utf-8")
    if reservoir_gj is not None:
        (out_dir / "oyan_reservoir.geojson").write_text(json.dumps(reservoir_gj) + "\n", encoding="utf-8")
    if unit_df is not None:
        unit_df.to_csv(out_dir / "ogun_unit_monthly_timeseries.csv", index=False)

    return _load_compiler().evaluate_cascade_coupling(str(monthly_out), str(out_dir / "cascade_diagnostics.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monthly", type=Path, required=True, help="ogun_monthly_timeseries.csv from Earth Engine")
    parser.add_argument("--units", type=Path, help="ogun_subbasins.geojson from Earth Engine (omit to keep the installed one)")
    parser.add_argument("--unit-monthly", type=Path, help="ogun_unit_monthly_timeseries.csv from Earth Engine")
    parser.add_argument("--dam-releases", type=Path,
                        help="optional CSV of Oyan Dam releases with columns year_month, oyan_release_mcm")
    parser.add_argument("--rivers", type=Path, help="optional ogun_rivers.geojson (map context layer)")
    parser.add_argument("--reservoir", type=Path, help="optional oyan_reservoir.geojson (map context layer)")
    parser.add_argument("--out", type=Path, default=DATA_DIR, help="output directory (default: docs/data)")
    args = parser.parse_args(argv)
    try:
        summary = ingest(args.monthly, args.units, args.unit_monthly, args.out, args.dam_releases,
                         args.rivers, args.reservoir)
    except ValidationError as exc:
        print(f"Validation failed; nothing was installed.\n{exc}", file=sys.stderr)
        return 1
    status = summary["provenance"]["status"]
    print(f"Installed exports into {args.out}. Provenance status: {status}")
    if summary["provenance"]["is_demonstration_data"]:
        print("WARNING: the time series still looks like demonstration data.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
