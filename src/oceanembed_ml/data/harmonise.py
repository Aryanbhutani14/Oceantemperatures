"""Phase 2 — harmonise every raw source onto the canonical grid.

Pipeline per source (docs/phase2_harmonisation.md):
  1 read metadata        2 rename to canonical names     3 explicit unit conversion
  4 coordinates sorted ascending, longitudes in [-180,180)
  5 spatial: ConservativeRegridder (identity / exact block mean / area-weighted)
  6 temporal: UTC calendar day (hourly -> daily mean, all 24 hours required)
  7 vertical (3-D only): linear interpolation to the 15 PS depths, no extrapolation
  8 land/lake masking with the canonical ocean mask (from the target)
  9 physical range QC: impossible values -> NaN, counted (never silent)
Output: data/interim/<source>.nc (float32, zlib) + data/audit/harmonisation_qc.json

Usage:
    python scripts/harmonise/harmonise.py --source glorys      # must run first (builds masks)
    python scripts/harmonise/harmonise.py --source all
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from oceanembed_ml.config import ROOT
from oceanembed_ml.grid import DEPTHS, LAT, LON, ConservativeRegridder, vertical_interp  # noqa: E402

warnings.filterwarnings("ignore")
RAW, INTERIM = ROOT / "data" / "raw", ROOT / "data" / "interim"
QC_PATH = ROOT / "data" / "audit" / "harmonisation_qc.json"

# Physical plausibility ranges (canonical units). Values outside -> NaN + counted.
# Upper T bound 38 degC: Persian Gulf summer SST is genuinely 35-36.7 degC (Phase 2 check).
RANGES = {"thetao": (-2.5, 38.0), "sst": (10.0, 38.0), "sss": (25.0, 42.0), "sla": (-1.5, 1.5),
          "uo": (-3.0, 3.0), "vo": (-3.0, 3.0), "u10": (-40.0, 40.0), "v10": (-40.0, 40.0)}
UNITS = {"thetao": "degC", "sst": "degC", "sss": "PSU", "sla": "m", "uo": "m s-1", "vo": "m s-1",
         "u10": "m s-1", "v10": "m s-1"}
LONG = {"thetao": "Sea water potential temperature", "sst": "Sea surface temperature (foundation, OSTIA)",
        "sss": "Sea surface salinity (practical salinity)", "sla": "Sea level anomaly",
        "uo": "Eastward surface geostrophic current", "vo": "Northward surface geostrophic current",
        "u10": "Eastward 10 m wind", "v10": "Northward 10 m wind"}


def _std_coords(ds: xr.Dataset) -> xr.Dataset:
    ren = {k: v for k, v in {"latitude": "lat", "longitude": "lon"}.items() if k in ds.dims or k in ds.coords}
    ds = ds.rename(ren)
    if float(ds.lon.max()) >= 180:
        ds = ds.assign_coords(lon=((ds.lon + 180) % 360) - 180)
    return ds.sortby("lat").sortby("lon")


def _open_months(src: str) -> list[Path]:
    files = sorted(p for p in (RAW / src).glob("*.nc") if not p.name.endswith(".part.nc"))
    if not files:
        raise FileNotFoundError(f"no raw files for {src}")
    return files


def _check_units(da: xr.DataArray, allowed: tuple) -> None:
    u = da.attrs.get("units")
    if u not in allowed:
        raise ValueError(f"{da.name}: units '{u}' not in allowed {allowed} — refusing to convert")


def _daily_index(t) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(t).floor("D")


def _regrid_stack(rg: ConservativeRegridder, arr: np.ndarray) -> np.ndarray:
    return rg(arr)


def _qc(name: str, arr: np.ndarray, qc: dict, ocean: np.ndarray | None) -> np.ndarray:
    lo, hi = RANGES[name]
    finite = np.isfinite(arr)
    bad = finite & ((arr < lo) | (arr > hi))
    rec = {"range": [lo, hi], "n_out_of_range_set_nan": int(bad.sum())}
    arr = np.where(bad, np.nan, arr).astype("float32")
    if ocean is not None:
        o = np.broadcast_to(ocean, arr.shape)
        rec["valid_frac_over_ocean"] = round(float(np.isfinite(arr)[o].mean()), 5)
        rec["n_ocean_cells_never_valid"] = int((~np.isfinite(arr).any(axis=0) & ocean).sum()) if arr.ndim == 3 else None
    v = arr[np.isfinite(arr)]
    rec.update({"min": float(v.min()), "max": float(v.max()), "mean": float(v.mean()),
                "p01": float(np.percentile(v, 1)), "p99": float(np.percentile(v, 99))})
    qc[name] = rec
    return arr


def _write(name: str, data_vars: dict, coords: dict, attrs: dict) -> Path:
    INTERIM.mkdir(parents=True, exist_ok=True)
    ds = xr.Dataset(data_vars, coords=coords, attrs=attrs)
    for v in data_vars:
        ds[v].attrs.update({"units": UNITS.get(v, ""), "long_name": LONG.get(v, v)})
    ds["lat"].attrs.update(units="degrees_north", note="cell centres, canonical 0.25 deg grid")
    ds["lon"].attrs.update(units="degrees_east", note="cell centres, canonical 0.25 deg grid")
    out = INTERIM / f"{name}.nc"
    enc = {v: {"zlib": True, "complevel": 4, "dtype": "float32"} for v in data_vars}
    tmp = out.with_suffix(".part.nc")
    ds.to_netcdf(tmp, encoding=enc)
    tmp.replace(out)
    return out


def _attrs(source: str, operator: str, extra: dict | None = None) -> dict:
    a = {"source_raw_dir": f"data/raw/{source}", "spatial_operator": operator,
         "time_convention": "UTC calendar day", "grid": "canonical 0.25 deg, 5-30N 45-105E (cell centres)",
         "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "history": "harmonised by scripts/harmonise/harmonise.py (OceanEmbed-ML Phase 2)"}
    a.update(extra or {})
    return a


def load_masks() -> xr.Dataset:
    p = INTERIM / "masks.nc"
    if not p.exists():
        raise FileNotFoundError("data/interim/masks.nc missing — run --source glorys first")
    return xr.open_dataset(p).load()


# --------------------------------------------------------------------------- sources
def do_glorys(qc: dict) -> None:
    """Target: exact selection (identity) + vertical interpolation; also builds masks."""
    parts, times = [], []
    rg = None
    for f in _open_months("glorys"):
        ds = _std_coords(xr.open_dataset(f))
        da = ds["thetao_glor"]
        _check_units(da, ("degrees_C",))
        if rg is None:
            rg = ConservativeRegridder(ds.lat.values, ds.lon.values)
            # exact-selection check: weights must be one-to-one
            assert np.allclose((rg.Wlat > 0).sum(1), 1) and np.allclose((rg.Wlon > 0).sum(1), 1), "GLORYS grid not aligned"
            zn = ds.depth.values.astype("float64")
        h = rg(da.values)                                   # (t, z, 101, 241)
        parts.append(vertical_interp(h, zn, DEPTHS, axis=1))  # (t, 15, 101, 241)
        times.append(_daily_index(ds.time.values))
        print(f"  glorys {f.name}", flush=True)
    th = np.concatenate(parts)
    t = np.concatenate(times)
    assert pd.Index(t).is_unique and pd.Index(t).is_monotonic_increasing
    # masks from the target (static: valid on every day)
    fin = np.isfinite(th)
    ocean = fin[:, 0].all(axis=0)
    depth_valid = fin.all(axis=0)                           # (15, lat, lon)
    flick = (fin[:, 0].any(axis=0) & ~ocean).sum()
    deepest = np.where(depth_valid.any(0), DEPTHS[np.clip(depth_valid.sum(0) - 1, 0, None)], np.nan)
    th = np.where(ocean[None, None], th, np.nan)
    th = _qc("thetao", th, qc, None)
    qc["thetao"]["n_valid_per_depth"] = [int(depth_valid[k].sum()) for k in range(len(DEPTHS))]
    qc["masks"] = {"n_ocean_cells": int(ocean.sum()), "n_cells_total": int(ocean.size),
                   "n_cells_ocean_on_some_days_only": int(flick),
                   "n_valid_cells_per_depth": {str(int(d)): int(depth_valid[k].sum()) for k, d in enumerate(DEPTHS)}}
    _write("glorys_thetao", {"thetao": (("time", "depth", "lat", "lon"), th)},
           {"time": t, "depth": DEPTHS, "lat": LAT, "lon": LON},
           _attrs("glorys", "exact selection (identity weights) + linear vertical interpolation; 0 m = shallowest level (0.506 m)",
                  {"product": "GLOBAL_MULTIYEAR_PHY_ENS_001_031 / cmems_mod_glo_phy-all_my_0.25deg_P1D-m (thetao_glor)"}))
    m = xr.Dataset({"ocean_mask": (("lat", "lon"), ocean.astype("int8")),
                    "depth_valid": (("depth", "lat", "lon"), depth_valid.astype("int8")),
                    "deepest_valid_depth": (("lat", "lon"), deepest.astype("float32"))},
                   coords={"depth": DEPTHS, "lat": LAT, "lon": LON},
                   attrs=_attrs("glorys", "derived from harmonised GLORYS", {"definition": "ocean_mask = target finite at 0 m on every day; depth_valid = finite at that depth on every day"}))
    m.to_netcdf(INTERIM / "masks.nc")
    print(f"  masks: {int(ocean.sum())} ocean cells of {ocean.size}", flush=True)


def do_glorys_clim(qc: dict) -> None:
    ds = _std_coords(xr.open_dataset(RAW / "glorys_clim" / "climatology_monthly.nc"))
    da = ds["thetao"]
    _check_units(da, ("degrees_C",))
    rg = ConservativeRegridder(ds.lat.values, ds.lon.values)
    h = rg(da.values)
    clim = vertical_interp(h, ds.depth.values.astype("float64"), DEPTHS, axis=1)
    ocean = load_masks().ocean_mask.values.astype(bool)
    clim = np.where(ocean[None, None], clim, np.nan)
    clim = _qc("thetao", clim, qc, None)
    months = pd.DatetimeIndex(ds.time.values).month.values
    assert sorted(months) == list(range(1, 13))
    _write("glorys_clim", {"thetao_clim": (("month", "depth", "lat", "lon"), clim)},
           {"month": months, "depth": DEPTHS, "lat": LAT, "lon": LON},
           _attrs("glorys_clim", "area-weighted conservative (= exact 3x3 block mean, nested grids) + linear vertical interpolation",
                  {"product": "GLOBAL_MULTIYEAR_PHY_001_030 / cmems_mod_glo_phy_my_0.083deg-climatology_P1M-m"}))


def _surface(src: str, mapping: dict, convert: dict, qc: dict, op_note: str, product: str,
             hourly: bool = False, squeeze_depth: bool = False) -> None:
    ocean = load_masks().ocean_mask.values.astype(bool)
    out = {k: [] for k in mapping}
    times, rg = [], None
    for f in _open_months(src):
        ds = _std_coords(xr.open_dataset(f))
        if squeeze_depth and "depth" in ds.dims:
            ds = ds.isel(depth=0, drop=True)
        if rg is None:
            rg = ConservativeRegridder(ds.lat.values, ds.lon.values)
        if hourly:
            day = _daily_index(ds.time.values)
            udays = day.unique()
        for canon, native in mapping.items():
            da = ds[native]
            allowed, fn = convert[canon]
            _check_units(da, allowed)
            x = da.values.astype("float64")
            if hourly:
                daily = []
                for d in udays:
                    sel = x[day == d]
                    if sel.shape[0] != 24:
                        raise ValueError(f"{f.name} {d.date()}: {sel.shape[0]} hours (need 24)")
                    m = sel.mean(axis=0)
                    m[~np.isfinite(sel).all(axis=0)] = np.nan  # all 24 hours required
                    daily.append(m)
                x = np.stack(daily)
            out[canon].append(rg(fn(x)))
        times.append(udays if hourly else _daily_index(ds.time.values))
        print(f"  {src} {f.name}", flush=True)
    t = np.concatenate(times)
    assert pd.Index(t).is_unique and pd.Index(t).is_monotonic_increasing and len(t) == 365, len(t)
    data = {}
    for canon in mapping:
        arr = np.concatenate(out[canon])
        land_vals = int((np.isfinite(arr) & ~ocean[None]).sum())
        arr = np.where(ocean[None], arr, np.nan)                     # land/lake masking
        arr = _qc(canon, arr, qc, ocean)
        qc[canon]["n_land_or_lake_values_masked"] = land_vals
        data[canon] = (("time", "lat", "lon"), arr)
    _write(src, data, {"time": t, "lat": LAT, "lon": LON}, _attrs(src, op_note, {"product": product}))


def do_sst(qc):
    _surface("sst", {"sst": "analysed_sst"}, {"sst": (("kelvin", "K"), lambda x: x - 273.15)}, qc,
             "area-weighted conservative from 0.05 deg (edges not nested: partial-cell weights); K -> degC (-273.15)",
             "SST_GLO_SST_L4_REP_OBSERVATIONS_010_011 / METOFFICE-GLO-SST-L4-REP-OBS-SST")


def do_sss(qc):
    _surface("sss", {"sss": "sos"}, {"sss": ((".001", "1e-3", "PSU", "psu", "0.001"), lambda x: x)}, qc,
             "area-weighted conservative (= exact 2x2 block mean, nested grids); practical salinity labelled PSU",
             "MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013 / cmems_obs-mob_glo_phy-sss_my_multi_P1D", squeeze_depth=True)


def do_ssh(qc):
    ident = lambda x: x  # noqa: E731
    _surface("ssh", {"sla": "sla", "uo": "ugos", "vo": "vgos"},
             {"sla": (("m",), ident), "uo": (("m/s", "m s-1"), ident), "vo": (("m/s", "m s-1"), ident)}, qc,
             "area-weighted conservative (= exact 2x2 block mean, nested grids)",
             "SEALEVEL_GLO_PHY_L4_MY_008_047 / cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D (uo,vo = geostrophic ugos,vgos)")


def do_winds(qc):
    ident = lambda x: x  # noqa: E731
    _surface("winds", {"u10": "eastward_wind", "v10": "northward_wind"},
             {"u10": (("m s-1", "m/s"), ident), "v10": (("m s-1", "m/s"), ident)}, qc,
             "daily mean of 24 hourly fields (all required), then area-weighted conservative (= exact 2x2 block mean)",
             "WIND_GLO_PHY_L4_MY_012_006 / cmems_obs-wind_glo_phy_my_l4_0.125deg_PT1H", hourly=True)


ORDER = {"glorys": do_glorys, "glorys_clim": do_glorys_clim, "sst": do_sst, "sss": do_sss, "ssh": do_ssh, "winds": do_winds}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=list(ORDER) + ["all"])
    a = ap.parse_args()
    qc_all = json.loads(QC_PATH.read_text(encoding="utf-8")) if QC_PATH.exists() else {}
    for s in (list(ORDER) if a.source == "all" else [a.source]):
        print(f"[{s}]", flush=True)
        qc: dict = {}
        ORDER[s](qc)
        qc_all[s] = qc
        QC_PATH.write_text(json.dumps(qc_all, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
