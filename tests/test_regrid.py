"""Unit tests for the regridding operator and vertical interpolation.

Run:  .venv/Scripts/python -m pytest -q tests
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from oceanembed_ml.grid import LAT, LON, ConservativeRegridder, vertical_interp  # noqa: E402


def _src(step, off):
    lat = np.round(np.arange(4.5 + off, 30.5, step), 6)
    lon = np.round(np.arange(44.5 + off, 105.5, step), 6)
    return lat, lon


def test_identity_on_same_grid():
    lat = np.round(np.arange(4.5, 30.5 + 1e-9, 0.25), 6)
    lon = np.round(np.arange(44.5, 105.5 + 1e-9, 0.25), 6)
    rng = np.random.default_rng(0)
    x = rng.normal(size=(lat.size, lon.size))
    out = ConservativeRegridder(lat, lon)(x)
    i0, j0 = np.searchsorted(lat, LAT[0]), np.searchsorted(lon, LON[0])
    np.testing.assert_allclose(out, x[i0:i0 + 101, j0:j0 + 241], atol=1e-6)


def test_constant_field_preserved_all_grids():
    for step, off in [(0.05, 0.025), (0.125, 0.0625), (1 / 12, 0.0)]:
        lat, lon = _src(step, off)
        out = ConservativeRegridder(lat, lon)(np.full((lat.size, lon.size), 7.5))
        assert np.allclose(out, 7.5), step


def test_nested_2x2_equals_block_mean():
    lat, lon = _src(0.125, 0.0625)
    rng = np.random.default_rng(1)
    x = rng.normal(size=(lat.size, lon.size))
    out = ConservativeRegridder(lat, lon)(x)
    # canonical cell at (LAT[10], LON[20]) = mean of the 4 native cells it contains (area-weighted)
    I, J = 10, 20
    rows = np.where(np.abs(lat - LAT[I]) < 0.125)[0]
    cols = np.where(np.abs(lon - LON[J]) < 0.125)[0]
    assert rows.size == 2 and cols.size == 2
    w = np.cos(np.deg2rad(lat[rows]))[:, None] * np.ones((1, 2))
    np.testing.assert_allclose(out[I, J], (x[np.ix_(rows, cols)] * w).sum() / w.sum(), atol=1e-5)


def test_area_integral_conserved_ostia_like():
    lat, lon = _src(0.05, 0.025)
    x = np.sin(np.deg2rad(lat))[:, None] * np.cos(np.deg2rad(lon))[None, :]
    rg = ConservativeRegridder(lat, lon)
    out = rg(x)
    # integral over the canonical domain computed two ways
    src_int = (rg.Wlat @ x @ rg.Wlon.T).sum()
    dst_int = (out * rg._full).sum()
    assert abs(src_int - dst_int) / abs(src_int) < 1e-5


def test_nan_threshold():
    lat, lon = _src(0.125, 0.0625)
    x = np.ones((lat.size, lon.size))
    I, J = 10, 20
    rows = np.where(np.abs(lat - LAT[I]) < 0.125)[0]
    cols = np.where(np.abs(lon - LON[J]) < 0.125)[0]
    x[rows[0], cols[0]] = np.nan                     # 1/4 missing -> still valid
    assert np.isfinite(ConservativeRegridder(lat, lon)(x)[I, J])
    x[rows[0], cols[1]] = np.nan
    x[rows[1], cols[0]] = np.nan                     # 3/4 missing -> NaN
    assert np.isnan(ConservativeRegridder(lat, lon)(x)[I, J])


def test_vertical_interp():
    z = np.array([0.5, 4.0, 6.0, 9.0, 11.0, 1045.0])
    v = np.array([30.0, 29.0, 28.0, 27.0, 26.0, 5.0])
    out = vertical_interp(v[:, None], z, np.array([0, 5, 10, 1000]))[:, 0]
    np.testing.assert_allclose(out[:3], [30.0, 28.5, 26.5])
    # below-seafloor: NaN bracket -> NaN, never extrapolated
    v2 = v.copy(); v2[-1] = np.nan
    assert np.isnan(vertical_interp(v2[:, None], z, np.array([1000]))[0, 0])
