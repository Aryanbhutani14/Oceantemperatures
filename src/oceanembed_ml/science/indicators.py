"""Oceanographic indicators computed from temperature profiles at the 15 standard depths.

All functions take T with depth as the LAST axis (..., 15) and treat the profile
as piecewise-linear between standard depths (the same assumption used to
interpolate GLORYS to these depths). NaN = depth below seafloor / not defined.

  D20, D26  depth (m) of the first downward crossing of the 20 / 26 degC isotherm
  TCHP      tropical cyclone heat potential = rho * cp * integral_0^D26 (T - 26) dz  [kJ cm-2]
            (Leipper & Volgenau 1972), integrated exactly for a piecewise-linear profile
  MLD       mixed layer depth: first depth below 10 m where T < T(10 m) - 0.5 degC
            (temperature criterion; density-based MLD would need salinity, not predicted)
  OHC300    upper-ocean heat content rho * cp * integral_0^300 T dz  [GJ m-2]
"""
from __future__ import annotations

import numpy as np

from oceanembed_ml.grid import DEPTHS

RHO, CP = 1025.0, 3990.0
Z = DEPTHS.astype("float64")


def isotherm_depth(T: np.ndarray, iso: float) -> np.ndarray:
    T = np.asarray(T, dtype="float64")
    out = np.full(T.shape[:-1], np.nan)
    done = np.zeros(T.shape[:-1], bool)
    surface_ok = T[..., 0] >= iso
    for k in range(len(Z) - 1):
        t0, t1 = T[..., k], T[..., k + 1]
        cross = surface_ok & ~done & (t0 >= iso) & (t1 < iso)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = Z[k] + (t0 - iso) / (t0 - t1) * (Z[k + 1] - Z[k])
        out = np.where(cross, z, out)
        done |= cross
    return out


def d20(T):
    return isotherm_depth(T, 20.0)


def d26(T):
    return isotherm_depth(T, 26.0)


def tchp(T: np.ndarray) -> np.ndarray:
    """Exact integral of max(T - 26, 0) over a piecewise-linear profile, in kJ cm-2.

    NaN when the profile is too shallow to reach below the 26 degC layer.
    """
    T = np.asarray(T, dtype="float64")
    e = T - 26.0
    total = np.zeros(T.shape[:-1])
    valid = np.isfinite(T[..., 0])
    reached = ~(e[..., 0] > 0)                       # surface already < 26 -> TCHP = 0
    for k in range(len(Z) - 1):
        a, b, dz = e[..., k], e[..., k + 1], Z[k + 1] - Z[k]
        seg_ok = np.isfinite(a) & np.isfinite(b)
        both = (a > 0) & (b > 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            part = np.where(both, 0.5 * (a + b) * dz,
                   np.where((a > 0) & (b <= 0), 0.5 * a * (a / (a - b)) * dz,
                   np.where((a <= 0) & (b > 0), 0.5 * b * (b / (b - a)) * dz, 0.0)))
        total += np.where(seg_ok, part, 0.0)
        reached |= seg_ok & (b <= 0)
    out = total * RHO * CP / 1e7                     # J m-2 -> kJ cm-2
    return np.where(valid & reached, out, np.nan)


def mld(T: np.ndarray, dT: float = 0.5) -> np.ndarray:
    T = np.asarray(T, dtype="float64")
    kref = int(np.where(Z == 10)[0][0])
    thr = T[..., kref] - dT
    out = np.full(T.shape[:-1], np.nan)
    done = ~np.isfinite(thr)
    for k in range(kref, len(Z) - 1):
        t0, t1 = T[..., k], T[..., k + 1]
        cross = ~done & (t0 >= thr) & (t1 < thr)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = Z[k] + (t0 - thr) / (t0 - t1) * (Z[k + 1] - Z[k])
        out = np.where(cross, z, out)
        done |= cross
    return out


def ohc300(T: np.ndarray) -> np.ndarray:
    T = np.asarray(T, dtype="float64")
    k300 = int(np.where(Z == 300)[0][0]) + 1
    z, t = Z[:k300], T[..., :k300]
    integral = np.sum(0.5 * (t[..., 1:] + t[..., :-1]) * np.diff(z), axis=-1)
    return integral * RHO * CP / 1e9                  # GJ m-2


INDICATORS = {"D20": (d20, "m"), "D26": (d26, "m"), "TCHP": (tchp, "kJ cm-2"), "MLD": (mld, "m"), "OHC300": (ohc300, "GJ m-2")}
