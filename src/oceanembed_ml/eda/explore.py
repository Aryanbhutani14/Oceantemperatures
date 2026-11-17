"""Phase 3 — Exploratory Data Analysis on the integrated cube.

Leakage rule: DESCRIPTIVE statistics use all days (they describe the data set),
but every RELATIONSHIP analysis that could inform feature/model choices
(correlations, PCA of profiles, feature-target relationships) uses TRAIN days
only. Test months are never looked at for those.

Outputs
  reports/figures/phase3/*.png
  data/audit/eda_stats.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
from scipy import stats  # noqa: E402

from oceanembed_ml.config import ROOT
from oceanembed_ml.grid import DEPTHS, REGIONS  # noqa: E402

warnings.filterwarnings("ignore")
OUT = ROOT / "reports" / "figures" / "phase3"
OUT.mkdir(parents=True, exist_ok=True)
INPUTS = ["sst", "sss", "sla", "uo", "vo", "u10", "v10"]
UNITS = {"sst": "°C", "sss": "PSU", "sla": "m", "uo": "m/s", "vo": "m/s", "u10": "m/s", "v10": "m/s"}
RNG = np.random.default_rng(42)
S: dict = {}


def save(fig, name):
    fig.savefig(OUT / name, dpi=110)
    plt.close(fig)


def describe(x: np.ndarray) -> dict:
    v = x[np.isfinite(x)]
    q = np.percentile(v, [1, 5, 25, 50, 75, 95, 99])
    return {"n": int(v.size), "mean": float(v.mean()), "std": float(v.std()), "min": float(v.min()), "max": float(v.max()),
            "p01": q[0], "p05": q[1], "p25": q[2], "median": q[3], "p75": q[4], "p95": q[5], "p99": q[6],
            "skew": float(stats.skew(v[:: max(1, v.size // 2_000_000)])), "kurtosis": float(stats.kurtosis(v[:: max(1, v.size // 2_000_000)]))}


def region_mask(ds, r):
    b = REGIONS[r]
    return ((ds.lat >= b["lat"][0]) & (ds.lat <= b["lat"][1]) & (ds.lon >= b["lon"][0]) & (ds.lon <= b["lon"][1])).values


def main() -> int:
    ds = xr.open_dataset(ROOT / "data" / "processed" / "cube.nc").load()
    ocean = ds.ocean_mask.values.astype(bool)
    split = ds.split.values
    train = split == "train"
    month = ds.month_of_time.values
    clim_daily = ds.thetao_clim.values[month - 1]                     # (t, z, y, x) external climatology
    anom = ds.thetao.values - clim_daily

    # ------------------------------------------------------------ 1. dataset-level
    S["dataset"] = {"dims": {k: int(v) for k, v in ds.sizes.items()}, "ocean_cells": int(ocean.sum()),
                    "days_per_split": pd.Series(split).value_counts().to_dict(),
                    "date_range": [str(ds.time.values[0])[:10], str(ds.time.values[-1])[:10]]}
    S["inputs"] = {v: describe(ds[v].values[:, ocean]) | {"missing_frac_ocean": float(np.isnan(ds[v].values[:, ocean]).mean())} for v in INPUTS}
    S["target_by_depth"] = {str(int(d)): describe(ds.thetao.values[:, k][:, ocean]) for k, d in enumerate(DEPTHS)}
    S["anomaly_std_by_depth"] = {str(int(d)): float(np.nanstd(anom[:, k][:, ocean])) for k, d in enumerate(DEPTHS)}
    S["anomaly_mean_by_depth"] = {str(int(d)): float(np.nanmean(anom[:, k][:, ocean])) for k, d in enumerate(DEPTHS)}

    # ------------------------------------------------------------ 2. spatial maps
    fig, ax = plt.subplots(2, 4, figsize=(18, 6.5), constrained_layout=True)
    for a, v in zip(ax.flat, INPUTS):
        m = ds[v].mean("time")
        cmap = "RdBu_r" if v in ("sla", "uo", "vo", "u10", "v10") else "turbo"
        im = a.pcolormesh(ds.lon, ds.lat, m, cmap=cmap, shading="auto",
                          vmin=-np.nanmax(abs(m)) if cmap == "RdBu_r" else None, vmax=np.nanmax(abs(m)) if cmap == "RdBu_r" else None)
        a.set_title(f"{v} annual mean ({UNITS[v]})"); a.set_aspect("equal"); fig.colorbar(im, ax=a, shrink=0.8)
    ws = np.hypot(ds.u10, ds.v10).mean("time")
    im = ax.flat[7].pcolormesh(ds.lon, ds.lat, ws, cmap="viridis", shading="auto")
    ax.flat[7].set_title("wind speed annual mean (m/s)"); ax.flat[7].set_aspect("equal"); fig.colorbar(im, ax=ax.flat[7], shrink=0.8)
    save(fig, "01_input_mean_maps.png")

    fig, ax = plt.subplots(2, 3, figsize=(16, 6.5), constrained_layout=True)
    for a, d in zip(ax.flat, [0, 50, 100, 200, 500, 1000]):
        m = ds.thetao.sel(depth=float(d)).mean("time")
        im = a.pcolormesh(ds.lon, ds.lat, m, cmap="turbo", shading="auto")
        a.set_title(f"temperature {d} m (annual mean, °C)"); a.set_aspect("equal"); fig.colorbar(im, ax=a, shrink=0.8)
    save(fig, "02_target_mean_maps.png")

    fig, ax = plt.subplots(1, 2, figsize=(14, 3.8), constrained_layout=True)
    for a, d in zip(ax, [100, 1000]):
        s = ds.thetao.sel(depth=float(d)).std("time")
        im = a.pcolormesh(ds.lon, ds.lat, s, cmap="magma", shading="auto")
        a.set_title(f"temperature std over 2021 at {d} m (°C)"); a.set_aspect("equal"); fig.colorbar(im, ax=a)
    save(fig, "03_target_variability_maps.png")

    # missingness
    fig, ax = plt.subplots(1, 3, figsize=(18, 3.8), constrained_layout=True)
    for a, v in zip(ax, ["sst", "sss", "uo"]):
        mf = np.where(ocean, np.isnan(ds[v].values).mean(0), np.nan)
        im = a.pcolormesh(ds.lon, ds.lat, mf, cmap="Reds", vmin=0, vmax=1, shading="auto")
        a.set_title(f"{v}: fraction of days missing (ocean only)"); a.set_aspect("equal"); fig.colorbar(im, ax=a)
    save(fig, "04_missingness_maps.png")
    S["missingness"] = {v: {"cells_with_any_missing": int((np.isnan(ds[v].values).any(0) & ocean).sum()),
                            "cells_always_missing": int((np.isnan(ds[v].values).all(0) & ocean).sum())} for v in INPUTS}

    # ------------------------------------------------------------ 3. temporal
    dom = {v: np.nanmean(ds[v].values[:, ocean], axis=1) for v in INPUTS}
    dom["wind_speed"] = np.nanmean(np.hypot(ds.u10.values, ds.v10.values)[:, ocean], axis=1)
    dom["T100"] = np.nanmean(ds.thetao.sel(depth=100.0).values[:, ocean], axis=1)
    t = pd.DatetimeIndex(ds.time.values)
    fig, ax = plt.subplots(2, 3, figsize=(16, 7), constrained_layout=True)
    for a, v in zip(ax.flat, ["sst", "sss", "sla", "wind_speed", "T100", "u10"]):
        a.plot(t, dom[v], lw=1)
        for sp, c in [("test", "tab:red"), ("buffer", "0.7")]:
            msk = split == sp
            a.scatter(t[msk], dom[v][msk], s=3, c=c, label=sp)
        a.set_title(f"domain mean {v}"); a.tick_params(axis="x", rotation=30)
    ax.flat[0].legend()
    save(fig, "05_domain_timeseries_with_splits.png")
    S["monthly_domain_means"] = {v: pd.Series(dom[v], index=t).groupby(t.month).mean().round(4).to_dict() for v in dom}

    # Hovmoller of T anomaly at 100 m along 10N (Arabian Sea + BoB)
    j = int(np.argmin(abs(ds.lat.values - 10.0)))
    hov = anom[:, list(DEPTHS).index(100.0), j, :]
    fig, a = plt.subplots(figsize=(10, 6), constrained_layout=True)
    im = a.pcolormesh(ds.lon, t, hov, cmap="RdBu_r", vmin=-4, vmax=4, shading="auto")
    a.set_xlabel("longitude"); a.set_title("Hovmöller: temperature anomaly vs climatology at 100 m along 10°N (°C)")
    fig.colorbar(im, ax=a)
    save(fig, "06_hovmoller_T100_anomaly_10N.png")

    # ------------------------------------------------------------ 4. depth / regional profiles
    fig, ax = plt.subplots(1, 3, figsize=(16, 6), constrained_layout=True)
    for r, c in [("arabian_sea", "tab:orange"), ("bay_of_bengal", "tab:blue")]:
        rm = region_mask(ds, r) & ocean
        prof = np.nanmean(ds.thetao.values[:, :, rm], axis=(0, 2))
        ax[0].plot(prof, DEPTHS, "o-", c=c, label=r)
        S.setdefault("regions", {})[r] = {"mean_profile": dict(zip([str(int(d)) for d in DEPTHS], np.round(prof, 3).tolist())),
                                          "sst_mean": float(np.nanmean(ds.sst.values[:, rm])), "sss_mean": float(np.nanmean(ds.sss.values[:, rm])),
                                          "ocean_cells": int(rm.sum())}
    ax[0].invert_yaxis(); ax[0].legend(); ax[0].set_title("mean profile by region"); ax[0].set_xlabel("°C"); ax[0].set_ylabel("depth (m)")
    seasons = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJAS": [6, 7, 8, 9], "ON": [10, 11]}
    for s, ms in seasons.items():
        tm = np.isin(month, ms)
        ax[1].plot(np.nanmean(ds.thetao.values[tm][:, :, ocean], axis=(0, 2)), DEPTHS, "o-", label=s)
    ax[1].invert_yaxis(); ax[1].legend(); ax[1].set_title("mean profile by season"); ax[1].set_xlabel("°C")
    abs_std = [S["target_by_depth"][str(int(d))]["std"] for d in DEPTHS]
    an_std = [S["anomaly_std_by_depth"][str(int(d))] for d in DEPTHS]
    ax[2].plot(abs_std, DEPTHS, "o-", label="absolute T (space+time)")
    ax[2].plot(an_std, DEPTHS, "s-", label="anomaly vs climatology")
    ax[2].invert_yaxis(); ax[2].legend(); ax[2].set_title("std by depth: what is left to learn"); ax[2].set_xlabel("°C")
    save(fig, "07_profiles_region_season_variance.png")

    # ------------------------------------------------------------ 5. relationships (TRAIN ONLY)
    tr = np.where(train)[0]
    yy, xx = np.where(ocean)
    n = 300_000
    ti = RNG.choice(tr, n); ci = RNG.integers(0, yy.size, n)
    yi, xi = yy[ci], xx[ci]
    feat = {v: ds[v].values[ti, yi, xi] for v in INPUTS}
    feat["wind_speed"] = np.hypot(feat["u10"], feat["v10"])
    feat["current_speed"] = np.hypot(feat["uo"], feat["vo"])
    feat["lat"] = ds.lat.values[yi]
    feat["lon"] = ds.lon.values[xi]
    doy = pd.DatetimeIndex(ds.time.values[ti]).dayofyear.values
    feat["sin_doy"], feat["cos_doy"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    F = pd.DataFrame(feat)
    Tabs = ds.thetao.values[ti, :, yi, xi]               # (n, 15)
    Tan = anom[ti, :, yi, xi]
    cm = F.corr(method="pearson")
    fig, a = plt.subplots(figsize=(9, 7.5), constrained_layout=True)
    im = a.imshow(cm, cmap="RdBu_r", vmin=-1, vmax=1); a.set_xticks(range(len(cm)), cm.columns, rotation=60); a.set_yticks(range(len(cm)), cm.columns)
    for i in range(len(cm)):
        for k in range(len(cm)):
            a.text(k, i, f"{cm.values[i, k]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im); a.set_title("input feature correlation (Pearson, train days, 300k samples)")
    save(fig, "08_feature_correlation_matrix.png")
    S["feature_corr_train"] = cm.round(3).to_dict()

    def corr_by_depth(target):
        out = np.full((F.shape[1], len(DEPTHS)), np.nan)
        for k in range(len(DEPTHS)):
            y = target[:, k]
            for i, c in enumerate(F.columns):
                x = F[c].values
                m = np.isfinite(x) & np.isfinite(y)
                if m.sum() > 1000:
                    out[i, k] = stats.spearmanr(x[m][:50_000], y[m][:50_000]).statistic
        return out

    ca, cn = corr_by_depth(Tabs), corr_by_depth(Tan)
    fig, ax = plt.subplots(1, 2, figsize=(16, 6), constrained_layout=True)
    for a, c, ttl in [(ax[0], ca, "absolute temperature"), (ax[1], cn, "temperature anomaly (vs climatology)")]:
        im = a.imshow(c, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        a.set_yticks(range(F.shape[1]), F.columns); a.set_xticks(range(len(DEPTHS)), [int(d) for d in DEPTHS], rotation=45)
        a.set_xlabel("depth (m)"); a.set_title(f"Spearman corr: feature vs {ttl} (train)")
        for i in range(c.shape[0]):
            for k in range(c.shape[1]):
                a.text(k, i, f"{c[i, k]:.2f}", ha="center", va="center", fontsize=6)
    fig.colorbar(im, ax=ax, shrink=0.8)
    save(fig, "09_feature_target_corr_by_depth.png")
    S["feature_target_spearman_train"] = {"absolute": {c: dict(zip([str(int(d)) for d in DEPTHS], np.round(ca[i], 3).tolist())) for i, c in enumerate(F.columns)},
                                          "anomaly": {c: dict(zip([str(int(d)) for d in DEPTHS], np.round(cn[i], 3).tolist())) for i, c in enumerate(F.columns)}}

    # depth-depth correlation + PCA (EOF) of anomaly profiles (complete profiles only, train)
    full = np.isfinite(Tan).all(1)
    A = Tan[full]
    dd = np.corrcoef(A.T)
    Z = (A - A.mean(0)) / A.std(0)
    ev = np.linalg.svd(Z, full_matrices=False)[1] ** 2
    evr = ev / ev.sum()
    fig, ax = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
    im = ax[0].imshow(dd, cmap="RdBu_r", vmin=-1, vmax=1)
    ax[0].set_xticks(range(15), [int(d) for d in DEPTHS], rotation=60); ax[0].set_yticks(range(15), [int(d) for d in DEPTHS])
    ax[0].set_title("depth-depth correlation of anomalies (train)"); fig.colorbar(im, ax=ax[0])
    ax[1].bar(range(1, 16), evr, label="per component"); ax[1].plot(range(1, 16), np.cumsum(evr), "o-k", label="cumulative")
    ax[1].axhline(0.9, ls=":", c="gray"); ax[1].set_xlabel("PCA component"); ax[1].set_title("PCA of standardised anomaly profiles (train)")
    ax[1].legend()
    save(fig, "10_depth_correlation_and_pca.png")
    S["pca_anomaly_profiles_train"] = {"n_profiles": int(full.sum()), "explained_variance_ratio": np.round(evr, 4).tolist(),
                                       "n_components_90pct": int(np.searchsorted(np.cumsum(evr), 0.90) + 1),
                                       "n_components_95pct": int(np.searchsorted(np.cumsum(evr), 0.95) + 1)}

    # distributions
    fig, ax = plt.subplots(2, 4, figsize=(18, 6.5), constrained_layout=True)
    for a, v in zip(ax.flat, INPUTS):
        x = ds[v].values[:, ocean].ravel()
        a.hist(x[np.isfinite(x)][::20], bins=80, color="tab:blue"); a.set_title(f"{v} ({UNITS[v]}), skew={S['inputs'][v]['skew']:.2f}")
    a = ax.flat[7]
    for d in [0, 100, 500]:
        x = ds.thetao.sel(depth=float(d)).values[:, ocean].ravel()
        a.hist(x[np.isfinite(x)][::20], bins=80, alpha=0.5, label=f"T {d} m")
    a.legend(); a.set_title("target distributions")
    save(fig, "11_distributions.png")

    (ROOT / "data" / "audit" / "eda_stats.json").write_text(json.dumps(S, indent=1, default=float), encoding="utf-8")
    print("EDA done ->", OUT.relative_to(ROOT))
    print("anomaly std by depth:", {k: round(v, 2) for k, v in S["anomaly_std_by_depth"].items()})
    print("PCA:", S["pca_anomaly_profiles_train"]["n_components_90pct"], "comps for 90%,", S["pca_anomaly_profiles_train"]["n_components_95pct"], "for 95%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
