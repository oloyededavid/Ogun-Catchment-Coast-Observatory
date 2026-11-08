"""Per-unit summaries for the interactive study-area map.

Reads docs/data/ogun_unit_monthly_timeseries.csv and writes docs/data/unit_summary.json:
for each unit, the mean and number of valid months of each variable over 2019–2024, and the
wet-season (April–October) mean rainfall. Means use only valid months; missing months are not
filled.

    python scripts/make_unit_summary.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
WET = set(range(4, 11))  # April to October
# Radar inundation is not interpreted in the upland units (dry-season radar artefacts); same rule as the explorer.
SAR_UNRELIABLE = {"Z1", "Z2"}
VARS = {"rain_mm": "rain", "shallow_sm_m3m3": "soil", "sar_flood_km2": "sar", "dw_flood_km2": "dw", "estuary_ndti": "ndti"}


def main() -> None:
    rows = list(csv.DictReader((DATA / "ogun_unit_monthly_timeseries.csv").open()))
    acc = defaultdict(lambda: defaultdict(list))
    wet = defaultdict(list)
    for r in rows:
        z = r["zone_id"]
        month = int(r["year_month"][5:])
        for col, key in VARS.items():
            if r[col] not in ("", None):
                acc[z][key].append(float(r[col]))
        if r["rain_mm"] and month in WET:
            wet[z].append(float(r["rain_mm"]))
    out = {"source": "docs/data/ogun_unit_monthly_timeseries.csv", "script": "scripts/make_unit_summary.py",
           "period": "2019-01 to 2024-12", "wet_season": "April to October", "sar_rule": "radar inundation not interpreted for Z1 and Z2 (as in the explorer)", "units": {}}
    for z in sorted(acc):
        u = {}
        for key in VARS.values():
            vals = acc[z][key]
            if key == "sar" and z in SAR_UNRELIABLE:
                u[key] = {"mean": None, "months": 0, "note": "not interpreted in upland units"}
                continue
            u[key] = {"mean": round(sum(vals) / len(vals), 4) if vals else None, "months": len(vals)}
        u["rain_wet_season_mean"] = round(sum(wet[z]) / len(wet[z]), 1) if wet[z] else None
        out["units"][z] = u
    (DATA / "unit_summary.json").write_text(json.dumps(out, indent=1) + "\n")
    print("wrote", DATA / "unit_summary.json")


if __name__ == "__main__":
    main()
