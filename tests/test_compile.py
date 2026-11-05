import numpy as np
import pandas as pd


def test_benjamini_hochberg_matches_reference(compiler):
    # Reference values from statsmodels.stats.multitest.multipletests(method="fdr_bh")
    adjusted = compiler._benjamini_hochberg([0.01, 0.04, 0.03])
    assert adjusted == [0.03, 0.04, 0.04]


def test_effective_n_shrinks_with_autocorrelation(compiler):
    t = np.arange(72)
    smooth = pd.Series(np.sin(t / 3.0))
    noise = pd.Series(np.random.default_rng(0).normal(size=72))
    assert compiler._effective_n(smooth, smooth, 72) < 20
    assert compiler._effective_n(noise, noise, 72) > 60


def test_insufficient_pairs_reported(compiler):
    res = compiler._bivariate_test(pd.Series([1.0, 2.0, np.nan]), pd.Series([1.0, np.nan, 3.0]))
    assert res["status"] == "INSUFFICIENT_OBSERVATIONS"
    assert res["pearson_r"] is None


def _monthly_frame(rain_by_year):
    rows = []
    for yi, rain in enumerate(rain_by_year):
        for m in range(12):
            rows.append({"year_month": f"{2019 + yi}-{m + 1:02d}", "rain_mm": rain[m],
                         "data_status": "VERIFIED_GEE_EXPORT"})
    return pd.DataFrame(rows)


def test_repeating_climatology_flagged_as_demo(compiler):
    base = 100 + 80 * np.sin(np.arange(12) / 12 * 2 * np.pi)
    df = _monthly_frame([base * 1.001 ** i for i in range(6)])
    assert compiler._detect_synthetic_template(df)


def test_varied_years_not_flagged(compiler):
    rng = np.random.default_rng(1)
    base = 100 + 80 * np.sin(np.arange(12) / 12 * 2 * np.pi)
    df = _monthly_frame([base + rng.normal(0, 40, 12) for _ in range(6)])
    assert not compiler._detect_synthetic_template(df)


def test_partial_correlation_removes_shared_driver(compiler):
    rng = np.random.default_rng(2)
    driver = pd.Series(rng.normal(size=72))
    x = driver + 0.1 * pd.Series(rng.normal(size=72))
    y = driver + 0.1 * pd.Series(rng.normal(size=72))
    plain = compiler._lag_suite(x, y)["lag_0_month"]["pearson_r"]
    partial = compiler._lag_suite(x, y, control=driver)["lag_0_month"]["pearson_r"]
    assert plain > 0.9
    assert abs(partial) < 0.35


def test_robustness_finds_single_outlier(compiler):
    rng = np.random.default_rng(3)
    x = pd.Series(rng.normal(size=60))
    y = pd.Series(rng.normal(size=60))
    x[17], y[17] = 12.0, 12.0  # one extreme month creates a spurious correlation
    months = pd.Series([f"m{i}" for i in range(60)])
    res = compiler._robustness(x, y, months)
    assert res["most_influential_month"] == "m17"
    assert res["pearson_r_full"] > 0.5
    assert abs(res["without_most_influential_month"]["pearson_r"]) < 0.4
