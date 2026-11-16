"""Phase 0 — Copernicus Marine (CMEMS) catalogue audit.

Queries the public CMEMS catalogue (no login required) for every candidate
product in configs/datasets.yaml and writes a machine-readable summary:

    data/audit/cmems_catalogue.json

For each dataset we record: variables, units, and the coordinate axes
(latitude/longitude/time/depth) with min, max, step and — for depth — the
full list of native levels. Nothing is downloaded except catalogue metadata.

Usage:
    python scripts/audit/audit_cmems.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import copernicusmarine as cm
import yaml

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "audit" / "cmems_catalogue.json"

# Services that expose coordinate information (the "original-files" service does not).
COORD_SERVICES = ("arco-geo-series", "arco-time-series", "omi-arco", "static-arco")


def _ms_to_iso(v):
    if v is None:
        return None
    try:
        return datetime.fromtimestamp(float(v) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return v


def _coord_summary(c: dict) -> dict:
    cid = c.get("coordinate_id")
    values = c.get("values")
    out = {
        "units": c.get("coordinate_unit"),
        "min": c.get("minimum_value"),
        "max": c.get("maximum_value"),
        "step": c.get("step"),
        "n_values": len(values) if values else None,
    }
    if cid == "time":
        out["min_iso"] = _ms_to_iso(out["min"] if out["min"] is not None else (values[0] if values else None))
        out["max_iso"] = _ms_to_iso(out["max"] if out["max"] is not None else (values[-1] if values else None))
        if out["step"] is not None:
            out["step_hours"] = float(out["step"]) / 3_600_000.0
    if cid in ("depth", "elevation") and values:
        out["values"] = [round(float(v), 4) for v in values]
    return out


def describe_product(product_id: str) -> dict:
    resp = cm.describe(product_id=product_id, disable_progress_bar=True)
    d = resp.model_dump() if hasattr(resp, "model_dump") else resp
    if not d.get("products"):
        return {"product_id": product_id, "error": "not found in catalogue"}
    p = d["products"][0]
    prod = {
        "product_id": p.get("product_id", product_id),
        "title": p.get("title"),
        "doi": p.get("digital_object_identifier") or p.get("doi"),
        "processing_level": p.get("processing_level"),
        "production_center": p.get("production_center"),
        "datasets": [],
    }
    for ds in p.get("datasets", []):
        entry = {"dataset_id": ds["dataset_id"], "versions": [], "variables": {}}
        for v in ds.get("versions", []):
            entry["versions"].append(v.get("label"))
        # Use the latest version, first part, and a service that carries coordinates.
        v = ds["versions"][-1]
        part = v["parts"][0]
        services = {s["service_name"]: s for s in part.get("services", [])}
        entry["services"] = sorted(services)
        svc = next((services[n] for n in COORD_SERVICES if n in services), None)
        if svc is None:
            svc = next(iter(services.values()))
        entry["coord_service"] = svc["service_name"]
        for var in svc.get("variables", []):
            entry["variables"][var["short_name"]] = {
                "standard_name": var.get("standard_name"),
                "units": var.get("units"),
                "coords": {c["coordinate_id"]: _coord_summary(c) for c in var.get("coordinates", [])},
            }
        prod["datasets"].append(entry)
    return prod


def main() -> int:
    cfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
    product_ids = [s["product_id"] for s in cfg["sources"].values() if s.get("provider") == "CMEMS"]
    product_ids = list(dict.fromkeys(product_ids))  # dedupe, keep order
    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "copernicusmarine_version": cm.__version__,
        "products": {},
    }
    for pid in product_ids:
        print(f"[audit] describing {pid} ...", flush=True)
        try:
            result["products"][pid] = describe_product(pid)
        except Exception as exc:  # record failure, don't hide it
            result["products"][pid] = {"product_id": pid, "error": f"{type(exc).__name__}: {exc}"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"[audit] wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
