"""Phase 3 — outlier screening: measurement error vs real ocean event.

Flag-only (nothing is removed). For SST, SLA and SSS at every ocean cell:
  * robust z-score vs the cell's own 2021 median:  z = (x - median) / (1.4826 * MAD)
  * temporal spike: |x_t - median(x_{t-3..t+3})| > 6 * 1.4826 * MAD_cell
Flagged values are then compared with 2021 North Indian Ocean cyclone tracks
(IBTrACS): a flag within 300 km and +-7 days of a storm position is labelled
"probable real event" (e.g. cyclone cold wake). Physical-range errors were
already handled in Phase 2.

Outputs: data/audit/outlier_report.json, reports/figures/phase3/12_outliers_cyclones.png
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
from scipy.ndimage import median_filter  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
Z = 6.0


def load_tracks() -> pd.DataFrame:
    f = next((ROOT / "data" / "raw" / "ibtracs").glob("*.csv"))
    df = pd.read_csv(f, skiprows=[1], usecols=["SID", "NAME", "ISO_TIME", "LAT", "LON", "USA_WIND", "WMO_WIND"], low_memory=False)
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], errors="coerce")
    df = df[(df.ISO_TIME.dt.year == 2021)].copy()
    df["LAT"] = pd.to_numeric(df.LAT, errors="coerce"); df["LON"] = pd.to_numeric(df.LON, errors="coerce")
    return df.dropna(subset=["LAT", "LON"])


def near_track(t, lat, lon, tracks, km=300.0, days=7):
    tt = tracks.ISO_TIME.values.astype("datetime64[D]")
    out = np.zeros(t.size, bool)
    for i in range(t.size):
        dt = np.abs((tt - t[i]).astype(int)) <= days
        if not dt.any():
            continue
        la, lo = tracks.LAT.values[dt], tracks.LON.values[dt]
        d = 6371 * np.arccos(np.clip(np.sin(np.radians(lat[i])) * np.sin(np.radians(la)) +
                                     np.cos(np.radians(lat[i])) * np.cos(np.radians(la)) * np.cos(np.radians(lon[i] - lo)), -1, 1))
        out[i] = (d <= km).any()
    return out


def main() -> int:
    ds = xr.open_dataset(ROOT / "data" / "processed" / "cube.nc")
    ocean = ds.ocean_mask.values.astype(bool)
    tracks = load_tracks()
    storms = tracks.groupby("NAME").agg(start=("ISO_TIME", "min"), end=("ISO_TIME", "max"),
                                        max_wind_kt=("USA_WIND", lambda s: pd.to_numeric(s, errors="coerce").max())).reset_index()
    rep = {"z_threshold": Z, "storms_2021": storms.astype(str).to_dict("records"), "variables": {}}
    times = ds.time.values.astype("datetime64[D]")
    for v in ["sst", "sla", "sss"]:
        x = ds[v].values
        med = np.nanmedian(x, axis=0)
        mad = 1.4826 * np.nanmedian(np.abs(x - med), axis=0)
        mad = np.where(mad > 0, mad, np.nan)
        z = (x - med) / mad
        robust = np.abs(z) > Z
        local = median_filter(np.nan_to_num(x, nan=np.nanmean(x)), size=(7, 1, 1), mode="nearest")
        spike = np.abs(x - local) / mad > Z
        flag = (robust | spike) & ocean[None] & np.isfinite(x)
        ti, yi, xi = np.where(flag)
        lat, lon = ds.lat.values[yi], ds.lon.values[xi]
        # cyclone association (on a subsample if very many)
        idx = np.arange(ti.size)
        if idx.size > 20000:
            idx = np.random.default_rng(0).choice(idx, 20000, replace=False)
        assoc = near_track(times[ti[idx]], lat[idx], lon[idx], tracks)
        rep["variables"][v] = {"n_flagged": int(flag.sum()), "frac_of_ocean_values": float(flag.sum() / (np.isfinite(x) & ocean[None]).sum()),
                               "n_robust_z": int((robust & ocean[None]).sum()), "n_temporal_spike": int((spike & ocean[None]).sum()),
                               "frac_flags_near_cyclone_300km_7d": float(assoc.mean()) if assoc.size else None,
                               "flags_by_month": pd.Series(pd.DatetimeIndex(times[ti]).month).value_counts().sort_index().to_dict(),
                               "action": "kept (flag only)"}
        if v == "sst":
            sst_flag_map = flag.sum(0)
    # baseline: how often a RANDOM ocean value is near a cyclone (to judge the association)
    yy, xx = np.where(ocean)
    rng = np.random.default_rng(1)
    k = 20000
    r_t = times[rng.integers(0, times.size, k)]; r_c = rng.integers(0, yy.size, k)
    rep["random_ocean_value_frac_near_cyclone"] = float(near_track(r_t, ds.lat.values[yy[r_c]], ds.lon.values[xx[r_c]], tracks).mean())

    fig, a = plt.subplots(figsize=(11, 5), constrained_layout=True)
    im = a.pcolormesh(ds.lon, ds.lat, np.where(ocean, sst_flag_map, np.nan), cmap="Reds", shading="auto")
    for name, g in tracks.groupby("NAME"):
        a.plot(g.LON, g.LAT, "-", lw=1.5, label=name)
    a.set_xlim(45, 105); a.set_ylim(5, 30); a.set_aspect("equal"); a.legend(fontsize=7, ncol=2, loc="lower left")
    a.set_title("SST flagged days per cell (robust z / spike > 6) with 2021 cyclone tracks")
    fig.colorbar(im, ax=a, label="flagged days")
    fig.savefig(ROOT / "reports" / "figures" / "phase3" / "12_outliers_cyclones.png", dpi=110)
    (ROOT / "data" / "audit" / "outlier_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(json.dumps({v: {k: r[k] for k in ("n_flagged", "frac_of_ocean_values", "frac_flags_near_cyclone_300km_7d")} for v, r in rep["variables"].items()}, indent=1))
    print("random baseline near-cyclone fraction:", round(rep["random_ocean_value_frac_near_cyclone"], 4))
    print(storms[["NAME", "start", "max_wind_kt"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
