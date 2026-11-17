"""Phase 1 — download ARGO profiles (2021, study domain) and IBTrACS (North Indian).

ARGO
  Uses the GDAC global profile index (cached by the Phase 0 audit) to list
  every core profile file inside the domain during 2021, then downloads each
  single-profile NetCDF file from the GDAC (https) into
  data/raw/argo/profiles/<dac>/<wmo>/<file>.nc. Resumable: existing files are
  skipped. The selected index rows are saved as data/raw/argo/selection_2021.csv.
  Files are stored untouched; QC / conversion happens in a later phase.

IBTrACS
  Downloads the official North Indian basin CSV (v04r01) from NOAA NCEI into
  data/raw/ibtracs/. Used only for event-based evaluation, never as a feature.

Usage:
    python scripts/download/download_argo_ibtracs.py [--workers 8]
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
import yaml

from oceanembed_ml.config import ROOT
RAW = ROOT / "data" / "raw"
GDAC = "https://data-argo.ifremer.fr/dac/"
INDEX = RAW / "argo" / "index" / "ar_index_global_prof.txt.gz"
IBTRACS_URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv"

grid = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
dcfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))


def select_profiles() -> pd.DataFrame:
    if not INDEX.exists():
        raise FileNotFoundError(f"{INDEX} missing — run scripts/audit/audit_podaac_argo.py first")
    df = pd.read_csv(INDEX, comment="#", compression="gzip")
    df["date"] = pd.to_datetime(df["date"].astype("Int64").astype(str), format="%Y%m%d%H%M%S", errors="coerce")
    d = grid["domain"]
    start = pd.Timestamp(dcfg["period"]["start"])
    end = pd.Timestamp(dcfg["period"]["end"]) + pd.Timedelta(days=1)
    sel = df[
        df.longitude.between(d["lon_min"], d["lon_max"])
        & df.latitude.between(d["lat_min"], d["lat_max"])
        & (df.date >= start) & (df.date < end)
    ].copy()
    # Core profiles only (skip B-/synthetic files if any appear in this index)
    sel = sel[~sel["file"].str.split("/").str[-1].str.startswith(("B", "S"))]
    return sel.sort_values("date").reset_index(drop=True)


def fetch(session: requests.Session, rel: str) -> tuple[str, str]:
    out = RAW / "argo" / "profiles" / rel
    if out.exists() and out.stat().st_size > 0:
        return rel, "skip"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    for attempt in range(3):
        try:
            r = session.get(GDAC + rel, timeout=120)
            r.raise_for_status()
            tmp.write_bytes(r.content)
            tmp.replace(out)
            return rel, "ok"
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
    return rel, f"error {err}"


def download_argo(workers: int) -> None:
    sel = select_profiles()
    out_csv = RAW / "argo" / "selection_2021.csv"
    sel.to_csv(out_csv, index=False)
    print(f"[argo] {len(sel)} profiles / {sel['file'].str.split('/').str[1].nunique()} floats selected -> {out_csv.relative_to(ROOT)}", flush=True)
    stats = {"ok": 0, "skip": 0, "error": 0}
    errors = []
    with requests.Session() as s, ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch, s, f) for f in sel["file"]]
        for i, fut in enumerate(as_completed(futs), 1):
            rel, status = fut.result()
            key = status.split()[0]
            stats[key] += 1
            if key == "error":
                errors.append(f"{rel}\t{status}")
            if i % 250 == 0:
                print(f"  {i}/{len(futs)} {stats}", flush=True)
    (RAW / "argo" / "download_errors.txt").write_text("\n".join(errors), encoding="utf-8")
    print(f"[argo] done {stats}", flush=True)


def download_ibtracs() -> None:
    out = RAW / "ibtracs" / Path(IBTRACS_URL).name
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        print(f"[ibtracs] skip existing {out.name}")
        return
    r = requests.get(IBTRACS_URL, timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(f"[ibtracs] {out.name}: {out.stat().st_size/1e6:.1f} MB", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    download_ibtracs()
    download_argo(a.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
