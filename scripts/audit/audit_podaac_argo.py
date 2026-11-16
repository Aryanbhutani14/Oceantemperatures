"""Phase 0 — NASA PO.DAAC (OSCAR, CCMP) and ARGO availability audit.

* PO.DAAC: queries NASA CMR (public, no Earthdata login needed for search) for
  each collection's temporal coverage, spatial extent, granule count in the
  study period, and typical granule size. Writes data/audit/podaac_catalogue.json.
* ARGO: queries the Argo GDAC index via argopy for the number of profiles in
  the study domain during the TEST period only (ARGO is validation-only).
  Writes data/audit/argo_index_summary.json.

Nothing is downloaded except catalogue/index metadata.

Usage:
    python scripts/audit/audit_podaac_argo.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import yaml

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "audit"
CMR = "https://cmr.earthdata.nasa.gov/search"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def audit_podaac(short_name: str, start: str, end: str) -> dict:
    import requests

    out: dict = {"short_name": short_name}
    r = requests.get(f"{CMR}/collections.umm_json", params={"short_name": short_name, "provider": "POCLOUD"}, timeout=180)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return {**out, "error": "collection not found in CMR (POCLOUD)"}
    umm = items[0]["umm"]
    out["concept_id"] = items[0]["meta"]["concept-id"]
    out["title"] = umm.get("EntryTitle")
    out["version"] = umm.get("Version")
    out["doi"] = (umm.get("DOI") or {}).get("DOI")
    out["temporal_extents"] = umm.get("TemporalExtents")
    out["spatial_extent"] = umm.get("SpatialExtent", {}).get("HorizontalSpatialDomain")
    out["processing_level"] = (umm.get("ProcessingLevel") or {}).get("Id")
    out["data_centers"] = [dc.get("ShortName") for dc in umm.get("DataCenters", [])]
    out["related_urls"] = [u.get("URL") for u in umm.get("RelatedUrls", [])][:8]

    # Granules within the study period: count (header) + a sample for size/name
    g = requests.get(
        f"{CMR}/granules.umm_json",
        params={"collection_concept_id": out["concept_id"], "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "page_size": 5, "sort_key": "start_date"},
        timeout=180,
    )
    g.raise_for_status()
    out["granules_in_period"] = int(g.headers.get("CMR-Hits", -1))
    sample = []
    for it in g.json().get("items", []):
        gu = it["umm"]
        size = None
        for af in (gu.get("DataGranule") or {}).get("ArchiveAndDistributionInformation", []) or []:
            if af.get("Size") is not None:
                size = f'{af.get("Size")} {af.get("SizeUnit", "")}'.strip()
                break
        sample.append({"granule_ur": gu.get("GranuleUR"), "temporal": gu.get("TemporalExtent"), "size": size})
    out["granule_sample"] = sample

    # Last granule overall (true end of record)
    gl = requests.get(
        f"{CMR}/granules.umm_json",
        params={"collection_concept_id": out["concept_id"], "page_size": 1, "sort_key": "-start_date"},
        timeout=180,
    )
    gl.raise_for_status()
    last = gl.json().get("items", [])
    out["latest_granule_temporal"] = last[0]["umm"].get("TemporalExtent") if last else None
    out["granules_total"] = int(gl.headers.get("CMR-Hits", -1))
    return out


GDAC_INDEX_URL = "https://data-argo.ifremer.fr/ar_index_global_prof.txt.gz"


def _argo_index_dataframe(cache_dir: Path):
    """Return the Argo GDAC global profile index as a DataFrame.

    The index (~tens of MB, gzipped) is cached under data/raw/argo/index/ and is
    the authoritative list of every Argo profile file. argopy's IndexFetcher
    failed on this machine (GdacPathError), so the index is read directly.
    """
    import pandas as pd
    import requests

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "ar_index_global_prof.txt.gz"
    if not path.exists():
        with requests.get(GDAC_INDEX_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    df = pd.read_csv(path, comment="#", compression="gzip")
    df["date"] = pd.to_datetime(df["date"].astype("Int64").astype(str), format="%Y%m%d%H%M%S", errors="coerce")
    df["wmo"] = df["file"].str.split("/").str[1]
    return df, path


def audit_argo(box: list, test_start: str, test_end: str) -> dict:
    import pandas as pd

    out: dict = {"box": box, "period": [test_start, test_end], "index_url": GDAC_INDEX_URL}
    try:
        df, path = _argo_index_dataframe(ROOT / "data" / "raw" / "argo" / "index")
        out["index_cached_at"] = str(path.relative_to(ROOT))
        out["index_total_profiles_global"] = int(len(df))
        lon0, lon1, lat0, lat1 = box
        sel = df[
            df.longitude.between(lon0, lon1)
            & df.latitude.between(lat0, lat1)
            & (df.date >= pd.Timestamp(test_start))
            & (df.date <= pd.Timestamp(test_end) + pd.Timedelta(days=1))
        ]
        out["n_profiles"] = int(len(sel))
        out["n_floats"] = int(sel["wmo"].nunique())
        # Delayed-mode files start with 'D' (best quality), real-time with 'R'
        fname = sel["file"].str.split("/").str[-1]
        out["n_delayed_mode"] = int(fname.str.startswith("D").sum())
        out["n_realtime"] = int(fname.str.startswith("R").sum())
        out["profiles_per_month"] = {str(k): int(v) for k, v in sel["date"].dt.to_period("M").value_counts().sort_index().items()}
        out["n_profiles_arabian_sea"] = int((sel.latitude.between(5, 25) & sel.longitude.between(50, 75)).sum())
        out["n_profiles_bay_of_bengal"] = int((sel.latitude.between(5, 23) & sel.longitude.between(80, 100)).sum())
        out["dacs"] = {k: int(v) for k, v in sel["institution"].value_counts().items()}
        out["source"] = "Argo GDAC global profile index (read directly)"
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def main() -> int:
    cfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    grid = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
    start, end = cfg["period"]["start"], cfg["period"]["end"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pod = {"generated_at": _now(), "period": [start, end], "collections": {}}
    for key, s in cfg["sources"].items():
        if s.get("provider") != "PODAAC":
            continue
        print(f"[audit] CMR {s['short_name']} ...", flush=True)
        try:
            pod["collections"][key] = audit_podaac(s["short_name"], start, end)
        except Exception as exc:
            pod["collections"][key] = {"short_name": s["short_name"], "error": f"{type(exc).__name__}: {exc}"}
    (OUT_DIR / "podaac_catalogue.json").write_text(json.dumps(pod, indent=2, default=str), encoding="utf-8")
    print("[audit] wrote data/audit/podaac_catalogue.json", flush=True)

    d = grid["domain"]
    box = [d["lon_min"], d["lon_max"], d["lat_min"], d["lat_max"]]
    # ARGO is audited for the TEST year only (it is never used for training).
    test_start, test_end = "2021-01-01", "2021-12-31"
    print("[audit] ARGO GDAC index ...", flush=True)
    argo = {"generated_at": _now(), **audit_argo(box, test_start, test_end)}
    (OUT_DIR / "argo_index_summary.json").write_text(json.dumps(argo, indent=2, default=str), encoding="utf-8")
    print("[audit] wrote data/audit/argo_index_summary.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
