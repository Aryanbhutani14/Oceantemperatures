"""Phase 6 — independent validation against ARGO float profiles (test days only).

Per profile (core GDAC file, first profile N_PROF=0):
  QC      POSITION_QC and JULD_QC in {1,2}; level QC in {1,2} for PRES and TEMP;
          ADJUSTED variables when DATA_MODE is 'A' or 'D' (delayed/adjusted), raw otherwise
  convert depth z = -gsw.z_from_p(p, lat); in-situ T -> POTENTIAL temperature with TEOS-10
          (GLORYS thetao is potential temperature). Absolute salinity from PSAL when its QC is
          good; otherwise SP = 35 is assumed (flagged; affects theta by < 0.01 degC at 1000 m)
  interp  linear to the 15 standard depths only where bracketed by measurements no further
          apart than 50 m (150 m below 300 m); 0 m = shallowest level if it is <= 6 m deep
  match   same UTC day as a TEST day; nearest 0.25 deg canonical cell (<= ~19 km); cell must be
          ocean. Several profiles in one cell-day are averaged (count recorded).

ARGO is never used for training, tuning or model selection. Caveat: GLORYS assimilates
ARGO, so ARGO is independent of the MODEL and its inputs, not of the training target.
Outputs: data/final/argo_matchups.parquet, results/phase6/argo_validation.json
"""
from __future__ import annotations

import json
import sys
import warnings

import gsw
import numpy as np
import pandas as pd
import xarray as xr

from oceanembed_ml.config import FINAL, RAW, ROOT
from oceanembed_ml.grid import DEPTHS, LAT, LON, REGIONS

warnings.filterwarnings("ignore")
RES = ROOT / "results" / "phase6"
GOOD = ("1", "2")


def _good(qc) -> np.ndarray:
    """QC flags arrive as bytes (S1); compare as text so b'1' and '1' both count."""
    return np.isin(np.asarray(qc).astype(str), GOOD)


def _s(x):
    return x.decode() if isinstance(x, bytes) else str(x)


def read_profile(path) -> dict | None:
    ds = xr.open_dataset(path, decode_times=False)
    try:
        if not (_good(ds["POSITION_QC"].values[:1])[0] and _good(ds["JULD_QC"].values[:1])[0]):
            return None
        mode = _s(ds["DATA_MODE"].values[0]).strip()
        sfx = "_ADJUSTED" if mode in ("A", "D") and "TEMP_ADJUSTED" in ds else ""
        p = ds[f"PRES{sfx}"].values[0].astype(float)
        t = ds[f"TEMP{sfx}"].values[0].astype(float)
        pq_ = ds[f"PRES{sfx}_QC"].values[0]
        tq = ds[f"TEMP{sfx}_QC"].values[0]
        ok = np.isfinite(p) & np.isfinite(t) & _good(pq_) & _good(tq)
        if ok.sum() < 10:
            return None
        lat, lon = float(ds["LATITUDE"].values[0]), float(ds["LONGITUDE"].values[0])
        sal_flag = False
        if f"PSAL{sfx}" in ds:
            s = ds[f"PSAL{sfx}"].values[0].astype(float)
            sq = _good(ds[f"PSAL{sfx}_QC"].values[0]) & np.isfinite(s)
        else:
            s, sq = np.full_like(t, np.nan), np.zeros_like(t, bool)
        if (sq & ok).sum() < 0.5 * ok.sum():
            s, sal_flag = np.full_like(t, 35.0), True
        else:
            s = np.where(sq, s, np.interp(p, p[sq & ok], s[sq & ok]))
        p, t, s = p[ok], t[ok], s[ok]
        o = np.argsort(p)
        p, t, s = p[o], t[o], s[o]
        SA = gsw.SA_from_SP(s, p, lon, lat)
        theta = gsw.pt0_from_t(SA, t, p)
        z = -gsw.z_from_p(p, lat)
        return {"platform": _s(ds["PLATFORM_NUMBER"].values[0]).strip(), "cycle": int(ds["CYCLE_NUMBER"].values[0]),
                "mode": mode, "juld": float(ds["JULD"].values[0]), "lat": lat, "lon": lon,
                "z": z, "theta": theta, "salinity_assumed": sal_flag}
    finally:
        ds.close()


def to_standard_depths(z: np.ndarray, th: np.ndarray) -> np.ndarray:
    out = np.full(len(DEPTHS), np.nan)
    for k, d in enumerate(DEPTHS):
        if d == 0:
            out[k] = th[0] if z[0] <= 6.0 else np.nan
            continue
        hi = np.searchsorted(z, d)
        if hi == 0 or hi >= len(z):
            if hi < len(z) and np.isclose(z[hi], d):
                out[k] = th[hi]
            continue
        lo = hi - 1
        gap = z[hi] - z[lo]
        if gap > (150.0 if d > 300 else 50.0):
            continue
        out[k] = th[lo] + (d - z[lo]) / gap * (th[hi] - th[lo])
    return out


def region_of(lat, lon):
    for name, b in REGIONS.items():
        if b["lat"][0] <= lat <= b["lat"][1] and b["lon"][0] <= lon <= b["lon"][1]:
            return name
    return "other"


def metrics(a: np.ndarray, p: np.ndarray) -> dict:
    m = np.isfinite(a) & np.isfinite(p)
    if m.sum() < 3:
        return {"n": int(m.sum())}
    e = p[m] - a[m]
    return {"n": int(m.sum()), "rmse": float(np.sqrt(np.mean(e**2))), "mae": float(np.mean(np.abs(e))),
            "bias": float(e.mean()), "r": float(np.corrcoef(a[m], p[m])[0, 1])}


def main() -> int:
    pr = xr.open_dataset(FINAL / "predictions" / "test_predictions.nc")
    test_days = pd.DatetimeIndex(pr.time.values).normalize()
    sel = pd.read_csv(RAW / "argo" / "selection_2021.csv", parse_dates=["date"])
    sel = sel[sel["date"].dt.normalize().isin(test_days)]
    print(f"[argo] {len(sel)} index entries fall on test days", flush=True)
    recs, rejected = [], 0
    for rel in sel["file"]:
        r = read_profile(RAW / "argo" / "profiles" / rel)
        if r is None:
            rejected += 1
            continue
        day = (pd.Timestamp("1950-01-01") + pd.to_timedelta(r["juld"], unit="D")).normalize()
        if day not in test_days:
            rejected += 1
            continue
        i, j = int(round((r["lat"] - LAT[0]) / 0.25)), int(round((r["lon"] - LON[0]) / 0.25))
        if not (0 <= i < len(LAT) and 0 <= j < len(LON)):
            rejected += 1
            continue
        ti = int(np.where(test_days == day)[0][0])
        pred = pr["pred"].isel(time=ti, lat=i, lon=j).values
        if not np.isfinite(pred[0]):          # land / no prediction at this cell
            rejected += 1
            continue
        recs.append({"profile_id": f"{r['platform']}_{r['cycle']:03d}", "platform": r["platform"], "mode": r["mode"],
                     "time": day, "lat": r["lat"], "lon": r["lon"], "lat_idx": i, "lon_idx": j, "region": region_of(r["lat"], r["lon"]),
                     "salinity_assumed": r["salinity_assumed"],
                     **{f"argo_d{k:02d}": v for k, v in enumerate(to_standard_depths(r["z"], r["theta"]))},
                     **{f"pred_d{k:02d}": v for k, v in enumerate(pred)},
                     **{f"glorys_d{k:02d}": v for k, v in enumerate(pr["glorys"].isel(time=ti, lat=i, lon=j).values)},
                     **{f"clim_d{k:02d}": v for k, v in enumerate(pr["clim"].isel(time=ti, lat=i, lon=j).values)}})
    df = pd.DataFrame(recs)
    n_raw = len(df)
    if n_raw == 0:
        raise RuntimeError(f"no ARGO matchups (rejected {rejected}) - check QC parsing")
    # several profiles in the same cell-day -> average (independent samples = cell-days)
    num = df.select_dtypes("number").columns.difference(["lat_idx", "lon_idx"])
    agg = df.groupby(["time", "lat_idx", "lon_idx"]).agg({**{c: "mean" for c in num}, "region": "first", "profile_id": "first",
                                                           "platform": "first", "mode": "first", "salinity_assumed": "max"})
    agg["n_profiles"] = df.groupby(["time", "lat_idx", "lon_idx"]).size()
    df = agg.reset_index()
    FINAL.mkdir(parents=True, exist_ok=True)
    df.to_parquet(FINAL / "argo_matchups.parquet", index=False)

    out = {"n_index_entries_on_test_days": int(len(sel)), "n_profiles_rejected": rejected, "n_profiles_matched": n_raw,
           "n_matchups_cell_days": int(len(df)), "n_floats": int(df["platform"].nunique()),
           "n_delayed_mode": int((df["mode"] == "D").sum()), "n_salinity_assumed": int(df["salinity_assumed"].sum()),
           "by_region": df["region"].value_counts().to_dict(), "per_depth": {}, "overall": {}}
    stacks = {s: [] for s in ("pred", "glorys", "clim")}
    A_all = []
    for k, d in enumerate(DEPTHS):
        a = df[f"argo_d{k:02d}"].to_numpy()
        A_all.append(a)
        out["per_depth"][str(int(d))] = {s: metrics(a, df[f"{s}_d{k:02d}"].to_numpy()) for s in stacks}
        for s in stacks:
            stacks[s].append(df[f"{s}_d{k:02d}"].to_numpy())
    A_all = np.concatenate(A_all)
    out["overall"] = {s: metrics(A_all, np.concatenate(v)) for s, v in stacks.items()}
    out["by_region_overall"] = {}
    for rg, g in df.groupby("region"):
        a = np.concatenate([g[f"argo_d{k:02d}"].to_numpy() for k in range(len(DEPTHS))])
        out["by_region_overall"][rg] = {s: metrics(a, np.concatenate([g[f"{s}_d{k:02d}"].to_numpy() for k in range(len(DEPTHS))])) for s in stacks}
    out["notes"] = ["model = final model (gradient boosting + climatology feature), never trained on ARGO",
                    "glorys = the training target itself (assimilates ARGO): an upper bound, not a competitor",
                    "clim = external climatology baseline", "ARGO in-situ T converted to potential temperature (TEOS-10)"]
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "argo_validation.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    o = out["overall"]
    print(f"[argo] matchups {len(df)} cell-days from {n_raw} profiles ({out['n_floats']} floats); rejected {rejected}")
    for s in ("pred", "glorys", "clim"):
        print(f"  vs ARGO  {s:7s} RMSE={o[s]['rmse']:.3f}  bias={o[s]['bias']:+.3f}  r={o[s]['r']:.4f}  n={o[s]['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
