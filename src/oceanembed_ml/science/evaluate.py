"""Phase 6 — compute indicators on the test grid and score them against GLORYS.

For every test day and ocean cell: D20, D26, TCHP, MLD, OHC300 from the model
prediction, from GLORYS (truth) and from the climatology (baseline).
Writes data/final/predictions/test_indicators.nc and results/phase6/indicators.json.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import xarray as xr

from oceanembed_ml.config import FINAL, ROOT
from oceanembed_ml.science.indicators import INDICATORS

RES = ROOT / "results" / "phase6"


def score(t, p):
    m = np.isfinite(t) & np.isfinite(p)
    e = p[m] - t[m]
    return {"n": int(m.sum()), "rmse": float(np.sqrt(np.mean(e**2))), "mae": float(np.mean(np.abs(e))),
            "bias": float(e.mean()), "r": float(np.corrcoef(t[m], p[m])[0, 1]),
            "truth_mean": float(t[m].mean()), "truth_std": float(t[m].std())}


def main() -> int:
    pr = xr.open_dataset(FINAL / "predictions" / "test_predictions.nc").load()
    out_vars, out = {}, {}
    for name, (fn, units) in INDICATORS.items():
        vals = {}
        for src in ("pred", "glorys", "clim"):
            T = np.moveaxis(pr[src].values, 1, -1)          # (time, lat, lon, depth)
            vals[src] = fn(T).astype("float32")
            out_vars[f"{name}_{src}"] = (("time", "lat", "lon"), vals[src])
        out[name] = {"units": units, "model_vs_glorys": score(vals["glorys"], vals["pred"]),
                     "clim_vs_glorys": score(vals["glorys"], vals["clim"])}
        mv, cv_ = out[name]["model_vs_glorys"], out[name]["clim_vs_glorys"]
        out[name]["skill_vs_clim"] = float(1 - mv["rmse"] ** 2 / cv_["rmse"] ** 2)
        print(f"  {name:6s} model RMSE={mv['rmse']:.2f} r={mv['r']:.3f} | clim RMSE={cv_['rmse']:.2f} ({units})", flush=True)
    ds = xr.Dataset(out_vars, coords={"time": pr.time, "lat": pr.lat, "lon": pr.lon})
    for name, (_, units) in INDICATORS.items():
        for src in ("pred", "glorys", "clim"):
            ds[f"{name}_{src}"].attrs["units"] = units
    ds.to_netcdf(FINAL / "predictions" / "test_indicators.nc", encoding={v: {"zlib": True} for v in ds.data_vars})
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "indicators.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
