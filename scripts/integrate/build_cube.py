"""Phase 3 — integrate all harmonised sources into one data cube.

Joins data/interim/*.nc with an EXACT coordinate join (any mismatch in time,
lat, lon or depth raises an error instead of silently aligning), then adds the
day-level split labels from configs/datasets.yaml (decision D-008):

    split = "test"   for days in test months (Feb, May, Aug, Nov)
            "buffer" for train-month days within `buffer_days` of a test month
            "train"  otherwise

Output: data/processed/cube.nc
    inputs  sst, sss, sla, uo, vo, u10, v10          (time, lat, lon)
    target  thetao                                   (time, depth, lat, lon)
    clim    thetao_clim                              (month, depth, lat, lon)
    masks   ocean_mask, depth_valid, deepest_valid_depth
    labels  split (time), month (time)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

ROOT = Path(__file__).resolve().parents[2]
INTERIM, PROCESSED = ROOT / "data" / "interim", ROOT / "data" / "processed"
cfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
INPUTS = {"sst.nc": ["sst"], "sss.nc": ["sss"], "ssh.nc": ["sla", "uo", "vo"], "winds.nc": ["u10", "v10"]}


def split_labels(times: pd.DatetimeIndex) -> np.ndarray:
    sp = cfg["splits"]
    test_m, buf = set(sp["test_months"]), int(sp["buffer_days"])
    test_days = times[times.month.isin(test_m)]
    lab = np.where(times.month.isin(test_m), "test", "train").astype(object)
    for i, t in enumerate(times):
        if lab[i] == "train" and len(test_days):
            if np.min(np.abs((test_days - t).days)) <= buf:
                lab[i] = "buffer"
    return lab.astype(str)


def main() -> int:
    target = xr.open_dataset(INTERIM / "glorys_thetao.nc")
    ds = target[["thetao"]].load()
    for f, vars_ in INPUTS.items():
        src = xr.open_dataset(INTERIM / f)[vars_].load()
        ds = xr.merge([ds, src], join="exact", combine_attrs="drop")   # raises on any coord mismatch
    clim = xr.open_dataset(INTERIM / "glorys_clim.nc").load()
    masks = xr.open_dataset(INTERIM / "masks.nc").load()
    ds = xr.merge([ds, clim[["thetao_clim"]], masks], join="exact", combine_attrs="drop")

    times = pd.DatetimeIndex(ds.time.values)
    assert len(times) == 365 and times.is_unique and times.is_monotonic_increasing
    ds["split"] = ("time", split_labels(times))
    ds["month_of_time"] = ("time", times.month.values.astype("int8"))
    for v in ["thetao", "sst", "sss", "sla", "uo", "vo", "u10", "v10", "thetao_clim"]:
        src_file = "glorys_thetao.nc" if v == "thetao" else "glorys_clim.nc" if v == "thetao_clim" else next(k for k, vs in INPUTS.items() if v in vs)
        ds[v].attrs = xr.open_dataset(INTERIM / src_file)[v].attrs
    ds.attrs = {"title": "OceanEmbed-ML integrated data cube (2021, canonical 0.25 deg daily grid)",
                "splits": json.dumps(cfg["splits"]),
                "history": "scripts/integrate/build_cube.py — exact join of data/interim/*.nc"}

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "cube.nc"
    enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars if ds[v].dtype.kind == "f"}
    ds.to_netcdf(out.with_suffix(".part.nc"), encoding=enc)
    out.with_suffix(".part.nc").replace(out)

    counts = pd.Series(ds.split.values).value_counts().to_dict()
    ocean = int(ds.ocean_mask.sum())
    summary = {"days_per_split": {k: int(v) for k, v in counts.items()},
               "ocean_cells": ocean,
               "surface_samples_per_split": {k: int(v) * ocean for k, v in counts.items()},
               "file": str(out.relative_to(ROOT)), "size_MB": round(out.stat().st_size / 1e6, 1)}
    (ROOT / "data" / "audit" / "cube_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
