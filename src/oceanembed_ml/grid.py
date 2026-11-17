"""Canonical grid and the single spatial regridding operator used for every source.

Canonical grid (configs/grid.yaml): cell CENTRES lat 5.00..30.00, lon 45.00..105.00,
step 0.25 deg. Cell (i, j) spans [c - 0.125, c + 0.125] in each direction.

Regridding = first-order CONSERVATIVE (area-weighted overlap) remapping:

    out[I, J] = sum_ij  w_lat[I, i] * w_lon[J, j] * x[i, j]  /  sum_ij w_lat w_lon valid[i, j]

where w_lat[I, i] = overlap length of native row i with canonical row I times
cos(latitude) (area factor), and w_lon[J, j] = overlap length in longitude.
Because the grids are regular the weights are separable, so the operator is two
small matrix products per time step.

Properties (unit-tested in tests/test_regrid.py):
  * identical grids                      -> identity (exact selection)
  * native cells nested inside canonical -> exactly the block mean (2x2, 3x3)
  * misaligned finer grid (OSTIA 0.05)   -> correct partial-cell weighting
  * a constant field stays constant; the area integral is conserved
  * NaN-aware: a canonical cell is NaN unless >= `min_valid_frac` of its
    overlapping area holds valid native data (no extrapolation into land/gaps)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from oceanembed_ml.config import ROOT
_GRID = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
DOMAIN = _GRID["domain"]
RES = float(DOMAIN["res"])
DEPTHS = np.array(_GRID["depths"], dtype="float64")
REGIONS = _GRID["regions"]

LAT = np.round(np.arange(DOMAIN["lat_min"], DOMAIN["lat_max"] + RES / 2, RES), 6)
LON = np.round(np.arange(DOMAIN["lon_min"], DOMAIN["lon_max"] + RES / 2, RES), 6)
assert LAT.size == 101 and LON.size == 241, (LAT.size, LON.size)


def cell_edges(centres: np.ndarray) -> np.ndarray:
    """Edges of a regular grid given its centres."""
    c = np.asarray(centres, dtype="float64")
    step = np.median(np.diff(c))
    return np.concatenate([c - step / 2, [c[-1] + step / 2]])


def overlap_matrix(dst_centres: np.ndarray, src_centres: np.ndarray, area_lat: bool = False) -> np.ndarray:
    """W[I, i] = length of overlap between destination cell I and source cell i.

    If `area_lat`, each source column is multiplied by cos(lat) so that, combined
    with the longitude matrix, weights are proportional to true cell areas.
    """
    de, se = cell_edges(dst_centres), cell_edges(src_centres)
    lo = np.maximum(de[:-1, None], se[None, :-1])
    hi = np.minimum(de[1:, None], se[None, 1:])
    w = np.clip(hi - lo, 0.0, None)
    w[w < 1e-9] = 0.0
    if area_lat:
        w = w * np.cos(np.deg2rad(np.asarray(src_centres)))[None, :]
    return w


class ConservativeRegridder:
    """Area-weighted, NaN-aware regridding from a regular source grid to the canonical grid."""

    def __init__(self, src_lat: np.ndarray, src_lon: np.ndarray, dst_lat=LAT, dst_lon=LON, min_valid_frac: float = 0.5):
        src_lat = np.asarray(src_lat, dtype="float64")
        src_lon = np.asarray(src_lon, dtype="float64")
        if not (np.all(np.diff(src_lat) > 0) and np.all(np.diff(src_lon) > 0)):
            raise ValueError("source coordinates must be strictly ascending (sort before regridding)")
        self.Wlat = overlap_matrix(dst_lat, src_lat, area_lat=True)  # (101, nlat_src)
        self.Wlon = overlap_matrix(dst_lon, src_lon)                 # (241, nlon_src)
        full = self.Wlat.sum(1)[:, None] * self.Wlon.sum(1)[None, :]
        if np.any(full <= 0):
            raise ValueError("source grid does not cover every canonical cell")
        self._full = full
        self.min_valid_frac = min_valid_frac

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """Regrid array (..., nlat_src, nlon_src) -> (..., 101, 241). float32 out."""
        x = np.asarray(x, dtype="float64")
        valid = np.isfinite(x)
        x0 = np.where(valid, x, 0.0)
        num = np.einsum("Ii,...ij,Jj->...IJ", self.Wlat, x0, self.Wlon, optimize=True)
        den = np.einsum("Ii,...ij,Jj->...IJ", self.Wlat, valid.astype("float64"), self.Wlon, optimize=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = num / den
        out[den < self.min_valid_frac * self._full] = np.nan
        return out.astype("float32")


def vertical_interp(values: np.ndarray, native_depth: np.ndarray, target_depth: np.ndarray = DEPTHS, axis: int = 0) -> np.ndarray:
    """Linear interpolation in depth, NaN-safe, no extrapolation.

    * target depth shallower than the first native level (0 m) -> value of the
      shallowest native level (documented convention, no extrapolation of slope)
    * a target depth is NaN unless BOTH bracketing native levels are finite
      (so cells shallower than the target depth stay NaN = below seafloor)
    """
    z = np.asarray(native_depth, dtype="float64")
    v = np.moveaxis(np.asarray(values, dtype="float64"), axis, 0)
    out = np.full((len(target_depth),) + v.shape[1:], np.nan)
    for k, d in enumerate(target_depth):
        if d <= z[0]:
            out[k] = v[0]
            continue
        hi = int(np.searchsorted(z, d))
        if hi >= len(z):
            continue  # deeper than deepest native level -> NaN (no extrapolation)
        lo = hi - 1
        if np.isclose(z[hi], d):
            out[k] = v[hi]
            continue
        f = (d - z[lo]) / (z[hi] - z[lo])
        out[k] = v[lo] * (1 - f) + v[hi] * f  # NaN if either bracket is NaN
    return np.moveaxis(out, 0, axis).astype("float32")
