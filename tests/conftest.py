import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "src" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def compiler():
    return _load("compile_observatory", "02_compile_observatory.py")


@pytest.fixture(scope="session")
def ingester():
    return _load("ingest_gee_exports", "01_ingest_gee_exports.py")
