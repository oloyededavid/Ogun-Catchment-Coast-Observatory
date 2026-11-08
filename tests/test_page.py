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
    for src in re.findall(r'<img src="([^"]+)"', html):
        assert (DOCS / src).exists(), src
    for href in re.findall(r'<a href="(data/[^"]+)" download>', html):
        assert (DOCS / href).exists(), href


def test_headline_numbers_are_the_corrected_ones():
    text = _page()
    assert "0 is significant after correction" in text
    assert "q = 0.006" in text
