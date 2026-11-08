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
RAW_KEYS = {"UNIT_ROWS", "SCHEMATIC", "SEASON_ROWS"}
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
    """Table 2: the five metrics that matter most for the study (area, rainfall, soil moisture, radar, Dynamic World)."""
    def cell(x, d):
        return "not interpreted" if x is None else f"{x:.{d}f}"
    out = []
    for z in ("Z1", "Z2", "Z3", "Z4", "Z5"):
        u = units[z]
        out.append(
            f"<tr><th scope=\"row\" class=\"text\"><strong>{z}</strong> {UNIT_NAMES[z]}</th>"
            f"<td>{areas[z]:,.0f}</td>"
            f"<td>{cell(u['rain']['mean'], 0)}</td>"
            f"<td>{cell(u['soil']['mean'], 2)}</td>"
            f"<td>{cell(u['sar']['mean'], 2)}</td>"
            f"<td>{cell(u['dw']['mean'], 1)}</td></tr>")
    return "\n".join(out)


def season_rows(units: dict) -> str:
    """Wet season (April to October) against dry season means for the units with valid data."""
    out = []
    for z in ("Z1", "Z2", "Z3", "Z4", "Z5"):
        se = units[z]["seasonal"]
        def pair(key, d):
            x = se.get(key)
            if not x:
                return "not interpreted", "not interpreted"
            f = (lambda v: "no data" if v is None else f"{v:.{d}f}")
            return f(x["wet_mean"]), f(x["dry_mean"])
        sw, sd = pair("soil", 2)
        dw_w, dw_d = pair("dw", 1)
        out.append(f"<tr><th scope=\"row\" class=\"text\"><strong>{z}</strong> {UNIT_NAMES[z]}</th>"
                   f"<td>{sw}</td><td>{sd}</td><td>{dw_w}</td><td>{dw_d}</td></tr>")
    return "\n".join(out)


def schematic(units: dict, areas: dict) -> str:
    """Catchment-to-coast chain as HTML, so it wraps on a phone instead of shrinking."""
    labels = {"Z1": "Headwaters", "Z2": "Oyan–Ofiki", "Z3": "Mainstem", "Z4": "Alluvial corridor", "Z5": "Lagoon zone"}
    items = []
    for z in ("Z1", "Z2", "Z3", "Z4", "Z5"):
        u = units[z]
        rain = "rainfall not interpreted" if u["rain"]["mean"] is None else f"{u['rain']['mean']:.0f} mm per month"
        items.append(f'<li class="chain-unit u{z[1]}"><span class="u-id">{z}</span>'
                     f'<span class="u-name">{labels[z]}</span>'
                     f'<span class="u-val">{areas[z]:,.0f} km²</span>'
                     f'<span class="u-val">{rain}</span></li>')
    return ('<ol class="chain" aria-label="Catchment-to-coast chain, from headwaters Z1 to lagoon Z5">'
            + "".join(items) + '</ol>'
            + '<p class="chain-note">Order of the units only. The chain shows how the catchment drains to the lagoon; '
              'it does not show measured water transfers.</p>')


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
        "SEASON_ROWS": season_rows(units),
        "SCHEMATIC": schematic(units, areas),
        "PRINT_DATE": date.today().strftime("%-d %B %Y"),
        "ISO_DATE": date.today().isoformat(),
    }
    se = {z: units[z]["seasonal"] for z in ("Z1", "Z2")}
    v.update({
        "Z2_SOIL_WET": f"{se['Z2']['soil']['wet_mean']:.2f}", "Z2_SOIL_DRY": f"{se['Z2']['soil']['dry_mean']:.2f}",
        "Z2_DW_WET": f"{se['Z2']['dw']['wet_mean']:.1f}", "Z2_DW_DRY": f"{se['Z2']['dw']['dry_mean']:.1f}",
        "Z1_DW_DRY": f"{se['Z1']['dw']['dry_mean']:.1f}", "Z1_DW_WET": f"{se['Z1']['dw']['wet_mean']:.1f}",
    })
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
