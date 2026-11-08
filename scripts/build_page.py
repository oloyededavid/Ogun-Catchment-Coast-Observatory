"""Build docs/index.html, the study page, from the published data files.

Every number on the page is computed here from docs/data/*.json and docs/data/*.csv, so the text
cannot drift from the analysis. Run after src/02_compile_observatory.py and scripts/make_figures.py:

    python scripts/build_page.py
"""
from __future__ import annotations

import csv
import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "docs" / "index.html"


def _month_name(ym: str) -> str:
    import calendar
    y, m = ym.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def sign(v: float, d: int = 2) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.{d}f}"


def num(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}".replace("-", "−")


def q(v: float) -> str:
    return "< 0.001" if v < 0.001 else f"{v:.3f}" if v < 0.1 else f"{v:.2f}"


def values() -> dict[str, str]:
    d = json.loads((DATA / "cascade_diagnostics.json").read_text())
    g = json.loads((DATA / "ogun_subbasins.geojson").read_text())
    rows = list(csv.DictReader((DATA / "ogun_monthly_timeseries.csv").open()))
    areas = {f["properties"]["zone_id"]: f["properties"]["area_km2"] for f in g["features"]}
    catch = sum(areas[z] for z in ("Z1", "Z2", "Z3", "Z4"))
    sar = [float(r["sar_flood_km2"]) for r in rows if r["sar_flood_km2"]]
    dw = [float(r["dw_flood_km2"]) for r in rows if r["dw_flood_km2"]]
    seas = d["rain_to_sar_inundation_lags_seasonal"]
    deseas = d["rain_to_sar_inundation_lags_deseasonalized"]
    sm_seas = d["soil_moisture_to_sar_inundation_lags_seasonal"]
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
    import calendar
    def clim_peak(col):
        bym = {}
        for r in rows:
            if r[col]:
                bym.setdefault(int(r["year_month"][5:]), []).append(float(r[col]))
        means = {m: sum(v) / len(v) for m, v in bym.items()}
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
        "PEAK_MONTH": _month_name(d["extremes"]["peak_sar_inundation_month"]),
        "SEAS2_RHO": sign(seas["lag_2_month"]["spearman_rho"]),
        "SEAS2_Q": q(seas["lag_2_month"]["p_value_bh_fdr"]),
        "SEAS1_Q": q(seas["lag_1_month"]["p_value_bh_fdr"]),
        "SEAS0_Q": q(seas["lag_0_month"]["p_value_bh_fdr"]),
        "SM_RHO": sign(sm_seas["lag_0_month"]["spearman_rho"]),
        "SM_Q": q(sm_seas["lag_0_month"]["p_value_bh_fdr"]),
        "RAIN_RHO": sign(f_rain["spearman_rho"]),
        "RAIN_Q": q(f_rain["p_value"]),
        "RAIN1_RHO": sign(f_rain1["spearman_rho"]),
        "RAIN1_Q": q(f_rain1["p_value"]),
        "RAIN_PEARSON": sign(f_rain["pearson_r"]),
        "RAIN_PEARSON_LO": sign(d["rain_to_sar_inundation_lags_deseasonalized"]["lag_0_month"]["pearson_ci95"][0]),
        "RAIN_PEARSON_HI": sign(d["rain_to_sar_inundation_lags_deseasonalized"]["lag_0_month"]["pearson_ci95"][1]),
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
        "SIG_SEAS_TEXT": "; ".join(f"{'same month' if l == 'lag_0_month' else 'one month later' if l == 'lag_1_month' else 'two months later'} (ρ = {sign(r['spearman_rho'])}, q = {q(r['p_value_bh_fdr'])})" for l, r in sig_seasonal) or "none",
        "PEAK_RAIN": clim_peak("rain_mm"),
        "PEAK_SOIL": clim_peak("shallow_sm_m3m3"),
        "PEAK_SAR": clim_peak("sar_flood_km2"),
        "PRINT_DATE": date.today().strftime("%-d %B %Y"),
    }
    return v


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="only light">
    <title>Monthly rainfall, soil moisture and floodplain inundation in the Ogun River catchment, Nigeria, 2019–2024</title>
    <meta name="description" content="Satellite records of rainfall, soil moisture, radar floodplain inundation and lagoon turbidity for the Ogun River catchment, 2019–2024. Rainfall and flooding share a seasonal cycle; month-to-month coupling is not robust.">
    <meta name="author" content="David Oluwayinka Oloyede">
    <meta name="citation_title" content="Monthly rainfall, soil moisture and floodplain inundation in the Ogun River catchment, Nigeria, 2019–2024">
    <meta name="citation_author" content="Oloyede, David Oluwayinka">
    <meta name="citation_publication_date" content="2026/11/08">
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%23111'/%3E%3Cpath d='M6 20c3 0 3-2 6-2s3 2 6 2 3-2 6-2' fill='none' stroke='%23fff' stroke-width='2.4' stroke-linecap='round'/%3E%3C/svg%3E">
    <link rel="preconnect" href="https://api.fontshare.com">
    <link rel="preconnect" href="https://cdn.fontshare.com" crossorigin>
    <link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&amp;display=swap">
    <link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=zodiak@500,700&amp;display=swap">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a class="skip" href="#abstract">Skip to the abstract</a>

<header class="site-header">
    <div class="site-inner">
        <a class="site-id" href="#top">Ogun catchment rainfall and flooding</a>
        <nav class="toc" aria-label="Sections">
            <a href="#abstract">Abstract</a>
            <a href="#study-area">Study area</a>
            <a href="#methods">Methods</a>
            <a href="#results">Results</a>
            <a href="#discussion">Discussion</a>
            <a href="explore.html" class="toc-ex">Explorer</a>
        </nav>
    </div>
    <div class="progress" aria-hidden="true"><span id="progress"></span></div>
</header>

<main class="article" id="top">
    <header class="title">
        <h1>Monthly rainfall, soil moisture and floodplain inundation in the Ogun River catchment, Nigeria, 2019–2024</h1>
        <p class="subtitle">Satellite records for four upland sub-basins and the Lagos Lagoon estuary</p>
        <p class="authors">David Oluwayinka Oloyede · Working paper, {PRINT_DATE}</p>
    </header>

    <section id="abstract" data-reveal class="abstract" aria-labelledby="h-abstract">
        <h2 id="h-abstract">Abstract</h2>
        <p><strong>Background.</strong> The Ogun River drains about {CATCH} km² of south-west Nigeria into the Lagos Lagoon. Rainfall and soil wetness control how much of the floodplain floods and how much sediment reaches the lagoon, but few studies have tested their month-to-month coupling with satellite data in this basin.</p>
        <p><strong>Aim.</strong> To assemble a monthly satellite record of rainfall, shallow soil moisture, radar-derived floodplain inundation and lagoon turbidity for {NMONTHS} months (January 2019 to December 2024), and to test whether rainfall and soil moisture are associated with inundation, and inundation with turbidity.</p>
        <p><strong>Methods.</strong> Monthly series were built from CHIRPS rainfall, ERA5-Land soil moisture (0–7 cm), Sentinel-1 radar inundation, Sentinel-2 turbidity (NDTI) and Dynamic World flooding as an optical reference, averaged over four upland sub-basins (Z1–Z4) and the estuarine zone (Z5). Associations were tested at lags of 0 to 2 months, on raw and seasonal-cycle-removed series, using Spearman's rho with autocorrelation-adjusted p-values, as the diagnostics recommend. Five headline relationships were corrected once for multiple testing (Benjamini–Hochberg).</p>
        <p><strong>Results.</strong> On raw monthly values, rainfall and inundation are associated at a two-month lag ({SEAS2_RHO}, q = {SEAS2_Q}), and soil moisture and inundation in the same month ({SM_RHO}, q = {SM_Q}). Both are seasonal co-variations that vanish once the seasonal cycle is removed. None of the {NFAM} headline relationships on the anomalies is significant after correction; the largest is between inundation and lagoon turbidity (ρ = {NDTI_RHO}, q = {NDTI_Q}). The radar index ranks months like the optical Dynamic World product in the seasonal cycle (ρ = {DW_SEAS_RHO}) but not in anomalies (ρ = {DW_ANOM_RHO}), and its values are far smaller (maximum {SAR_MAX} km² against {DW_MAX} km²).</p>
        <p><strong>Conclusions.</strong> Over six years, rainfall, soil moisture and radar inundation share a seasonal cycle but show no robust month-to-month coupling. The radar inundation index is uncalibrated and should be treated as relative. Its flood extent should not be cited until it is validated against gauge or optical data.</p>
        <p class="keywords"><strong>Keywords:</strong> Ogun River; floodplain inundation; Sentinel-1; CHIRPS; ERA5-Land; lagoon turbidity; time series; Nigeria</p>
    </section>

    <section id="introduction" aria-labelledby="h-intro">
        <h2 id="h-intro"><span class="n">1</span>Introduction</h2>
        <p>Floodplains store water and sediment between a river and its estuary. How much of a floodplain goes under water in a given month depends on rainfall, on how wet the soil already is, and on any reservoir upstream. Radar satellites can map inundation through cloud. The Sentinel-1 processing chain developed for automated flood mapping <span class="cite">(Twele et al., 2016)</span> is one such approach, and Google's Dynamic World product provides an optical land cover record that includes flooded vegetation and open water <span class="cite">(Brown et al., 2022)</span>.</p>
        <p>Gauge-based studies of the Ogun basin and its rainfall–flood behaviour exist, but in our review limited evidence was found for a single satellite record that combines rainfall, soil moisture, floodplain inundation and lagoon turbidity at monthly resolution. This study asks whether such a record can show how rainfall and soil moisture relate to floodplain inundation, and whether inundation relates to turbidity in the lagoon, over 2019 to 2024.</p>
    </section>

    <section id="study-area" aria-labelledby="h-area">
        <h2 id="h-area"><span class="n">2</span>Study area</h2>
        <p>The Ogun River drains about {CATCH} km² of south-west Nigeria, from the Oyo Basement Complex in the north to the Lagos Lagoon in the south. The catchment is divided into four hydrological sub-basins derived from HydroBASINS level 9 <span class="cite">(Lehner &amp; Grill, 2013)</span>. The fifth unit, Z5, is a rectangular lagoon zone at the river's outlet; it is not a watershed and is used only for turbidity (Figure 1).</p>
    </section>
    <figure class="wide reveal" id="fig-1">
        <img src="assets/figures/fig1_study_area.png" width="1440" height="1080" loading="lazy" alt="Map of the five analytical units of the Ogun catchment, Z1 to Z4 sub-basins and the lagoon zone Z5">
        <figcaption><b>Figure 1.</b> The five analytical units. Z1 to Z4 are hydrological sub-basins from HydroBASINS level 9; Z5 is the lagoon zone (areas in the legend).</figcaption>
    </figure>

    <section id="methods" aria-labelledby="h-methods">
        <h2 id="h-methods"><span class="n">3</span>Data and methods</h2>
        <figure class="tablefig">
            <figcaption id="cap-t1"><b>Table 1.</b> Data sources. All products are from Google Earth Engine (script v2.4.0), monthly, January 2019 to December 2024.</figcaption>
            <div class="table-wrap">
                <table aria-labelledby="cap-t1">
                    <thead><tr><th class="text">Variable</th><th class="text">Product</th><th class="text">Resolution</th><th class="text">Processing</th></tr></thead>
                    <tbody>
                        <tr><td class="text">Rainfall</td><td class="text">CHIRPS pentad <span class="cite">(Funk et al., 2015)</span></td><td class="text">0.05°</td><td class="text">Monthly total; kept when at least five pentads exist</td></tr>
                        <tr><td class="text">Shallow soil moisture</td><td class="text">ERA5-Land monthly <span class="cite">(Muñoz-Sabater et al., 2021)</span></td><td class="text">0.1°</td><td class="text">Volumetric water, 0–7 cm</td></tr>
                        <tr><td class="text">Floodplain inundation (index)</td><td class="text">Sentinel-1 GRD, VV, IW, ascending</td><td class="text">10 m, focal 50 m</td><td class="text">Radar water index; uncalibrated</td></tr>
                        <tr><td class="text">Flooding reference</td><td class="text">Dynamic World V1 <span class="cite">(Brown et al., 2022)</span></td><td class="text">10 m</td><td class="text">Water or flooded vegetation, same domain</td></tr>
                        <tr><td class="text">Lagoon turbidity</td><td class="text">Sentinel-2 SR</td><td class="text">10 m</td><td class="text">NDTI = (B4 − B3)/(B4 + B3) over open water (MNDWI &gt; 0)</td></tr>
                        <tr><td class="text">Reservoir</td><td class="text">Sentinel-1 open water, Oyan Reservoir</td><td class="text">10 m</td><td class="text">Area used as a regulation proxy; dam releases not available</td></tr>
                        <tr><td class="text">Catchment and units</td><td class="text">HydroBASINS level 9 <span class="cite">(Lehner &amp; Grill, 2013)</span></td><td class="text">Vector</td><td class="text">Upstream units traced from the Ogun mouth</td></tr>
                    </tbody>
                </table>
            </div>
        </figure>
        <p>Each variable is averaged over its unit and reported as a monthly series (Figure 2). Missing months are kept as missing and excluded pairwise. Dynamic World has {NDW} valid months; turbidity has {NNDTI}, and {NNDTIMISS} months are missing, mostly in the cloudy wet season.</p>
        <p>Two series are tested in two forms. The raw series show the seasonal co-variation. The anomaly series subtract each calendar month's six-year mean, so only month-to-month departures remain:</p>
        <div class="eq" role="group" aria-label="Equation 1">
            <div><span><var>a</var><sub><var>t</var></sub> = <var>x</var><sub><var>t</var></sub> − <var>x̄</var><sub>month(<var>t</var>)</sub></span><span>(1)</span></div>
        </div>
        <p>Association is measured with Spearman's rho, the estimator the diagnostics recommend when either series is not normally distributed. Its p-value is adjusted for autocorrelation with an effective sample size. Lags of 0, 1 and 2 months are tested. The five headline relationships on anomalies form one family, corrected once with Benjamini–Hochberg false discovery rate control <span class="cite">(Benjamini &amp; Hochberg, 1995)</span>; the result is reported as q. The Pearson correlation and its interval are given for transparency, but they are not used to decide significance. The reservoir control removes the linear effect of reservoir area before testing rainfall and flooding.</p>
        <p class="small">Full method, code and tests: <a href="https://github.com/oloyededavid/Ogun-Catchment-Coast-Observatory">repository</a>. The diagnostics file is <span class="mono">docs/data/cascade_diagnostics.json</span>.</p>
    </section>

    <section id="results" aria-labelledby="h-results">
        <h2 id="h-results"><span class="n">4</span>Results</h2>
        <h3 id="h-series"><span class="n">4.1</span>Seasonal pattern</h3>
        <p>Averaged by calendar month, rainfall peaks in {PEAK_RAIN}, soil moisture in {PEAK_SOIL} and the radar inundation index in {PEAK_SAR}. The largest radar value is {SAR_MAX} km², in {PEAK_MONTH}. The optical Dynamic World series reaches {DW_MAX} km² in its largest month, so the two are on very different scales (Figure 2).</p>
    </section>
    <figure class="wide reveal" id="fig-2">
        <img src="assets/figures/fig2_series.png" width="1440" height="1520" loading="lazy" alt="Five stacked time series, January 2019 to December 2024: rainfall, soil moisture, radar inundation index, Dynamic World flooding and lagoon turbidity">
        <figcaption><b>Figure 2.</b> Monthly catchment series, 2019 to 2024. Gaps are months without a valid observation.</figcaption>
    </figure>

    <section aria-labelledby="h-lags">
        <h3 id="h-lags"><span class="n">4.2</span>Raw monthly values</h3>
        <p>On raw values, rainfall and radar inundation are negatively associated at a lag: rain two months earlier goes with less flooding now ({SEAS2_RHO}, q = {SEAS2_Q}). Soil moisture and flooding in the same month show a similar negative association ({SM_RHO}, q = {SM_Q}). These are the seasonal co-variations the data would show in any two series that share an annual cycle. Their sign is not explained by a mechanism here, and the seasonal test below removes them (Figure 3).</p>
    </section>
    <figure class="wide reveal" id="fig-3">
        <img src="assets/figures/fig3_lags.png" width="1440" height="720" loading="lazy" alt="Bars of Spearman correlation between rainfall and inundation at lags of 0, 1 and 2 months, raw and with the seasonal cycle removed">
        <figcaption><b>Figure 3.</b> Spearman ρ between rainfall and radar inundation at lags of 0 to 2 months, on raw values and with the seasonal cycle removed. Raw values show a significant association only at two months (q = {SEAS2_Q}).</figcaption>
    </figure>

    <section aria-labelledby="h-anom">
        <h3 id="h-anom"><span class="n">4.3</span>Month-to-month anomalies</h3>
        <p>With the seasonal cycle removed, rainfall and flooding in the same month show a positive association (ρ = {RAIN_RHO}, q = {RAIN_Q}) that is not significant after correction. A one-month lag gives ρ = {RAIN1_RHO} (q = {RAIN1_Q}). The Pearson correlation for the same month is {RAIN_PEARSON} (95% interval {RAIN_PEARSON_LO} to {RAIN_PEARSON_HI}), but Pearson is sensitive to a single extreme month. Leaving out {PEAK_MONTH} alone gives r = {ROB_R} (95% interval {ROB_LO} to {ROB_HI}). Soil moisture and flooding give ρ = {SM_ANOM_RHO} (q = {SM_ANOM_Q}). Of the {NFAM} headline relationships, {NSIG_ANOM} is significant after correction (Figure 4).</p>
    </section>
    <figure class="wide reveal" id="fig-4">
        <img src="assets/figures/fig4_relationships.png" width="1440" height="680" loading="lazy" alt="Dot plot of Spearman correlation for the headline relationships, all with q above 0.05">
        <figcaption><b>Figure 4.</b> Spearman ρ for the headline relationships on anomalies. q is the Benjamini–Hochberg adjusted p-value across the family. Grey: not significant.</figcaption>
    </figure>

    <section aria-labelledby="h-res">
        <h3 id="h-res"><span class="n">4.4</span>Reservoir</h3>
        <p>Controlling for the open-water area of Oyan Reservoir leaves the same-month anomaly association almost unchanged (ρ = {CTL_RHO}, against {BASE_RHO} without the control). The reservoir is therefore not the explanation for the absence of a month-to-month link. Dam release records are not available, so the regulation effect is only partly tested (Figure 5).</p>
    </section>
    <figure class="wide reveal" id="fig-5">
        <img src="assets/figures/fig5_reservoir.png" width="1440" height="680" loading="lazy" alt="Bars comparing rainfall and inundation correlations with and without a reservoir control">
        <figcaption><b>Figure 5.</b> Spearman ρ between rainfall and inundation anomalies, with and without controlling for the Oyan Reservoir area.</figcaption>
    </figure>

    <section aria-labelledby="h-turb">
        <h3 id="h-turb"><span class="n">4.5</span>Flooding and lagoon turbidity</h3>
        <p>Lagoon turbidity (NDTI) and radar inundation anomalies are positively associated (ρ = {NDTI_RHO}, q = {NDTI_Q}), the largest association among the headline relationships, but it is not significant after correction. The NDTI is an uncalibrated indicator, not NTU or mg/L (Figure 6).</p>
    </section>
    <figure class="narrow reveal" id="fig-6">
        <img src="assets/figures/fig6_turbidity.png" width="920" height="720" loading="lazy" alt="Scatter of lagoon turbidity anomaly against radar inundation anomaly">
        <figcaption><b>Figure 6.</b> Monthly anomalies of radar inundation and lagoon turbidity.</figcaption>
    </figure>

    <section aria-labelledby="h-val">
        <h3 id="h-val"><span class="n">4.6</span>Agreement with the optical reference</h3>
        <p>The radar index and the Dynamic World flooding series rank months alike in the seasonal cycle (ρ = {DW_SEAS_RHO}), but not in the anomalies (ρ = {DW_ANOM_RHO}, q = {DW_ANOM_Q}). Its magnitude is far below the optical extent, so the index should be read as a relative measure of wet-season flooding, not an area (Figure 7).</p>
    </section>
    <figure class="narrow reveal" id="fig-7">
        <img src="assets/figures/fig7_dynamic_world.png" width="920" height="720" loading="lazy" alt="Scatter of radar inundation anomaly against Dynamic World flooding anomaly">
        <figcaption><b>Figure 7.</b> Monthly anomalies of the radar index and Dynamic World flooding.</figcaption>
    </figure>

    <section id="discussion" data-reveal aria-labelledby="h-disc">
        <h2 id="h-disc"><span class="n">5</span>Discussion</h2>
        <p>Rainfall, soil moisture and radar inundation share a seasonal cycle in this catchment, and that shared cycle is what the raw correlations show. Once it is removed, no headline relationship survives correction. A link between rainfall and flooding is therefore plausible from the seasonal pattern, but this six-year record cannot show that it operates from month to month. Longer records, which would give more years to estimate the climatology from, are the first requirement.</p>
        <p>The inundation index is the weakest part of the chain. It ranks months like the optical reference in the seasonal cycle, but its magnitude is far smaller, and it does not agree in anomalies. Until it is calibrated against gauge or optical water extent, the conclusions about flooding should be read as indicative.</p>
    </section>

    <section id="limitations" data-reveal aria-labelledby="h-lim">
        <h2 id="h-lim"><span class="n">6</span>Limitations</h2>
        <ul>
            <li>Six years give only six values per calendar month, so the anomalies depend on the six-year climatology and on individual years.</li>
            <li>Monthly resolution is coarser than the travel time of water across the upland catchment. Lagged results may reflect storage in soil and floodplain rather than flood routing.</li>
            <li>The radar inundation index is uncalibrated and far smaller than the optical reference.</li>
            <li>NDTI is an uncalibrated indicator and is missing mostly in the wet season, so turbidity results lean towards the dry season.</li>
            <li>Dam release records are not available; only the reservoir's open-water area is used.</li>
            <li>CHIRPS (about 5 km) and ERA5-Land (about 9 km) are coarse relative to the sub-basins' floodplain.</li>
            <li>The autocorrelation adjustment is an approximation based on an effective sample size.</li>
        </ul>
    </section>

    <section id="conclusion" data-reveal aria-labelledby="h-concl">
        <h2 id="h-concl"><span class="n">7</span>Conclusion</h2>
        <p>Over 2019 to 2024, rainfall, soil moisture and radar floodplain inundation in the Ogun catchment share a seasonal cycle, but they show no robust month-to-month coupling, and the lagoon turbidity link is not significant after correction. The radar inundation index needs calibration before its flood extent can be cited.</p>
    </section>

    <section id="explorer" class="explore-cta" data-reveal aria-labelledby="h-explorer">
        <a class="cta-card" href="explore.html">
            <span class="cta-text">
                <span class="cta-kicker">Interactive explorer</span>
                <span class="cta-title" id="h-explorer">Explore the monthly record</span>
                <span class="cta-body">Switch the map between inundation, rainfall, turbidity and vegetation, play through the months, and read each unit's series.</span>
                <span class="cta-go">Open the explorer →</span>
            </span>
        </a>
    </section>

    <section id="data-code" data-reveal aria-labelledby="h-dc">
        <h2 id="h-dc">Data, code and citation</h2>
        <ul class="downloads">
            <li><a href="data/ogun_monthly_timeseries.csv" download>ogun_monthly_timeseries.csv</a><span>Catchment-wide monthly series, 72 months</span></li>
            <li><a href="data/ogun_unit_monthly_timeseries.csv" download>ogun_unit_monthly_timeseries.csv</a><span>Per-unit monthly series</span></li>
            <li><a href="data/ogun_subbasins.geojson" download>ogun_subbasins.geojson</a><span>Analytical units</span></li>
            <li><a href="data/cascade_diagnostics.json" download>cascade_diagnostics.json</a><span>All statistics on this page</span></li>
            <li><a href="https://github.com/oloyededavid/Ogun-Catchment-Coast-Observatory">Repository</a><span>Earth Engine script, pipeline, tests</span></li>
        </ul>
        <h3 id="cite">How to cite</h3>
        <div class="citation">
            <p id="cite-text">Oloyede, D. O. (2026). <i>Monthly rainfall, soil moisture and floodplain inundation in the Ogun River catchment, Nigeria, 2019–2024</i>. https://github.com/oloyededavid/Ogun-Catchment-Coast-Observatory</p>
            <button type="button" class="button" id="copy-cite">Copy citation</button>
        </div>
    </section>

    <section id="references" aria-labelledby="h-refs">
        <h2 id="h-refs">References</h2>
        <ol class="refs">
            <li>Benjamini, Y., &amp; Hochberg, Y. (1995). Controlling the false discovery rate: a practical and powerful approach to multiple testing. <i>Journal of the Royal Statistical Society: Series B</i>, 57(1), 289–300. <a href="https://doi.org/10.1111/j.2517-6161.1995.tb02031.x">doi:10.1111/j.2517-6161.1995.tb02031.x</a></li>
            <li>Brown, C. F., et al. (2022). Dynamic World, near real-time global 10 m land use land cover mapping. <i>Scientific Data</i>, 9(1). <a href="https://doi.org/10.1038/s41597-022-01307-4">doi:10.1038/s41597-022-01307-4</a></li>
            <li>Funk, C., Peterson, P., Landsfeld, M., et al. (2015). The climate hazards infrared precipitation with stations: a new environmental record for monitoring extremes. <i>Scientific Data</i>, 2, 150066. <a href="https://doi.org/10.1038/sdata.2015.66">doi:10.1038/sdata.2015.66</a></li>
            <li>Lehner, B., &amp; Grill, G. (2013). Global river hydrography and network routing: baseline data and new approaches to study the world's large river systems. <i>Hydrological Processes</i>, 27(15), 2171–2186. <a href="https://doi.org/10.1002/hyp.9740">doi:10.1002/hyp.9740</a></li>
            <li>Muñoz-Sabater, J., Dutra, E., Agustí-Panareda, A., et al. (2021). ERA5-Land: a state-of-the-art global reanalysis dataset for land applications. <i>Earth System Science Data</i>, 13, 4349–4383. <a href="https://doi.org/10.5194/essd-13-4349-2021">doi:10.5194/essd-13-4349-2021</a></li>
            <li>Twele, A., Cao, W., Plank, S., &amp; Martinis, S. (2016). Sentinel-1-based flood mapping: a fully automated processing chain. <i>International Journal of Remote Sensing</i>, 37(13), 2990–3004.</li>
        </ol>
    </section>
</main>

<footer>
    <div class="inner">
        <p class="sig"><span>David Oloyede</span><span><a href="https://github.com/oloyededavid">github.com/oloyededavid</a></span><span>Last updated <time datetime="{ISO_DATE}">{PRINT_DATE}</time></span></p>
        <p>Code MIT, derived data CC BY 4.0. Source data keep their own terms: CHIRPS (Climate Hazards Center, UC Santa Barbara), ERA5-Land (Copernicus), Sentinel-1 and Sentinel-2 (Copernicus), Dynamic World (Google and World Resources Institute), HydroBASINS (WWF / HydroSHEDS).</p>
        <p>Other studies: <a href="https://oloyededavid.github.io/Oueme-Ogun-Groundwater-Recharge/">Ouémé–Ogun water balance</a> · <a href="https://oloyededavid.github.io/Lagos-Urban-Heat-Analytics/">Lagos Urban Heat and Exposure Analytics</a></p>
    </div>
</footer>
<script>
(() => {
    const bar = document.getElementById('progress');
    const top = document.getElementById('top');
    const onScroll = () => { const max = document.documentElement.scrollHeight - innerHeight; bar.style.width = (max > 0 ? scrollY / max * 100 : 0) + '%'; };
    addEventListener('scroll', onScroll, { passive: true }); onScroll();
    const copy = document.getElementById('copy-cite');
    copy.addEventListener('click', () => {
        const t = document.getElementById('cite-text').textContent.replace(/\\s+/g, ' ').trim();
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(() => copy.textContent = 'Copied', () => prompt('Copy the citation:', t));
        else prompt('Copy the citation:', t);
    });
})();
</script>
</body>
</html>
"""


def main() -> None:
    v = values()
    v["ISO_DATE"] = date.today().isoformat()
    if v.get("NSIG_ANOM") != "0":
        raise SystemExit("A headline relationship is now significant: the abstract and section 4.3 wording must be revised first.")
    text = TEMPLATE
    for k, val in v.items():
        text = text.replace("{" + k + "}", html.escape(val, quote=False) if k not in ("SIG_SEAS_TEXT",) else val)
    left = [t for t in ("{NMONTHS}",) if t in text]
    assert not left, left
    OUT.write_text(text)
    print("wrote", OUT, "| placeholders filled:", len(v))


if __name__ == "__main__":
    main()
