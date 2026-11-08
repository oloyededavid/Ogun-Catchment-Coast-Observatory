"""Bundle the data behind the study page into docs/data/ogun_data.zip.

The bundle holds only files that already exist in docs/data (no new data), so every number on the page can be
checked against it. Run after the pipeline:

    python scripts/make_data_bundle.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
FILES = ["ogun_monthly_timeseries.csv", "ogun_unit_monthly_timeseries.csv", "ogun_subbasins.geojson",
         "unit_summary.json", "cascade_diagnostics.json"]


def main() -> None:
    out = DATA / "ogun_data.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(DATA / name, arcname=name)
    print("wrote", out, "with", len(FILES), "files")


if __name__ == "__main__":
    main()
