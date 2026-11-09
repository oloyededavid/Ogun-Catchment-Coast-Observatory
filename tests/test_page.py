"""The study page must be complete: no unfilled placeholders, every image and download present."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _page():
    return (DOCS / "index.html").read_text(encoding="utf-8")


def test_no_unfilled_placeholders():
    assert not re.findall(r"\{[A-Z][A-Z0-9_]+\}", _page())


def test_every_image_and_download_exists():
    html = _page()
    srcs = re.findall(r'<img[^>]*\ssrc="([^"]+)"', html) + re.findall(r'<source[^>]*\ssrcset="([^"]+)"', html)
    assert srcs, "no images found"
    for src in srcs:
        assert (DOCS / src).exists(), src
    downloads = re.findall(r'<a[^>]*\shref="(data/[^"]+)"[^>]*\sdownload', html)
    assert downloads, "no data download link found"
    for href in downloads:
        assert (DOCS / href).exists(), href


def test_figure_numbers_run_in_order():
    numbers = [int(n) for n in re.findall(r"<b>Figure (\d+)\.</b>", _page())]
    assert numbers == sorted(numbers) and numbers == list(range(1, len(numbers) + 1)), numbers


def test_months_and_units_come_from_the_data():
    import csv
    rows = list(csv.DictReader((DOCS / "data" / "ogun_unit_monthly_timeseries.csv").open(encoding="utf-8")))
    months = {r["year_month"] for r in rows}
    assert f'data-count="{len(months)}"' in _page()


def test_headline_numbers_are_the_corrected_ones():
    text = _page()
    assert "None of the 5 headline relationships is significant after correction." in text
    assert "q = 0.006" in text
