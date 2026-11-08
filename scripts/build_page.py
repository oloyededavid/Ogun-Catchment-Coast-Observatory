"""Build docs/index.html, the study page, from the published data files.

Every number on the page is computed here from docs/data/*.json and docs/data/*.csv, so the text
cannot drift from the analysis. Run after src/02_compile_observatory.py, scripts/make_unit_summary.py
and scripts/make_figures.py:

    python scripts/build_page.py
"""
from __future__ import annotations

import calendar
import csv
import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "docs" / "index.html"
RAW_KEYS = {"UNIT_ROWS", "SCHEMATIC"}
UNIT_NAMES = {"Z1": "Upper Ogun Headwaters", "Z2": "Oyan–Ofiki Tributary", "Z3": "Middle Ogun Mainstem",
              "Z4": "Lower Ogun Alluvial Corridor", "Z5": "Northwest Lagos Lagoon Estuary"}


def sign(v: float, d: int = 2) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.{d}f}"


def num(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}".replace("-", "−")


def q(v: float) -> str:
    return "< 0.001" if v < 0.001 else f"{v:.3f}" if v < 0.1 else f"{v:.2f}"


def month_name(ym: str) -> str:
    y, m = ym.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def unit_rows(units: dict, areas: dict) -> str:
    def cell(x, d):
        return "not interpreted" if x is None else f"{x:.{d}f}"
    out = []
    for z in ("Z1", "Z2", "Z3", "Z4", "Z5"):
        u = units[z]
        out.append(
            f"<tr><td class=\"text\"><strong>{z}</strong> {UNIT_NAMES[z]}</td>"
            f"<td>{areas[z]:,.0f}</td>"
            f"<td>{cell(u['rain']['mean'], 0)}</td>"
            f"<td>{cell(u['rain_wet_season_mean'], 0)}</td>"
            f"<td>{cell(u['soil']['mean'], 3)}</td>"
            f"<td>{cell(u['sar']['mean'], 2)}</td>"
            f"<td>{cell(u['dw']['mean'], 1)}</td>"
            f"<td>{cell(u['ndti']['mean'], 3)}</td></tr>")
    return "\n".join(out)


def schematic(units: dict, areas: dict) -> str:
    """Catchment-to-coast chain as an SVG. It shows the order of the units, not a routed water balance."""
    boxes = [("Z1", "Headwaters"), ("Z2", "Oyan–Ofiki"), ("Z3", "Mainstem"), ("Z4", "Alluvial corridor"), ("Z5", "Lagoon zone")]
    w, h, gap, x0, y0 = 150, 104, 36, 12, 16
    width = 5 * w + 4 * gap + 24
    parts = [f'<svg viewBox="0 0 {width} {h + 52}" role="img" aria-labelledby="schem-title schem-desc" class="schematic">',
             '<title id="schem-title">Catchment-to-coast chain of the Ogun units</title>',
             '<desc id="schem-desc">Five units in order: upland headwaters Z1, the Oyan tributary Z2, the mainstem Z3, '
             'the alluvial corridor Z4 and the lagoon zone Z5. Each box gives the unit area and mean monthly rainfall.</desc>']
    for i, (z, label) in enumerate(boxes):
        x = x0 + i * (w + gap)
        u = units[z]
        rain = "rainfall n/a" if u["rain"]["mean"] is None else f"{u['rain']['mean']:.0f} mm per month"
        parts.append(
            f'<g class="unit"><rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="10" class="unit-box u{z[1]}"/>'
            f'<text x="{x + 12}" y="{y0 + 24}" class="u-id">{z}</text>'
            f'<text x="{x + 40}" y="{y0 + 24}" class="u-name">{label}</text>'
            f'<text x="{x + 12}" y="{y0 + 58}" class="u-val">{areas[z]:,.0f} km²</text>'
            f'<text x="{x + 12}" y="{y0 + 80}" class="u-val">{rain}</text></g>')
        if i < len(boxes) - 1:
            ax = x + w + 6
            parts.append(f'<line x1="{ax}" y1="{y0 + h / 2}" x2="{ax + gap - 12}" y2="{y0 + h / 2}" class="flow"/>')
    parts.append(f'<text x="12" y="{h + 42}" class="axis-note">Order of the units only. The arrows show how the catchment '
                 f'drains to the lagoon; they are not measured water transfers.</text>')
    parts.append("</svg>")
    return "".join(parts)


def values() -> dict[str, str]:
    d = json.loads((DATA / "cascade_diagnostics.json").read_text())
    g = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    rows = list(csv.DictReader((DATA / "ogun_monthly_timeseries.csv").open()))
    units = json.loads((DATA / "unit_summary.json").read_text())["units"]
    areas = {f["properties"]["zone_id"]: f["properties"]["area_km2"] for f in g["features"]}
    catch = sum(areas[z] for z in ("Z1", "Z2", "Z3", "Z4"))
    sar = [float(r["sar_flood_km2"]) for r in rows if r["sar_flood_km2"]]
    dw = [float(r["dw_flood_km2"]) for r in rows if r["dw_flood_km2"]]
    seas = d["rain_to_sar_inundation_lags_seasonal"]
    deseas = d["rain_to_sar_inundation_lags_deseasonalized"]
    sm_seas = d["soil_moisture_to_sar_inundation_lags_seasonal"]
    sm_deseas = d["soil_moisture_to_sar_inundation_lags_deseasonalized"]
    ctl = d["rain_to_sar_inundation_controlling_for_oyan_reservoir"]["deseasonalized"]["lag_0_month"]
    rb = d["robustness"]["rain_to_sar_lag_0_deseasonalized"]
    rb_w = rb["without_most_influential_month"]
    cov = d["coverage"]
    fk = {f["relationship"]: f for f in d["key_findings"]}
    f_rain = fk["Rain -> floodplain SAR inundation (same month, deseasonalized)"]
    f_rain1 = fk["Rain -> floodplain SAR inundation (1-month lag, deseasonalized)"]
    f_sm = fk["Soil moisture -> floodplain SAR inundation (same month, deseasonalized)"]
    f_ndti = fk["Floodplain SAR inundation -> estuary NDTI (deseasonalized)"]
    f_dw = fk["SAR inundation vs Dynamic World flooding (deseasonalized)"]
    dw_seas = d["sar_validation_against_dynamic_world"]["seasonal"]
    def peak(col):
        acc: dict[int, list[float]] = {}
        for r in rows:
            if r[col]:
                acc.setdefault(int(r["year_month"][5:]), []).append(float(r[col]))
        means = {m: sum(v) / len(v) for m, v in acc.items()}
        return calendar.month_name[max(means, key=means.get)]
    sig_seasonal = [(lag, seas[lag]) for lag in ("lag_0_month", "lag_1_month", "lag_2_month") if seas[lag]["p_value_bh_fdr"] < 0.05]
    v = {
        "CATCH": f"{catch:,.0f}",
        "NMONTHS": str(cov["n_total_months"]),
        "NDW": str(cov["valid_dynamic_world_months"]),
        "NNDTI": str(cov["valid_ndti_months"]),
        "NNDTIMISS": str(cov["missing_ndti_months"]),
        "SAR_MAX": num(max(sar)),
        "DW_MAX": f"{max(dw):.0f}",
        "PEAK_MONTH": month_name(d["extremes"]["peak_sar_inundation_month"]),
        "SEAS2_RHO": sign(seas["lag_2_month"]["spearman_rho"]),
        "SEAS2_Q": q(seas["lag_2_month"]["p_value_bh_fdr"]),
        "SEAS1_RHO": sign(seas["lag_1_month"]["spearman_rho"]),
        "SEAS1_Q": q(seas["lag_1_month"]["p_value_bh_fdr"]),
        "SM_RHO": sign(sm_seas["lag_0_month"]["spearman_rho"]),
        "SM_Q": q(sm_seas["lag_0_month"]["p_value_bh_fdr"]),
        "RAIN_RHO": sign(f_rain["spearman_rho"]),
        "RAIN_Q": q(f_rain["p_value"]),
        "RAIN1_RHO": sign(f_rain1["spearman_rho"]),
        "RAIN1_Q": q(f_rain1["p_value"]),
        "RAIN_PEARSON": sign(f_rain["pearson_r"]),
        "RAIN_PEARSON_LO": sign(deseas["lag_0_month"]["pearson_ci95"][0]),
        "RAIN_PEARSON_HI": sign(deseas["lag_0_month"]["pearson_ci95"][1]),
        "ROB_R": sign(rb_w["pearson_r"]),
        "ROB_LO": sign(rb_w["pearson_ci95"][0]),
        "ROB_HI": sign(rb_w["pearson_ci95"][1]),
        "SM_ANOM_RHO": sign(f_sm["spearman_rho"]),
        "SM_ANOM_Q": q(f_sm["p_value"]),
        "NDTI_RHO": sign(f_ndti["spearman_rho"]),
        "NDTI_Q": q(f_ndti["p_value"]),
        "DW_SEAS_RHO": sign(dw_seas["spearman_rho"]),
        "DW_ANOM_RHO": sign(f_dw["spearman_rho"]),
        "DW_ANOM_Q": q(f_dw["p_value"]),
        "CTL_RHO": sign(ctl["spearman_rho"]),
        "BASE_RHO": sign(deseas["lag_0_month"]["spearman_rho"]),
        "NSIG_ANOM": str(sum(1 for f in d["key_findings"] if f["significant"])),
        "NFAM": str(len(d["key_findings"])),
        "SEAS_PEAK_RAIN": peak("rain_mm"),
        "SEAS_PEAK_SOIL": peak("shallow_sm_m3m3"),
        "SEAS_PEAK_SAR": peak("sar_flood_km2"),
        "SIG_SEAS_TEXT": "; ".join(f"{'same month' if l == 'lag_0_month' else 'one month later' if l == 'lag_1_month' else 'two months later'} (ρ = {sign(r['spearman_rho'])}, q = {q(r['p_value_bh_fdr'])})" for l, r in sig_seasonal) or "none",
        "UNIT_ROWS": unit_rows(units, areas),
        "SCHEMATIC": schematic(units, areas),
        "PRINT_DATE": date.today().strftime("%-d %B %Y"),
        "ISO_DATE": date.today().isoformat(),
    }
    if v["NSIG_ANOM"] != "0":
        raise SystemExit("A headline relationship is now significant: the abstract and section 4.3 wording must be revised first.")
    return v


TEMPLATE_PATH = Path(__file__).with_name("page_template.html")


def _figure_sizes(text: str) -> str:
    """Give every figure image its real pixel size, so the browser reserves the right space."""
    import re
    from PIL import Image

    def fix(m):
        path = ROOT / "docs" / m.group(1)
        with Image.open(path) as im:
            w, h = im.size
        return f'<img src="{m.group(1)}" width="{w}" height="{h}"'
    return re.sub(r'<img src="(assets/figures/[^"]+)" width="\d+" height="\d+"', fix, text)


def main() -> None:
    v = values()
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    text = _figure_sizes(text)
    for k, val in v.items():
        text = text.replace("{" + k + "}", val if k in RAW_KEYS else html.escape(val, quote=False))
    left = sorted(set(__import__("re").findall(r"\{[A-Z][A-Z0-9_]+\}", text)))
    assert not left, left
    OUT.write_text(text, encoding="utf-8")
    print("wrote", OUT, "| values filled:", len(v))


if __name__ == "__main__":
    main()
