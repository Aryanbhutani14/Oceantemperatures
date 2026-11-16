"""Phase 1 — download CMEMS sources for the study period, subset at the server.

Each source is downloaded MONTH BY MONTH into data/raw/<source>/<YYYY-MM>.nc so
a failed/interrupted run can simply be restarted (existing complete files are
skipped). Only the padded bounding box, the needed variables and — for 3-D
products — the depth range down to the first level >= 1000 m are requested.

Raw files are never modified afterwards. A SHA-256 manifest is written by
scripts/download/verify_raw.py.

Usage:
    python scripts/download/download_cmems.py --source sst
    python scripts/download/download_cmems.py --source all --dry-run

Requires a prior `copernicusmarine login` (credentials are stored locally by
the toolbox; this script never handles passwords).
"""
from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import copernicusmarine as cm
import yaml

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
LOG = RAW / "download_log.jsonl"

grid = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
dcfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
D, PAD = grid["domain"], grid["download_pad_deg"]
BBOX = dict(
    minimum_longitude=D["lon_min"] - PAD,
    maximum_longitude=D["lon_max"] + PAD,
    minimum_latitude=D["lat_min"] - PAD,
    maximum_latitude=D["lat_max"] + PAD,
)

# Short source keys -> what to request. Depth limits are chosen from the audit
# (data/audit/grid_alignment.json): first native level >= 1000 m.
SOURCES = {
    "glorys": dict(cfg="glorys_ens", dataset_id="cmems_mod_glo_phy-all_my_0.25deg_P1D-m",
                   variables=["thetao_glor"], depth=(0.0, 1046.0)),
    "glorys_clim": dict(cfg="glorys12_climatology", dataset_id="cmems_mod_glo_phy_my_0.083deg-climatology_P1M-m",
                        variables=["thetao"], depth=(0.0, 1063.0), climatology=True),
    "sst": dict(cfg="ostia_rep", dataset_id="METOFFICE-GLO-SST-L4-REP-OBS-SST",
                variables=["analysed_sst"]),
    "sss": dict(cfg="sss_multiobs", dataset_id="cmems_obs-mob_glo_phy-sss_my_multi_P1D",
                variables=["sos"]),
    "ssh": dict(cfg="duacs", dataset_id="cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D",
                variables=["sla", "ugos", "vgos"]),
    "winds": dict(cfg="cmems_winds", dataset_id="cmems_obs-wind_glo_phy_my_l4_0.125deg_PT1H",
                  variables=["eastward_wind", "northward_wind"]),
}


def months(start: str, end: str):
    s, e = datetime.fromisoformat(start), datetime.fromisoformat(end)
    y, m = s.year, s.month
    while (y, m) <= (e.year, e.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["logged_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def fetch(key: str, spec: dict, out: Path, start: str, end: str, dry_run: bool, retries: int = 3) -> None:
    kwargs = dict(
        dataset_id=spec["dataset_id"],
        variables=spec["variables"],
        start_datetime=start,
        end_datetime=end,
        output_directory=str(out.parent),
        output_filename=out.name,
        overwrite=True,
        disable_progress_bar=True,
        dry_run=dry_run,
        **BBOX,
    )
    if "depth" in spec:
        kwargs["minimum_depth"], kwargs["maximum_depth"] = spec["depth"]
    tmp = out.with_suffix(".part.nc")
    if not dry_run:
        kwargs["output_filename"] = tmp.name
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            resp = cm.subset(**kwargs)
            info = resp.model_dump() if hasattr(resp, "model_dump") else {}
            if not dry_run:
                tmp.replace(out)  # atomic: a file only appears once complete
            log({"source": key, "file": str(out.relative_to(ROOT)), "dataset_id": spec["dataset_id"],
                 "variables": spec["variables"], "start": start, "end": end, "bbox": BBOX,
                 "depth": spec.get("depth"), "dry_run": dry_run, "seconds": round(time.time() - t0, 1),
                 "size_MB_estimate": info.get("file_size"), "status": "ok"})
            if dry_run:
                print(f"  [dry-run] {out.name}: ~{info.get('file_size')} MB, coords {info.get('coordinates_extent')}", flush=True)
            else:
                print(f"  {out.name}: {out.stat().st_size/1e6:.1f} MB in {time.time()-t0:.0f}s", flush=True)
            return
        except Exception as exc:
            log({"source": key, "file": str(out.relative_to(ROOT)), "status": "error", "attempt": attempt,
                 "error": f"{type(exc).__name__}: {exc}"})
            print(f"  ! {out.name} attempt {attempt} failed: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
            if tmp.exists():
                tmp.unlink()
            time.sleep(10 * attempt)
    raise RuntimeError(f"{key}: {out.name} failed after {retries} attempts")


def run(key: str, dry_run: bool) -> None:
    spec = SOURCES[key]
    out_dir = RAW / key
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{key}] {spec['dataset_id']} vars={spec['variables']}", flush=True)
    if spec.get("climatology"):
        out = out_dir / "climatology_monthly.nc"
        if out.exists() and not dry_run:
            print(f"  skip existing {out.name}")
            return
        fetch(key, spec, out, "2004-01-01T00:00:00", "2004-12-31T23:59:59", dry_run)
        return
    for y, m in months(dcfg["period"]["start"], dcfg["period"]["end"]):
        out = out_dir / f"{y:04d}-{m:02d}.nc"
        if out.exists() and not dry_run:
            print(f"  skip existing {out.name}")
            continue
        last = calendar.monthrange(y, m)[1]
        fetch(key, spec, out, f"{y:04d}-{m:02d}-01T00:00:00", f"{y:04d}-{m:02d}-{last:02d}T23:59:59", dry_run)
        if dry_run:
            break  # one month is enough to validate the request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=list(SOURCES) + ["all"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    keys = list(SOURCES) if a.source == "all" else [a.source]
    for k in keys:
        run(k, a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
