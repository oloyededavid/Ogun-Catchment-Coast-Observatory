import json

import pandas as pd
import pytest

from conftest import REPO_ROOT

DATA = REPO_ROOT / "docs" / "data"


def _monthly():
    return pd.read_csv(DATA / "ogun_monthly_timeseries.csv")


def test_current_monthly_csv_validates(ingester):
    out = ingester.validate_monthly(_monthly())
    assert len(out) == 72


def test_gee_export_columns_are_stripped(ingester):
    df = _monthly()
    df["system:index"] = range(len(df))
    df[".geo"] = '{"type":"MultiPoint","coordinates":[]}'
    out = ingester.validate_monthly(df)
    assert "system:index" not in out.columns and ".geo" not in out.columns


def test_missing_month_rejected(ingester):
    df = _monthly().drop(index=10)
    with pytest.raises(ingester.ValidationError, match="missing months"):
        ingester.validate_monthly(df)


def test_out_of_range_value_rejected(ingester):
    df = _monthly()
    df.loc[3, "shallow_sm_m3m3"] = 4.2
    with pytest.raises(ingester.ValidationError, match="shallow_sm_m3m3"):
        ingester.validate_monthly(df)


def test_units_require_all_zones(ingester):
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text(encoding="utf-8"))
    gj["features"] = gj["features"][:4]
    with pytest.raises(ingester.ValidationError, match="expected zone_ids"):
        ingester.validate_units(gj)


def test_ingest_writes_files_and_diagnostics(ingester, tmp_path):
    summary = ingester.ingest(DATA / "ogun_monthly_timeseries.csv", DATA / "ogun_subbasins.geojson", None, tmp_path)
    assert (tmp_path / "ogun_monthly_timeseries.csv").exists()
    assert (tmp_path / "cascade_diagnostics.json").exists()
    published = json.loads((DATA / "cascade_diagnostics.json").read_text(encoding="utf-8"))
    assert summary["provenance"]["status"] == published["provenance"]["status"]


def test_failed_validation_installs_nothing(ingester, tmp_path):
    bad = tmp_path / "bad.csv"
    _monthly().drop(columns=["rain_mm"]).to_csv(bad, index=False)
    out = tmp_path / "out"
    with pytest.raises(ingester.ValidationError):
        ingester.ingest(bad, DATA / "ogun_subbasins.geojson", None, out)
    assert not out.exists()


def test_dam_releases_merged(ingester):
    monthly = ingester.validate_monthly(_monthly())
    rel = pd.DataFrame({"year_month": monthly["year_month"][:12], "oyan_release_mcm": range(12)})
    merged = ingester.merge_dam_releases(monthly, rel)
    assert merged["oyan_release_mcm"].notna().sum() == 12


def test_dam_releases_outside_period_rejected(ingester):
    monthly = ingester.validate_monthly(_monthly())
    rel = pd.DataFrame({"year_month": ["1999-01"], "oyan_release_mcm": [5.0]})
    with pytest.raises(ingester.ValidationError, match="outside the study period"):
        ingester.merge_dam_releases(monthly, rel)


def test_context_layers_validated(ingester):
    line = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ORD_STRA": 4},
            "geometry": {"type": "LineString", "coordinates": [[3.3, 7.0], [3.4, 6.9]]}}]}
    assert ingester.validate_context_layer(line, "rivers", ("LineString", "MultiLineString"))["features"]
    with pytest.raises(ingester.ValidationError, match="geometry must be"):
        ingester.validate_context_layer(line, "reservoir", ("Polygon", "MultiPolygon"))
