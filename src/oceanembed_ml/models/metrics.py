"""Per-depth regression metrics on ABSOLUTE temperature (prediction = climatology + anomaly).

R² on absolute temperature is inflated by the large spatial/vertical spread, so we
also report SKILL vs climatology:  skill = 1 - MSE_model / MSE_climatology
(0 = no better than climatology, 1 = perfect). Bias = mean(pred - truth).
"""
from __future__ import annotations

import numpy as np

from oceanembed_ml.grid import DEPTHS


def _one(t: np.ndarray, p: np.ndarray, c: np.ndarray) -> dict:
    m = np.isfinite(t) & np.isfinite(p)
    t, p, c = t[m].astype("float64"), p[m].astype("float64"), c[m].astype("float64")
    e = p - t
    mse = float(np.mean(e**2))
    mse_clim = float(np.mean((c - t) ** 2))
    return {"n": int(m.sum()), "rmse": mse**0.5, "mae": float(np.mean(np.abs(e))), "bias": float(e.mean()),
            "r2": float(1 - mse / np.var(t)) if np.var(t) > 0 else float("nan"),
            "pearson_r": float(np.corrcoef(t, p)[0, 1]) if m.sum() > 2 else float("nan"),
            "skill_vs_clim": float(1 - mse / mse_clim) if mse_clim > 0 else float("nan"),
            "rmse_clim": mse_clim**0.5}


def evaluate(Y: np.ndarray, A_pred: np.ndarray, C: np.ndarray) -> dict:
    """Y, A_pred, C: (n, 15). Returns per-depth and pooled metrics."""
    P = C + A_pred
    per = {str(int(d)): _one(Y[:, k], P[:, k], C[:, k]) for k, d in enumerate(DEPTHS)}
    overall = _one(Y.ravel(), P.ravel(), C.ravel())
    return {"overall": overall, "per_depth": per,
            "mean_rmse_over_depths": float(np.mean([v["rmse"] for v in per.values()])),
            "mean_skill_over_depths": float(np.mean([v["skill_vs_clim"] for v in per.values()]))}


def rmse_anomaly(A_true: np.ndarray, A_pred: np.ndarray) -> np.ndarray:
    """RMSE per column on the anomaly (used in CV)."""
    m = np.isfinite(A_true) & np.isfinite(A_pred)
    out = []
    for k in range(A_true.shape[1]):
        mk = m[:, k]
        out.append(float(np.sqrt(np.mean((A_true[mk, k] - A_pred[mk, k]) ** 2))) if mk.any() else np.nan)
    return np.array(out)
