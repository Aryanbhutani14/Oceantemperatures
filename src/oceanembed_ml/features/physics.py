"""Physically motivated feature functions (pure NumPy, unit-tested).

All functions work on arrays shaped (time, lat, lon) or (lat, lon) on a regular
lat/lon grid and are NaN-aware. None of them look into the future: temporal
features use TRAILING windows only (day t uses days <= t).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

EARTH_RADIUS_M = 6_371_000.0
OMEGA = 7.2921e-5          # Earth's rotation rate (s-1)
RHO_AIR = 1.22             # kg m-3
RHO_SEA = 1025.0           # kg m-3


def _spacing(lat: np.ndarray, lon: np.ndarray):
    """Grid spacing in metres: dx (per latitude row) and dy (scalar)."""
    dlat = np.deg2rad(np.median(np.diff(lat)))
    dlon = np.deg2rad(np.median(np.diff(lon)))
    dy = EARTH_RADIUS_M * dlat
    dx = EARTH_RADIUS_M * np.cos(np.deg2rad(lat)) * dlon          # (nlat,)
    return dx, dy


def gradients(field: np.ndarray, lat: np.ndarray, lon: np.ndarray):
    """Centred differences d/dx, d/dy in field-units per 100 km (NaN at coasts)."""
    dx, dy = _spacing(lat, lon)
    f = np.asarray(field, dtype="float64")
    ddy = np.gradient(f, axis=-2) / dy
    ddx = np.gradient(f, axis=-1) / dx[:, None]
    return (ddx * 1e5).astype("float32"), (ddy * 1e5).astype("float32")


def laplacian(field: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """d2/dx2 + d2/dy2 in field-units per (100 km)^2. Positive = local minimum (e.g. cyclonic eddy in SLA)."""
    dx, dy = _spacing(lat, lon)
    f = np.asarray(field, dtype="float64")
    d2y = np.gradient(np.gradient(f, axis=-2), axis=-2) / dy**2
    d2x = np.gradient(np.gradient(f, axis=-1), axis=-1) / (dx[:, None] ** 2)
    return ((d2x + d2y) * 1e10).astype("float32")


def box_mean(field: np.ndarray, size: int) -> np.ndarray:
    """NaN-aware spatial moving average over a size x size window (land ignored, not treated as 0)."""
    f = np.asarray(field, dtype="float64")
    valid = np.isfinite(f)
    spatial = (1,) * (f.ndim - 2) + (size, size)
    num = uniform_filter(np.where(valid, f, 0.0), size=spatial, mode="nearest")
    den = uniform_filter(valid.astype("float64"), size=spatial, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den == 0] = np.nan
    out[~valid] = np.nan               # keep land/gap cells NaN (no fabrication)
    return out.astype("float32")


def drag_coefficient(speed: np.ndarray) -> np.ndarray:
    """Large & Pond (1981) neutral drag coefficient (speeds < 4 m/s held at the 4 m/s value)."""
    s = np.asarray(speed, dtype="float64")
    return np.where(s < 11.0, 1.2e-3, (0.49 + 0.065 * s) * 1e-3)


def wind_stress(u10: np.ndarray, v10: np.ndarray):
    """Bulk wind stress (N m-2): tau = rho_air * Cd(|U|) * |U| * (u, v)."""
    u, v = np.asarray(u10, dtype="float64"), np.asarray(v10, dtype="float64")
    s = np.hypot(u, v)
    k = RHO_AIR * drag_coefficient(s) * s
    return (k * u).astype("float32"), (k * v).astype("float32")


def coriolis(lat: np.ndarray) -> np.ndarray:
    return 2 * OMEGA * np.sin(np.deg2rad(lat))


def ekman_pumping(taux: np.ndarray, tauy: np.ndarray, lat: np.ndarray, lon: np.ndarray):
    """Wind-stress curl (N m-3, x1e7) and Ekman pumping velocity w_E = curl(tau / f) / rho0 (m/day).

    Positive w_E = upwelling (lifts the thermocline, cools the subsurface).
    The domain starts at 5 N, so f is never zero.
    """
    dx, dy = _spacing(lat, lon)
    f = coriolis(lat)[:, None]
    tx, ty = np.asarray(taux, dtype="float64"), np.asarray(tauy, dtype="float64")
    curl = np.gradient(ty, axis=-1) / dx[:, None] - np.gradient(tx, axis=-2) / dy
    curl_f = np.gradient(ty / f, axis=-1) / dx[:, None] - np.gradient(tx / f, axis=-2) / dy
    w = curl_f / RHO_SEA * 86400.0
    return (curl * 1e7).astype("float32"), w.astype("float32")


def trailing_mean(x: np.ndarray, window: int) -> np.ndarray:
    """Mean over days t-window+1 .. t (inclusive), NaN-aware, along axis 0. Never uses t+1.

    At the start of the record fewer days are available; the mean uses what
    exists (documented). Returns NaN where no valid value exists.
    """
    a = np.asarray(x, dtype="float64")
    valid = np.isfinite(a)
    cs = np.cumsum(np.where(valid, a, 0.0), axis=0)
    cn = np.cumsum(valid, axis=0).astype("float64")
    cs_lag = np.concatenate([np.zeros((window,) + a.shape[1:]), cs[:-window]], axis=0)[: a.shape[0]]
    cn_lag = np.concatenate([np.zeros((window,) + a.shape[1:]), cn[:-window]], axis=0)[: a.shape[0]]
    n = cn - cn_lag
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (cs - cs_lag) / n
    out[n == 0] = np.nan
    return out.astype("float32")


def lagged_change(x: np.ndarray, lag: int) -> np.ndarray:
    """x_t - x_{t-lag} (NaN for the first `lag` days). Past-only."""
    a = np.asarray(x, dtype="float32")
    out = np.full_like(a, np.nan)
    out[lag:] = a[lag:] - a[:-lag]
    return out
