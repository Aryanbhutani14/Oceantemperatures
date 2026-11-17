"""Phase 2 — sanity figures: native vs harmonised fields, masks, mean profile.

Writes PNGs to reports/figures/phase2/. Values plotted are read from the raw
and interim files; nothing is typed by hand.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import xarray as xr  # noqa: E402

from oceanembed_ml.config import ROOT
from oceanembed_ml.grid import DEPTHS  # noqa: E402

warnings.filterwarnings("ignore")
RAW, INTERIM = ROOT / "data" / "raw", ROOT / "data" / "interim"
OUT = ROOT / "reports" / "figures" / "phase2"
OUT.mkdir(parents=True, exist_ok=True)
DATE = "2021-08-15"
EXT = [44.5, 105.5, 4.5, 30.5]


def _native(src, var, conv=lambda x: x, hourly=False, depth=None):
    f = RAW / src / "2021-08.nc"
    ds = xr.open_dataset(f)
    lat = "latitude" if "latitude" in ds.dims else "lat"
    lon = "longitude" if "longitude" in ds.dims else "lon"
    da = ds[var]
    if hourly:
        da = da.sel(time=DATE).mean("time")
    else:
        da = da.sel(time=DATE, method="nearest")
    if "depth" in da.dims:
        da = da.isel(depth=0) if depth is None else da.sel(depth=depth, method="nearest")
    return conv(da.sortby(lat).sortby(lon)), lat, lon


def compare(src, native_var, file, var, label, cmap, conv=lambda x: x, hourly=False, depth=None, harm_depth=None):
    nat, la, lo = _native(src, native_var, conv, hourly, depth)
    h = xr.open_dataset(INTERIM / file)[var].sel(time=DATE)
    if harm_depth is not None:
        h = h.sel(depth=harm_depth)
    vmin, vmax = np.nanpercentile(h.values, [2, 98])
    fig, ax = plt.subplots(1, 2, figsize=(13, 3.6), constrained_layout=True)
    ax[0].pcolormesh(nat[lo], nat[la], nat.values, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
    ax[0].set_title(f"native {src} ({abs(float(nat[la][1] - nat[la][0])):.3f}°)")
    im = ax[1].pcolormesh(h.lon, h.lat, h.values, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
    ax[1].set_title("harmonised (canonical 0.25°, ocean mask)")
    for a in ax:
        a.set_xlim(EXT[:2]); a.set_ylim(EXT[2:]); a.set_aspect("equal")
    fig.colorbar(im, ax=ax, shrink=0.9, label=label)
    fig.suptitle(f"{label} — {DATE}")
    fig.savefig(OUT / f"compare_{var}.png", dpi=110)
    plt.close(fig)


def masks_and_profile():
    m = xr.open_dataset(INTERIM / "masks.nc")
    fig, ax = plt.subplots(1, 2, figsize=(13, 3.6), constrained_layout=True)
    ax[0].pcolormesh(m.lon, m.lat, m.ocean_mask, cmap="Blues", shading="auto")
    ax[0].set_title(f"ocean mask: {int(m.ocean_mask.sum())} ocean cells of {m.ocean_mask.size}")
    im = ax[1].pcolormesh(m.lon, m.lat, m.deepest_valid_depth, cmap="viridis_r", shading="auto")
    ax[1].set_title("deepest valid standard depth (m)")
    fig.colorbar(im, ax=ax[1])
    for a in ax:
        a.set_aspect("equal")
    fig.savefig(OUT / "masks.png", dpi=110)
    plt.close(fig)

    th = xr.open_dataset(INTERIM / "glorys_thetao.nc").thetao
    cl = xr.open_dataset(INTERIM / "glorys_clim.nc").thetao_clim
    mean = th.mean(("time", "lat", "lon")).values
    std = th.std(("time", "lat", "lon")).values
    fig, ax = plt.subplots(1, 2, figsize=(9, 5), constrained_layout=True)
    ax[0].plot(mean, DEPTHS, "o-", label="GLORYS 2021 (harmonised)")
    ax[0].fill_betweenx(DEPTHS, mean - std, mean + std, alpha=0.2)
    ax[0].plot(cl.mean(("month", "lat", "lon")).values, DEPTHS, "s--", label="GLORYS12 climatology")
    ax[0].invert_yaxis(); ax[0].set_xlabel("temperature (°C)"); ax[0].set_ylabel("depth (m)"); ax[0].legend()
    ax[0].set_title("domain-mean profile ±1σ")
    ax[1].plot(std, DEPTHS, "o-"); ax[1].invert_yaxis(); ax[1].set_xlabel("std (°C)")
    ax[1].set_title("variability by depth")
    fig.savefig(OUT / "mean_profile.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    masks_and_profile()
    compare("glorys", "thetao_glor", "glorys_thetao.nc", "thetao", "Temperature 100 m (°C)", "turbo", depth=100, harm_depth=100.0)
    compare("sst", "analysed_sst", "sst.nc", "sst", "SST (°C)", "turbo", conv=lambda x: x - 273.15)
    compare("sss", "sos", "sss.nc", "sss", "SSS (PSU)", "viridis")
    compare("ssh", "sla", "ssh.nc", "sla", "SLA (m)", "RdBu_r")
    if (INTERIM / "winds.nc").exists():
        compare("winds", "eastward_wind", "winds.nc", "u10", "U10 wind (m/s)", "RdBu_r", hourly=True)
    print("figures ->", OUT.relative_to(ROOT))
