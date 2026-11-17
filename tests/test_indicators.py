"""Indicator tests on synthetic profiles with known answers."""
import numpy as np

from oceanembed_ml.grid import DEPTHS
from oceanembed_ml.science.indicators import d20, d26, mld, tchp

Z = DEPTHS.astype(float)


def linear_profile(t0=30.0, slope=-0.05):
    return t0 + slope * Z            # 30 C at surface, -0.05 C per m


def test_isotherm_depths_linear_profile():
    T = linear_profile()
    assert abs(d26(T) - 80.0) < 1e-6      # 30 - 0.05 z = 26 -> z = 80
    assert abs(d20(T) - 200.0) < 1e-6


def test_tchp_exact_for_linear_profile():
    T = linear_profile()
    # integral_0^80 (4 - 0.05 z) dz = 4*80 - 0.025*80^2 = 160 degC m
    expected = 160 * 1025 * 3990 / 1e7
    assert abs(tchp(T) - expected) < 1e-6


def test_tchp_zero_when_cold_and_nan_when_shallow():
    assert tchp(np.full(15, 20.0)) == 0.0
    T = np.full(15, 29.0); T[5:] = np.nan        # never reaches below 26 C -> undefined
    assert np.isnan(tchp(T))


def test_mld_well_mixed_layer():
    T = np.array([28, 28, 28, 28, 28, 27, 25, 23, 21, 19, 17, 13, 10, 8, 6], float)
    # T(10) = 28, threshold 27.5, crossing between 30 m (28) and 50 m (27) -> 40 m
    assert abs(mld(T) - 40.0) < 1e-6


def test_vectorised_shapes():
    T = np.stack([linear_profile(), linear_profile(28.0)])
    assert d26(T).shape == (2,) and tchp(T).shape == (2,)
