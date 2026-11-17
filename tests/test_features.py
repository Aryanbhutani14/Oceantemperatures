"""Unit + leakage tests for Phase 4 features.

Run:  python -m pytest -q
"""
import numpy as np
import pytest

from oceanembed_ml.config import FINAL
from oceanembed_ml.features import physics as P

LAT = np.arange(5.0, 30.01, 0.25)
LON = np.arange(45.0, 105.01, 0.25)


def test_trailing_mean_is_past_only():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(40, 3, 3))
    a = P.trailing_mean(x, 7)
    x2 = x.copy()
    x2[25:] += 100.0                       # change the FUTURE of day 24
    b = P.trailing_mean(x2, 7)
    np.testing.assert_allclose(a[:25], b[:25])
    np.testing.assert_allclose(a[10], x[4:11].mean(0), rtol=1e-5)


def test_lagged_change():
    x = np.arange(10, dtype="float32")[:, None, None] * np.ones((1, 2, 2))
    c = P.lagged_change(x, 7)
    assert np.isnan(c[:7]).all() and np.allclose(c[7:], 7.0)


def test_gradient_of_linear_field():
    # field increasing 1 unit per degree of latitude -> d/dy = 1 / 111.2 km = 0.899 per 100 km
    f = np.repeat(LAT[:, None], LON.size, axis=1)
    dx, dy = P.gradients(f, LAT, LON)
    assert np.allclose(dx, 0, atol=1e-6)
    assert np.allclose(dy, 100 / (6371 * np.pi / 180), rtol=1e-3)


def test_uniform_wind_has_no_curl_and_stress_direction():
    u = np.full((LAT.size, LON.size), 8.0)
    v = np.zeros_like(u)
    tx, ty = P.wind_stress(u, v)
    assert np.allclose(tx, 1.22 * 1.2e-3 * 64) and np.allclose(ty, 0)
    curl, w = P.ekman_pumping(np.zeros_like(u), np.zeros_like(u), LAT, LON)
    assert np.allclose(curl, 0) and np.allclose(w, 0)


def test_box_mean_keeps_land_nan_and_constant():
    f = np.full((20, 20), 3.0)
    f[5, 5] = np.nan
    b = P.box_mean(f, 5)
    assert np.isnan(b[5, 5])
    assert np.allclose(b[np.isfinite(b)], 3.0)


@pytest.mark.skipif(not (FINAL / "features" / "train.parquet").exists(), reason="feature tables not built")
def test_tables_have_no_split_overlap():
    import pyarrow.parquet as pq
    tr = pq.read_table(FINAL / "features" / "train.parquet", columns=["time", "month"]).to_pandas()
    te = pq.read_table(FINAL / "features" / "test.parquet", columns=["time", "month"]).to_pandas()
    assert set(tr.month.unique()).isdisjoint(set(te.month.unique()))
    assert set(te.month.unique()) == {2, 5, 8, 11}
    gap = min(abs((a - b).days) for a in tr.time.unique() for b in te.time.unique())
    assert gap > 7, f"train/test days closer than the 7-day buffer: {gap}"
