"""Export compact data files for the static dashboard (dashboard/data/).

Everything shown on the dashboard comes from files written by earlier phases:
  data/final/predictions/test_predictions.nc   final model, GLORYS, climatology (test days)
  data/final/predictions/test_indicators.nc    TCHP / D20 for prediction, GLORYS, climatology
  data/processed/cube.nc                       satellite inputs on the canonical grid
  data/final/argo_matchups.parquet             ARGO profiles matched to test cell-days
  results/**.json, results/phase7/classification_scores.npz

Binary layout (little-endian int16, missing = -32768), one value per OCEAN cell
in the order given by meta.json "cells":
  day_YYYYMMDD.bin : pred[15], glorys[15] (x100 degC), inputs[7], tchp[3] (x10), d20[3] (x10)
  clim_MM.bin      : climatology[15] (x100 degC)

Run:  python scripts/09_export_dashboard.py
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import xarray as xr

from oceanembed_ml.config import FINAL, ROOT
from oceanembed_ml.grid import DEPTHS

OUT = ROOT / "dashboard" / "data"
DAYS = ["2021-02-10", "2021-02-24", "2021-05-05", "2021-05-14", "2021-05-16", "2021-05-24",
        "2021-08-10", "2021-08-25", "2021-11-10", "2021-11-25"]
INPUTS = [("sst", 100), ("sss", 100), ("sla", 1000), ("uo", 1000), ("vo", 1000), ("u10", 100), ("v10", 100)]
MISSING = -32768


def q(a, scale):
    a = np.asarray(a, dtype="float64") * scale
    out = np.where(np.isfinite(a), np.clip(np.round(a), -32767, 32767), MISSING)
    return out.astype("<i2")


def J(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8").replace("NaN", "null"))


def r(x, n=3):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pr = xr.open_dataset(FINAL / "predictions" / "test_predictions.nc")
    ind = xr.open_dataset(FINAL / "predictions" / "test_indicators.nc")
    cube = xr.open_dataset(ROOT / "data" / "processed" / "cube.nc")

    mask = cube["ocean_mask"].values.astype(bool)
    iy, ix = np.where(mask)
    deepest = cube["deepest_valid_depth"].values[iy, ix]
    meta = {"lat": [float(v) for v in pr.lat.values], "lon": [float(v) for v in pr.lon.values],
            "depths": [int(d) for d in DEPTHS], "days": DAYS, "n_cells": int(mask.sum()),
            "cells": {"iy": iy.tolist(), "ix": ix.tolist()},
            "deepest": [None if not np.isfinite(v) else int(v) for v in deepest],
            "inputs": [n for n, _ in INPUTS], "missing": MISSING,
            "layout": {"pred": 0, "glorys": 15, "inputs": 30, "tchp": 37, "d20": 40, "rows": 43}}

    # ------------------------------------------------------------ per-day binaries
    for day in DAYS:
        t = np.datetime64(day)
        p = pr.sel(time=t)
        rows = [q(p["pred"].values[k][iy, ix], 100) for k in range(15)]
        rows += [q(p["glorys"].values[k][iy, ix], 100) for k in range(15)]
        c = cube.sel(time=t)
        rows += [q(c[n].values[iy, ix], s) for n, s in INPUTS]
        i = ind.sel(time=t)
        rows += [q(i[f"TCHP_{w}"].values[iy, ix], 10) for w in ("glorys", "pred", "clim")]
        rows += [q(i[f"D20_{w}"].values[iy, ix], 10) for w in ("glorys", "pred", "clim")]
        np.stack(rows).tofile(OUT / f"day_{day.replace('-', '')}.bin")
    for m in (2, 5, 8, 11):
        t = pr.time.values[pd.DatetimeIndex(pr.time.values).month == m][0]
        cl = pr["clim"].sel(time=t).values
        np.stack([q(cl[k][iy, ix], 100) for k in range(15)]).tofile(OUT / f"clim_{m:02d}.bin")
    print("[dash] wrote", len(DAYS), "day files + 4 climatology files", flush=True)

    # ------------------------------------------------------------ daily domain RMSE (all 120 test days)
    daily = {"dates": [str(d)[:10] for d in pr.time.values]}
    for k, d in ((0, 0), (7, 100), (11, 300)):
        g = pr["glorys"].isel(depth=k).values
        for w in ("pred", "clim"):
            e = (pr[w].isel(depth=k).values - g) ** 2
            daily[f"{w}_{d}"] = [r(np.sqrt(np.nanmean(e[t])), 3) for t in range(e.shape[0])]

    # ------------------------------------------------------------ domain-mean profile (hero gauge)
    g = pr["glorys"].values
    prof = {"mean": [r(np.nanmean(g[:, k]), 2) for k in range(15)], "std": [r(np.nanstd(g[:, k]), 2) for k in range(15)]}

    # ------------------------------------------------------------ ARGO
    a = pd.read_parquet(FINAL / "argo_matchups.parquet")
    argo = {"time": [str(x)[:10] for x in a["time"]], "iy": a["lat_idx"].astype(int).tolist(), "ix": a["lon_idx"].astype(int).tolist(),
            "region": a["region"].astype(str).tolist(), "platform": a["platform"].astype(str).tolist()}
    for w in ("argo", "pred", "glorys", "clim"):
        cols = [f"{w}_d{k:02d}" for k in range(15)]
        if not all(c in a.columns for c in cols):
            continue
        argo[w] = [[r(v, 2) for v in row] for row in a[cols].to_numpy()]

    # ------------------------------------------------------------ cyclone tracks 2021
    tr = pd.read_csv(ROOT / "data" / "raw" / "ibtracs" / "ibtracs.NI.list.v04r01.csv", skiprows=[1], low_memory=False,
                     usecols=["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "WMO_WIND", "USA_WIND"])
    tr = tr[tr["SEASON"].astype(str) == "2021"]
    tracks = []
    for sid, gdf in tr.groupby("SID"):
        gdf = gdf.sort_values("ISO_TIME")
        wind = pd.to_numeric(gdf["USA_WIND"], errors="coerce").fillna(pd.to_numeric(gdf["WMO_WIND"], errors="coerce"))
        tracks.append({"name": str(gdf["NAME"].iloc[0]).title(), "time": gdf["ISO_TIME"].str[:16].tolist(),
                       "lat": gdf["LAT"].astype(float).round(2).tolist(), "lon": gdf["LON"].astype(float).round(2).tolist(),
                       "wind": [None if not np.isfinite(w) else int(w) for w in wind]})

    # ------------------------------------------------------------ classification threshold sweep
    z = np.load(ROOT / "results" / "phase7" / "classification_scores.npz")
    y = z["y"].astype(int)
    clf = {}
    for name in ("logistic_l1", "gradient_boosting"):
        s = z[name]
        thr = np.round(np.linspace(0.01, 0.99, 99), 2)
        rows = []
        for t in thr:
            p = s >= t
            rows.append([int((p & (y == 1)).sum()), int((p & (y == 0)).sum()), int((~p & (y == 1)).sum()), int((~p & (y == 0)).sum())])
        clf[name] = {"thr": thr.tolist(), "tp_fp_fn_tn": rows}
    rule = z["climatology_rule"] >= 0.5
    clf["climatology_rule"] = [int((rule & (y == 1)).sum()), int((rule & (y == 0)).sum()), int((~rule & (y == 1)).sum()), int((~rule & (y == 0)).sum())]

    # ------------------------------------------------------------ results summary
    T5, CV = J("results/phase5/test_metrics.json"), J("results/phase5/cv_selection.json")
    models = {}
    for m, v in T5["models"].items():
        models[m] = {"rmse": r(v["overall"]["rmse"]), "skill": r(v["mean_skill_over_depths"]), "fit_s": r(v.get("fit_seconds", 0), 0),
                     "per_depth": [r(v["per_depth"][str(int(d))]["rmse"]) for d in DEPTHS],
                     "skill_depth": [r(v["per_depth"][str(int(d))]["skill_vs_clim"]) for d in DEPTHS],
                     "cv": r(CV.get(m, {}).get("best_cv_rmse"), 4), "params": CV.get(m, {}).get("best_params")}
    tcv = J("results/phase5/target_cv.json")
    if T5.get("final_model") in models:
        models[T5["final_model"]]["cv"] = r(tcv["variants"]["anomaly+clim_feat"]["cv_rmse_mean"], 4)
        models[T5["final_model"]]["params"] = tcv["params"]
    C = J("results/phase7/classification.json")
    summary = {
        "models": models, "final": T5.get("final_model"),
        "full": J("results/phase6/full_test_metrics.json"),
        "tolerance": J("results/phase6/tolerance_accuracy.json"),
        "breakdown": J("results/validation/breakdown.json"),
        "argo_stats": J("results/phase6/argo_validation.json"),
        "indicators": J("results/phase6/indicators.json"),
        "classification": {k: {m: v.get(m) for m in ("accuracy", "precision", "recall", "f1", "roc_auc", "best_params", "cv_auc")}
                           for k, v in C["models"].items()},
        "clf_selected": C["selected_by_cv"], "clf_sweep": clf,
        "daily": daily, "profile": prof, "argo": argo, "tracks": tracks,
    }
    (OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, separators=(",", ":"), default=float).replace("NaN", "null"), encoding="utf-8")
    sizes = {p.name: round(p.stat().st_size / 1e6, 2) for p in OUT.iterdir()}
    print("[dash] files (MB):", sizes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
