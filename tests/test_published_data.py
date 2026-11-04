"""The published diagnostics must be exactly what the script produces from the published CSV."""
import json

from conftest import REPO_ROOT

DATA = REPO_ROOT / "docs" / "data"


def test_diagnostics_match_script_output(compiler, tmp_path):
    published = json.loads((DATA / "cascade_diagnostics.json").read_text(encoding="utf-8"))
    regenerated = compiler.evaluate_cascade_coupling(str(DATA / "ogun_monthly_timeseries.csv"),
                                                     str(tmp_path / "diag.json"))
    assert published == json.loads(json.dumps(regenerated)), (
        "docs/data/cascade_diagnostics.json is out of date or was edited by hand. "
        "Re-run: python src/02_compile_observatory.py"
    )


def test_geojson_has_five_units():
    gj = json.loads((DATA / "ogun_subbasins.geojson").read_text(encoding="utf-8"))
    assert sorted(f["properties"]["zone_id"] for f in gj["features"]) == ["Z1", "Z2", "Z3", "Z4", "Z5"]
