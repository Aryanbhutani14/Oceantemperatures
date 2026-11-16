"""Phase 0 — grid-alignment analysis and download-volume estimate.

Pure computation on the audited catalogue metadata (no network):

1. For every gridded source, compare its native grid with the canonical grid
   (configs/grid.yaml) and decide the spatial operator:
     * identical centres                       -> exact selection
     * finer grid whose cells NEST exactly in
       canonical cells (edges coincide)        -> block mean (= conservative)
     * otherwise                               -> area-weighted conservative
                                                  (finer) / bilinear (same res)
2. For GLORYS, list the native levels that bracket the 15 PS depths.
3. Estimate uncompressed download volume for the bbox (+pad) and period.

Writes data/audit/grid_alignment.json and prints a summary table.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data" / "audit"
grid = yaml.safe_load((ROOT / "configs" / "grid.yaml").read_text(encoding="utf-8"))
dcfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text(encoding="utf-8"))
cat = json.loads((AUDIT / "cmems_catalogue.json").read_text(encoding="utf-8"))

D = grid["domain"]
RES = D["res"]
PAD = grid["download_pad_deg"]
DEPTHS = grid["depths"]
N_DAYS = (
    __import__("datetime").date.fromisoformat(dcfg["period"]["end"])
    - __import__("datetime").date.fromisoformat(dcfg["period"]["start"])
).days + 1

# Canonical cell EDGES are at centre +/- RES/2, i.e. at (k*RES + RES/2) offsets from lat_min.
CANON_EDGE_PHASE = (D["lat_min"] - RES / 2) % RES  # 4.875 % 0.25 = 0.125


def _phase(x0: float, step: float) -> float:
    """Phase of native cell EDGES modulo the canonical resolution."""
    edge0 = x0 - step / 2
    return round(edge0 % RES, 6)


def analyse(name: str, lat_min: float, lon_min: float, step: float) -> dict:
    lat_centre_offset = round((lat_min - D["lat_min"]) % RES, 6)
    lon_centre_offset = round((lon_min - D["lon_min"]) % RES, 6)
    out = {"native_step_deg": step, "native_lat0": lat_min, "native_lon0": lon_min}
    ratio = RES / step
    same_res = math.isclose(step, RES, rel_tol=1e-4)
    centres_aligned = min(lat_centre_offset, RES - lat_centre_offset) < 1e-4 and min(lon_centre_offset, RES - lon_centre_offset) < 1e-4
    if same_res and centres_aligned:
        op = "exact_select"
        why = "native centres coincide with canonical centres"
    elif same_res:
        op = "bilinear"
        why = f"same resolution, centres offset by ({lat_centre_offset}, {lon_centre_offset}) deg"
    else:
        integer_ratio = abs(ratio - round(ratio)) < 1e-3
        e_lat = _phase(lat_min, step)
        e_lon = _phase(lon_min, step)
        edges_nest = integer_ratio and all(
            min(abs(e - CANON_EDGE_PHASE) % step, step - abs(e - CANON_EDGE_PHASE) % step) < 1e-4 for e in (e_lat, e_lon)
        )
        if edges_nest:
            op = f"block_mean_{round(ratio)}x{round(ratio)}"
            why = f"{round(ratio)}x{round(ratio)} native cells nest exactly inside each canonical cell (edges coincide) -> block mean is exactly area-conservative"
        else:
            op = "conservative_area_weighted"
            why = f"native edges (phase {e_lat},{e_lon}) do NOT coincide with canonical edges (phase {CANON_EDGE_PHASE}); a {ratio:.0f}x{ratio:.0f} block mean would mix partial cells / shift the field -> use area-weighted overlap"
    out.update({"centre_offset_deg": [lat_centre_offset, lon_centre_offset], "ratio": round(ratio, 4), "operator": op, "reason": why})
    return out


def _coords(pid: str, ds_id: str, var: str) -> dict:
    for ds in cat["products"][pid]["datasets"]:
        if ds["dataset_id"] == ds_id:
            return ds["variables"][var]["coords"]
    raise KeyError(f"{pid}/{ds_id}/{var}")


SOURCES = {
    "glorys_ens (target)": ("GLOBAL_MULTIYEAR_PHY_ENS_001_031", "cmems_mod_glo_phy-all_my_0.25deg_P1D-m", "thetao_glor", 1),
    "glorys12 (target alt.)": ("GLOBAL_MULTIYEAR_PHY_001_030", "cmems_mod_glo_phy_my_0.083deg_P1D-m", "thetao", 1),
    "glorys12_clim (baseline)": ("GLOBAL_MULTIYEAR_PHY_001_030", "cmems_mod_glo_phy_my_0.083deg-climatology_P1M-m", "thetao", 1),
    "ostia_rep (sst)": ("SST_GLO_SST_L4_REP_OBSERVATIONS_010_011", "METOFFICE-GLO-SST-L4-REP-OBS-SST", "analysed_sst", 1),
    "sss_multiobs (sss)": ("MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013", "cmems_obs-mob_glo_phy-sss_my_multi_P1D", "sos", 1),
    "duacs (sla, ugos, vgos)": ("SEALEVEL_GLO_PHY_L4_MY_008_047", "cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D", "sla", 3),
    "cmems_winds 0.125 (u10, v10)": ("WIND_GLO_PHY_L4_MY_012_006", "cmems_obs-wind_glo_phy_my_l4_0.125deg_PT1H", "eastward_wind", 2),
}

result = {"canonical": {"res": RES, "lat0": D["lat_min"], "lon0": D["lon_min"], "edge_phase": CANON_EDGE_PHASE}, "n_days": N_DAYS, "sources": {}}

for name, (pid, ds, var, nvars) in SOURCES.items():
    c = _coords(pid, ds, var)
    lat, lon = c["latitude"], c["longitude"]
    step = float(lat["step"])
    a = analyse(name, float(lat["min"]), float(lon["min"]), step)
    # bbox with pad -> native points
    nlat = math.ceil((D["lat_max"] - D["lat_min"] + 2 * PAD) / step) + 1
    nlon = math.ceil((D["lon_max"] - D["lon_min"] + 2 * PAD) / step) + 1
    tstep_h = c["time"].get("step_hours")
    nt = 12 if tstep_h is None else int(N_DAYS * 24 / tstep_h)  # None = monthly climatology
    nz = 1
    # Surface products may still carry a single-level depth axis -> treat as 2-D.
    if "depth" in c and c["depth"].get("values") and max(c["depth"]["values"]) >= max(DEPTHS):
        levels = sorted(c["depth"]["values"])
        deepest_needed = min(z for z in levels if z >= max(DEPTHS))
        used = [z for z in levels if z <= deepest_needed]
        nz = len(used)
        bracket = {}
        for d in DEPTHS:
            if d == 0:
                bracket[d] = {"uses": levels[0], "note": "shallowest native level (no extrapolation)"}
            else:
                lo = max(z for z in levels if z <= d) if any(z <= d for z in levels) else None
                hi = min(z for z in levels if z >= d)
                bracket[d] = {"lower": lo, "upper": hi}
        a["vertical"] = {"n_native_levels_total": len(levels), "n_levels_to_download": nz, "deepest_level_needed": deepest_needed, "bracketing": bracket}
    gb = nlat * nlon * nt * nz * nvars * 4 / 1e9
    a["volume_estimate"] = {"n_lat": nlat, "n_lon": nlon, "n_time": nt, "n_levels": nz, "n_vars": nvars, "uncompressed_GB_float32": round(gb, 2)}
    a["time_coverage"] = [c["time"].get("min_iso"), c["time"].get("max_iso")]
    result["sources"][name] = a

(AUDIT / "grid_alignment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

print(f"period days = {N_DAYS}\n")
print(f"{'source':32s} {'step':>7s} {'centre offset':>16s} {'operator':30s} {'GB':>7s}  coverage")
for name, a in result["sources"].items():
    v = a["volume_estimate"]
    print(f"{name:32s} {a['native_step_deg']:7.4f} {str(a['centre_offset_deg']):>16s} {a['operator']:30s} {v['uncompressed_GB_float32']:7.2f}  {a['time_coverage'][0][:10]}..{a['time_coverage'][1][:10]}")
    if "vertical" in a:
        vv = a["vertical"]
        print(f"{'':32s} levels: {vv['n_levels_to_download']} of {vv['n_native_levels_total']} (deepest needed {vv['deepest_level_needed']} m)")
