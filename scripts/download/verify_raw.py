"""Phase 1 — verify raw downloads and write a provenance manifest.

For every raw NetCDF under data/raw/<source>/ this checks:
  * the file opens, has the expected variables and units
  * time steps per month are complete (daily: days in month; hourly: 24 x days;
    climatology: 12)
  * the spatial extent covers the padded canonical domain
  * for 3-D products, the depth range reaches >= 1000 m
and records SHA-256, size, shape and the fraction of NaN values.

Outputs:
  data/raw/manifest.json              full per-file manifest (not committed)
  data/audit/raw_verification.json    per-source summary (committed)

Usage:
    python scripts/download/verify_raw.py
"""
from __future__ import annotations

import calendar
import hashlib
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr
import yaml

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
grid = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
D = grid["domain"]

EXPECT = {
    "glorys": dict(vars={"thetao_glor": "degrees_C"}, freq="daily", depth=True),
    "glorys_clim": dict(vars={"thetao": "degrees_C"}, freq="clim", depth=True),
    "sst": dict(vars={"analysed_sst": "kelvin"}, freq="daily"),
    "sss": dict(vars={"sos": None}, freq="daily"),
    "ssh": dict(vars={"sla": "m", "ugos": "m/s", "vgos": "m/s"}, freq="daily"),
    "winds": dict(vars={"eastward_wind": "m s-1", "northward_wind": "m s-1"}, freq="hourly"),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _name(ds, *cands):
    for c in cands:
        if c in ds.coords or c in ds.dims:
            return c
    return None


def check_file(src: str, p: Path) -> dict:
    exp = EXPECT[src]
    rec = {"file": str(p.relative_to(ROOT)).replace("\\", "/"), "size_MB": round(p.stat().st_size / 1e6, 2), "sha256": sha256(p), "problems": []}
    with xr.open_dataset(p, decode_times=True) as ds:
        lat, lon = _name(ds, "latitude", "lat"), _name(ds, "longitude", "lon")
        rec["dims"] = {k: int(v) for k, v in ds.sizes.items()}
        rec["lat_range"] = [float(ds[lat].min()), float(ds[lat].max())]
        rec["lon_range"] = [float(ds[lon].min()), float(ds[lon].max())]
        if rec["lat_range"][0] > D["lat_min"] - 0.125 or rec["lat_range"][1] < D["lat_max"] + 0.125:
            rec["problems"].append(f"latitude {rec['lat_range']} does not cover domain edges")
        if rec["lon_range"][0] > D["lon_min"] - 0.125 or rec["lon_range"][1] < D["lon_max"] + 0.125:
            rec["problems"].append(f"longitude {rec['lon_range']} does not cover domain edges")
        t = ds["time"].values
        rec["time_range"] = [str(t.min())[:19], str(t.max())[:19]]
        rec["n_time"] = int(t.size)
        if exp["freq"] == "clim":
            want = 12
        else:
            ts = np.datetime64(t.min(), "D").astype(object)
            ndays = calendar.monthrange(ts.year, ts.month)[1]
            want = ndays * (24 if exp["freq"] == "hourly" else 1)
        if t.size != want:
            rec["problems"].append(f"time steps {t.size} != expected {want}")
        if np.unique(t).size != t.size:
            rec["problems"].append("duplicate time stamps")
        if exp.get("depth"):
            dep = ds[_name(ds, "depth")].values
            rec["depth_range"] = [float(dep.min()), float(dep.max())]
            rec["n_depth"] = int(dep.size)
            if dep.max() < 1000:
                rec["problems"].append(f"max depth {dep.max():.1f} < 1000 m")
        rec["vars"] = {}
        for v, unit in exp["vars"].items():
            if v not in ds:
                rec["problems"].append(f"missing variable {v}")
                continue
            arr = ds[v]
            u = arr.attrs.get("units")
            if unit is not None and u != unit:
                rec["problems"].append(f"{v} units '{u}' != expected '{unit}'")
            # NaN fraction on a subsample of time steps (cheap; land is NaN by design)
            sub = arr.isel(time=slice(0, None, max(1, arr.sizes["time"] // 4)))
            if "depth" in sub.dims:
                sub = sub.isel(depth=0)
            vals = sub.values
            rec["vars"][v] = {"units": u, "nan_frac_sample": round(float(np.isnan(vals).mean()), 4),
                              "min": float(np.nanmin(vals)), "max": float(np.nanmax(vals))}
    return rec


def main() -> int:
    manifest = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": {}}
    summary = {"generated_at": manifest["generated_at"], "sources": {}}
    for src in EXPECT:
        files = sorted((RAW / src).glob("*.nc"))
        files = [f for f in files if not f.name.endswith(".part.nc")]
        recs = []
        for f in files:
            try:
                recs.append(check_file(src, f))
            except Exception as exc:  # noqa: BLE001
                recs.append({"file": str(f.relative_to(ROOT)), "problems": [f"cannot open: {type(exc).__name__}: {exc}"]})
        manifest["sources"][src] = recs
        expected_files = 1 if EXPECT[src]["freq"] == "clim" else 12
        probs = [f"{r['file']}: {p}" for r in recs for p in r.get("problems", [])]
        summary["sources"][src] = {
            "n_files": len(recs), "expected_files": expected_files,
            "total_MB": round(sum(r.get("size_MB", 0) for r in recs), 1),
            "complete": len(recs) == expected_files and not probs,
            "problems": probs,
            "example": {k: recs[0].get(k) for k in ("dims", "lat_range", "lon_range", "depth_range", "vars")} if recs else None,
        }
        s = summary["sources"][src]
        print(f"{src:12s} files {s['n_files']:2d}/{s['expected_files']:2d}  {s['total_MB']:8.1f} MB  {'OK' if s['complete'] else 'INCOMPLETE'}  problems={len(probs)}")
        for p in probs[:5]:
            print("   -", p)

    # ARGO + IBTrACS
    argo_files = list((RAW / "argo" / "profiles").rglob("*.nc"))
    sel = RAW / "argo" / "selection_2021.csv"
    n_sel = sum(1 for _ in sel.open(encoding="utf-8")) - 1 if sel.exists() else None
    summary["sources"]["argo"] = {"n_files": len(argo_files), "expected_files": n_sel,
                                  "total_MB": round(sum(f.stat().st_size for f in argo_files) / 1e6, 1),
                                  "complete": n_sel is not None and len(argo_files) == n_sel}
    ib = list((RAW / "ibtracs").glob("*.csv"))
    summary["sources"]["ibtracs"] = {"n_files": len(ib), "expected_files": 1,
                                     "total_MB": round(sum(f.stat().st_size for f in ib) / 1e6, 1), "complete": len(ib) == 1}
    for k in ("argo", "ibtracs"):
        s = summary["sources"][k]
        print(f"{k:12s} files {s['n_files']}/{s['expected_files']}  {s['total_MB']:8.1f} MB  {'OK' if s['complete'] else 'INCOMPLETE'}")

    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (ROOT / "data" / "audit" / "raw_verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if all(s["complete"] for s in summary["sources"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
