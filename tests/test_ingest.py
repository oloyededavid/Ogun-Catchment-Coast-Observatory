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
    assert summary["provenance"]["status"] == "DEMONSTRATION_PREVIEW"


def test_failed_validation_installs_nothing(ingester, tmp_path):
    bad = tmp_path / "bad.csv"
    _monthly().drop(columns=["rain_mm"]).to_csv(bad, index=False)
    out = tmp_path / "out"
    with pytest.raises(ingester.ValidationError):
        ingester.ingest(bad, DATA / "ogun_subbasins.geojson", None, out)
    assert not out.exists()
