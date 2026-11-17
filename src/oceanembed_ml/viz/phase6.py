"""Phase 6 figures: maps, cyclone TCHP, ARGO validation, indicators, daily skill."""
from __future__ import annotations

import json
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

from oceanembed_ml.config import FIGURES, FINAL, ROOT  # noqa: E402
from oceanembed_ml.eda.outliers import load_tracks  # noqa: E402
from oceanembed_ml.grid import DEPTHS  # noqa: E402

warnings.filterwarnings("ignore")
OUT = FIGURES / "phase6"
RES = ROOT / "results" / "phase6"
DZ = [int(d) for d in DEPTHS]


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=110)
    plt.close(fig)


def _track(ax, tracks, name, date=None, days=4):
    g = tracks[tracks.NAME.str.contains(name, case=False)]
    if date is not None:
        g = g[(g.ISO_TIME >= pd.Timestamp(date) - pd.Timedelta(days=days)) & (g.ISO_TIME <= pd.Timestamp(date) + pd.Timedelta(days=days))]
    ax.plot(g.LON, g.LAT, "k-", lw=1.5)
    if date is not None:
        now = g.iloc[(g.ISO_TIME - pd.Timestamp(date)).abs().argsort()[:1]]
        ax.plot(now.LON, now.LAT, "k*", ms=12)


def maps(pr, tracks):
    day = "2021-05-15"
    p, g = pr.pred.sel(time=day, depth=100.0), pr.glorys.sel(time=day, depth=100.0)
    vmin, vmax = np.nanpercentile(g, [2, 98])
    fig, ax = plt.subplots(1, 3, figsize=(19, 4.6), constrained_layout=True)
    for a, f, t in [(ax[0], g, "GLORYS (truth)"), (ax[1], p, "ML prediction (from surface data only)")]:
        im = a.pcolormesh(pr.lon, pr.lat, f, cmap="turbo", vmin=vmin, vmax=vmax, shading="auto"); a.set_title(f"{t}: T at 100 m, {day}")
    fig.colorbar(im, ax=ax[:2], shrink=0.85, label="°C")
    im = ax[2].pcolormesh(pr.lon, pr.lat, p - g, cmap="RdBu_r", vmin=-3, vmax=3, shading="auto")
    rm = float(np.sqrt(np.nanmean((p - g) ** 2)))
    ax[2].set_title(f"error (prediction − truth), RMSE {rm:.2f} °C"); fig.colorbar(im, ax=ax[2], shrink=0.85, label="°C")
    for a in ax:
        a.set_aspect("equal"); _track(a, tracks, "TAUKTAE", day)
    _save(fig, "01_map_T100_tauktae.png")

    fig, ax = plt.subplots(1, 3, figsize=(19, 4.6), constrained_layout=True)
    for a, d in zip(ax, [0.0, 100.0, 300.0]):
        e = pr.pred.sel(depth=d) - pr.glorys.sel(depth=d)
        im = a.pcolormesh(pr.lon, pr.lat, np.sqrt((e**2).mean("time")), cmap="magma_r", shading="auto",
                          vmax=float(np.nanpercentile(np.sqrt((e**2).mean("time")), 98)))
        a.set_title(f"RMSE over all 120 test days at {int(d)} m"); a.set_aspect("equal"); fig.colorbar(im, ax=a, shrink=0.85, label="°C")
    _save(fig, "02_map_rmse_test_period.png")


def cyclone_tchp(ind, tracks):
    cases = [("2021-05-14", "TAUKTAE"), ("2021-05-24", "YAAS")]
    fig, ax = plt.subplots(2, 3, figsize=(19, 8.5), constrained_layout=True)
    for r, (day, name) in enumerate(cases):
        for c, (src, t) in enumerate([("glorys", "GLORYS (truth)"), ("pred", "ML prediction"), ("clim", "climatology")]):
            f = ind[f"TCHP_{src}"].sel(time=day)
            im = ax[r, c].pcolormesh(ind.lon, ind.lat, f, cmap="YlOrRd", vmin=0, vmax=150, shading="auto")
            ax[r, c].set_title(f"{name} {day}: TCHP, {t}"); ax[r, c].set_aspect("equal")
            _track(ax[r, c], tracks, name, day, days=6)
    fig.colorbar(im, ax=ax, shrink=0.6, label="TCHP (kJ cm⁻²)")
    _save(fig, "03_cyclone_tchp.png")


def argo_figs(tracks):
    v = json.loads((RES / "argo_validation.json").read_text())
    df = pd.read_parquet(FINAL / "argo_matchups.parquet")
    fig, ax = plt.subplots(1, 3, figsize=(19, 6), constrained_layout=True)
    for s, c, lab in [("clim", "gray", "climatology"), ("pred", "tab:red", "ML model"), ("glorys", "tab:blue", "GLORYS (assimilates ARGO; ceiling)")]:
        ax[0].plot([v["per_depth"][str(d)][s].get("rmse", np.nan) for d in DZ], DZ, "o-", c=c, label=lab)
        ax[1].plot([v["per_depth"][str(d)][s].get("bias", np.nan) for d in DZ], DZ, "o-", c=c, label=lab)
    for a, t in zip(ax[:2], ["RMSE vs ARGO (°C)", "bias vs ARGO (°C, prediction − ARGO)"]):
        a.invert_yaxis(); a.grid(alpha=0.3); a.set_title(t); a.set_ylabel("depth (m)")
    ax[1].axvline(0, c="k", lw=0.8); ax[0].legend()
    A = np.concatenate([df[f"argo_d{k:02d}"] for k in range(15)]); P = np.concatenate([df[f"pred_d{k:02d}"] for k in range(15)])
    Dd = np.repeat(DZ, len(df))
    m = np.isfinite(A) & np.isfinite(P)
    sc = ax[2].scatter(A[m], P[m], c=Dd[m], s=3, cmap="viridis_r", alpha=0.5)
    ax[2].plot([5, 32], [5, 32], "k:"); fig.colorbar(sc, ax=ax[2], label="depth (m)")
    o = v["overall"]["pred"]
    ax[2].set_title(f"ML vs ARGO: {v['n_matchups_cell_days']} profiles, {v['n_floats']} floats\nRMSE {o['rmse']:.2f} °C, r {o['r']:.3f}")
    ax[2].set_xlabel("ARGO potential temperature (°C)"); ax[2].set_ylabel("ML prediction (°C)")
    _save(fig, "04_argo_validation.png")

    fig, a = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    a.scatter(df.lon, df.lat, s=8, c=pd.to_datetime(df.time).dt.month, cmap="tab10")
    a.set_xlim(45, 105); a.set_ylim(5, 30); a.set_aspect("equal"); a.set_title("ARGO matchups on test days (colour = month)")
    _save(fig, "05_argo_locations.png")


def indicator_figs(ind):
    v = json.loads((RES / "indicators.json").read_text())
    names = ["D20", "D26", "TCHP", "MLD", "OHC300"]
    fig, ax = plt.subplots(1, 5, figsize=(24, 4.8), constrained_layout=True)
    for a, n in zip(ax, names):
        t = ind[f"{n}_glorys"].values.ravel(); p = ind[f"{n}_pred"].values.ravel()
        m = np.isfinite(t) & np.isfinite(p)
        a.hexbin(t[m], p[m], gridsize=60, bins="log", cmap="Blues")
        lo, hi = np.percentile(t[m], [0.5, 99.5]); a.plot([lo, hi], [lo, hi], "r:")
        a.set_xlim(lo, hi); a.set_ylim(lo, hi)
        mv, cv = v[n]["model_vs_glorys"], v[n]["clim_vs_glorys"]
        a.set_title(f"{n} ({v[n]['units']})\nML RMSE {mv['rmse']:.2f}, r {mv['r']:.2f} | clim RMSE {cv['rmse']:.2f}", fontsize=9)
        a.set_xlabel("GLORYS"); a.set_ylabel("ML")
    _save(fig, "06_indicator_scatter.png")


def daily_skill(pr, tracks):
    t = pd.DatetimeIndex(pr.time.values)
    fig, a = plt.subplots(figsize=(13, 4), constrained_layout=True)
    for d, c in [(0.0, "tab:orange"), (100.0, "tab:red"), (300.0, "tab:blue")]:
        e = pr.pred.sel(depth=d) - pr.glorys.sel(depth=d)
        ec = pr.clim.sel(depth=d) - pr.glorys.sel(depth=d)
        a.plot(t, np.sqrt((e**2).mean(("lat", "lon"))), "o-", ms=2, c=c, label=f"ML {int(d)} m")
        a.plot(t, np.sqrt((ec**2).mean(("lat", "lon"))), ":", c=c, label=f"climatology {int(d)} m")
    for name, s, e in [("Tauktae", "2021-05-14", "2021-05-19"), ("Yaas", "2021-05-23", "2021-05-28")]:
        a.axvspan(pd.Timestamp(s), pd.Timestamp(e), color="gray", alpha=0.2); a.text(pd.Timestamp(s), a.get_ylim()[1] * 0.95, name, fontsize=8)
    a.set_ylabel("domain RMSE (°C)"); a.set_title("Daily error on test days (gaps = training months)"); a.legend(ncol=3, fontsize=8)
    _save(fig, "07_daily_rmse.png")


def main():
    pr = xr.open_dataset(FINAL / "predictions" / "test_predictions.nc").load()
    ind = xr.open_dataset(FINAL / "predictions" / "test_indicators.nc").load()
    tracks = load_tracks()
    maps(pr, tracks); cyclone_tchp(ind, tracks); argo_figs(tracks); indicator_figs(ind); daily_skill(pr, tracks)
    print("figures ->", OUT)


if __name__ == "__main__":
    main()
