"""Phase 6 — predict EVERY ocean cell on EVERY test day with the final model.

Writes data/final/predictions/test_predictions.nc with, on the canonical grid:
    pred    model temperature            (time, depth, lat, lon)
    glorys  GLORYS truth                 (time, depth, lat, lon)
    clim    external climatology         (time, depth, lat, lon)
and results/phase6/full_test_metrics.json (all 1.43M test rows, not a subsample).
This file feeds the maps, the indicators, the ARGO validation and the dashboard.
"""
from __future__ import annotations

import json
import sys
import time

import joblib
import numpy as np
import pyarrow.parquet as pq
import xarray as xr

from oceanembed_ml.config import FINAL, ROOT
from oceanembed_ml.grid import DEPTHS, LAT, LON
from oceanembed_ml.models import data as D
from oceanembed_ml.models.metrics import evaluate

OUT = FINAL / "predictions"
RES = ROOT / "results" / "phase6"


def main() -> int:
    bundle = joblib.load(ROOT / "models" / "phase5" / "final_model.joblib")
    model, feats, target = bundle["model"], bundle["features"], bundle["target"]
    cols = list(dict.fromkeys(["time", "lat_idx", "lon_idx"] + feats + D.A_COLS + D.Y_COLS + D.C_COLS))
    df = pq.read_table(FINAL / "features" / "test.parquet", columns=cols).to_pandas()
    t0 = time.time()
    P = model.predict(df[feats].to_numpy("float32"))
    if target == "absolute":
        P = P - df[D.C_COLS].to_numpy("float32")
    print(f"[predict] {len(df):,} rows in {time.time() - t0:.0f}s", flush=True)
    Y, C = df[D.Y_COLS].to_numpy("float32"), df[D.C_COLS].to_numpy("float32")
    T = C + P
    met = evaluate(Y, P, C)
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "full_test_metrics.json").write_text(json.dumps({"rows": len(df), "model": "final_model", "target": target, **met}, indent=1), encoding="utf-8")
    print(f"[predict] full test set RMSE={met['overall']['rmse']:.4f} skill={met['mean_skill_over_depths']:.3f}", flush=True)

    times = np.sort(df["time"].unique())
    ti = np.searchsorted(times, df["time"].to_numpy())
    yi, xi = df["lat_idx"].to_numpy(), df["lon_idx"].to_numpy()
    shape = (len(times), len(DEPTHS), len(LAT), len(LON))
    cubes = {}
    for name, arr in (("pred", T), ("glorys", Y), ("clim", C)):
        g = np.full(shape, np.nan, dtype="float32")
        g[ti, :, yi, xi] = arr
        cubes[name] = (("time", "depth", "lat", "lon"), g)
    ds = xr.Dataset(cubes, coords={"time": times, "depth": DEPTHS, "lat": LAT, "lon": LON},
                    attrs={"model": "final_model (gradient boosting + climatology feature)", "target": target,
                           "units": "degC (potential temperature)", "split": "test months Feb, May, Aug, Nov 2021"})
    OUT.mkdir(parents=True, exist_ok=True)
    enc = {v: {"zlib": True, "complevel": 4} for v in cubes}
    ds.to_netcdf(OUT / "test_predictions.part.nc", encoding=enc)
    (OUT / "test_predictions.part.nc").replace(OUT / "test_predictions.nc")
    print(f"[predict] wrote {OUT / 'test_predictions.nc'}  {dict(ds.sizes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
