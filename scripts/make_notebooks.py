"""Generate and EXECUTE the exploration notebooks (notebooks/*.ipynb).

Notebooks are for exploration and presentation only: they import the reusable
code from src/oceanembed_ml and read the outputs each phase produced. They never
contain pipeline logic that results depend on.

    python scripts/make_notebooks.py            # build + execute all
    python scripts/make_notebooks.py 04         # only notebooks whose name starts with 04
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

SETUP = """\
import json, warnings
import numpy as np, pandas as pd, xarray as xr
import matplotlib.pyplot as plt
from IPython.display import Image, display, Markdown
from oceanembed_ml.config import ROOT, AUDIT, INTERIM, PROCESSED, FINAL, FIGURES, load_yaml
warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 50); pd.set_option("display.width", 200)
print("project root:", ROOT)"""

NOTEBOOKS = {
"01_data_audit.ipynb": [
("md", """# 01 · Data audit (Phase 0–1)
**Question:** which datasets exist for SIH26066, do they cover 2021, and how does each one's grid line up with ours?

Everything below is read from the JSON the audit/download code wrote (`data/audit/`), nothing is typed by hand.
Code: `src/oceanembed_ml/audit/`, `src/oceanembed_ml/data/download_*.py`."""),
("code", SETUP),
("md", "## Canonical grid (single source of truth: `configs/grid.yaml`)"),
("code", """grid = load_yaml("grid.yaml"); d = grid["domain"]
print(f"lat {d['lat_min']}–{d['lat_max']}, lon {d['lon_min']}–{d['lon_max']}, res {d['res']}°")
print("depths (m):", grid["depths"])"""),
("md", "## Copernicus catalogue: variables, units, coverage"),
("code", """cat = json.loads((AUDIT/"cmems_catalogue.json").read_text())
rows = []
for pid, p in cat["products"].items():
    for ds in p.get("datasets", []):
        for v, info in ds["variables"].items():
            c = info["coords"]; t = c.get("time", {})
            rows.append(dict(product=pid, dataset=ds["dataset_id"], variable=v, units=info["units"],
                             step_deg=c.get("latitude", {}).get("step"), start=(t.get("min_iso") or "")[:10], end=(t.get("max_iso") or "")[:10]))
df = pd.DataFrame(rows)
used = ["thetao_glor","thetao","analysed_sst","sos","sla","ugos","vgos","eastward_wind","northward_wind"]
df[df.variable.isin(used) & ~df.dataset.str.contains("P1M|mnstd|nrt|demo|0.25deg_PT1H")].reset_index(drop=True)"""),
("md", "## Grid alignment → which regridding operator each source needs"),
("code", """ga = json.loads((AUDIT/"grid_alignment.json").read_text())
pd.DataFrame([{**{"source": k}, "native_step": v["native_step_deg"], "centre_offset": v["centre_offset_deg"],
               "operator": v["operator"], "GB (2021)": v["volume_estimate"]["uncompressed_GB_float32"]} for k, v in ga["sources"].items()])"""),
("md", "## ARGO (independent validation) and download verification"),
("code", """argo = json.loads((AUDIT/"argo_index_summary.json").read_text())
print({k: argo[k] for k in ["n_profiles","n_floats","n_delayed_mode","n_profiles_arabian_sea","n_profiles_bay_of_bengal"]})
pd.Series(argo["profiles_per_month"]).plot.bar(title="ARGO profiles per month in the domain (2021)"); plt.show()
rv = json.loads((AUDIT/"raw_verification.json").read_text())
pd.DataFrame(rv["sources"]).T[["n_files","expected_files","total_MB","complete"]]"""),
],
"02_harmonisation.ipynb": [
("md", """# 02 · Harmonisation onto one grid (Phase 2)
Every dataset → 0.25° cell centres, UTC daily, canonical units, ocean mask. One **conservative (area-weighted)** operator
(`src/oceanembed_ml/grid.py`) that reduces to the identity / exact block mean when grids nest."""),
("code", SETUP),
("md", "## The operator on a toy example: a 2×2 nested grid gives exactly the block mean"),
("code", """from oceanembed_ml.grid import ConservativeRegridder, LAT, LON
lat = np.round(np.arange(4.5625, 30.5, 0.125), 4); lon = np.round(np.arange(44.5625, 105.5, 0.125), 4)
x = np.random.default_rng(0).normal(size=(lat.size, lon.size))
out = ConservativeRegridder(lat, lon)(x)
print("native", x.shape, "-> canonical", out.shape)
print("constant field preserved:", np.allclose(ConservativeRegridder(lat, lon)(np.full_like(x, 7.5)), 7.5))"""),
("md", "## QC summary after harmonisation (`data/audit/harmonisation_qc.json`)"),
("code", """qc = json.loads((AUDIT/"harmonisation_qc.json").read_text())
rows = [{"source": s, "var": v, **{k: r.get(k) for k in ["valid_frac_over_ocean","n_ocean_cells_never_valid","n_out_of_range_set_nan","min","max"]}}
        for s, d in qc.items() if s != "glorys" for v, r in d.items() if isinstance(r, dict) and "min" in r]
print("ocean cells:", qc["glorys"]["masks"]["n_ocean_cells"])
pd.DataFrame(rows)"""),
("md", "## Native vs harmonised (2021-08-15)"),
("code", """for f in ["compare_sst.png","compare_sss.png","compare_sla.png","compare_u10.png","compare_thetao.png","masks.png"]:
    display(Image(filename=str(FIGURES/"phase2"/f)))"""),
("md", "**Note (decision D-016):** a 35 °C plausibility cap would have deleted real Persian Gulf summer SST (up to 36.7 °C); the cap is 38 °C."),
],
"03_eda.ipynb": [
("md", """# 03 · Exploratory data analysis (Phase 3)
Descriptive statistics use all days; every **relationship** analysis uses **train days only** (no peeking at test months).
Code: `src/oceanembed_ml/eda/`."""),
("code", SETUP),
("code", """cube = xr.open_dataset(PROCESSED/"cube.nc")
print(cube)
print(pd.Series(cube.split.values).value_counts())"""),
("md", "## Input statistics"),
("code", """S = json.loads((AUDIT/"eda_stats.json").read_text())
pd.DataFrame(S["inputs"]).T[["mean","std","min","p01","median","p99","max","skew","missing_frac_ocean"]].round(3)"""),
("md", "## Target by depth: absolute variability vs anomaly left after removing the climatology"),
("code", """dep = load_yaml("grid.yaml")["depths"]
t = pd.DataFrame({"abs_std": [S["target_by_depth"][str(d)]["std"] for d in dep],
                  "anomaly_std": [S["anomaly_std_by_depth"][str(d)] for d in dep]}, index=pd.Index(dep, name="depth_m"))
plt.figure(figsize=(5,6)); plt.plot(t.abs_std, dep, "o-", label="absolute"); plt.plot(t.anomaly_std, dep, "s-", label="anomaly")
plt.gca().invert_yaxis(); plt.xlabel("std (°C)"); plt.ylabel("depth (m)"); plt.legend(); plt.title("what the model has to learn"); plt.show()
t.round(2).T"""),
("md", "## Which surface variables carry information at which depth (Spearman, train days)"),
("code", """display(Image(filename=str(FIGURES/"phase3"/"09_feature_target_corr_by_depth.png")))
a = pd.DataFrame(S["feature_target_spearman_train"]["anomaly"]).T
a[["0","50","100","150","300","1000"]].round(2).sort_values("100", key=abs, ascending=False)"""),
("md", "## Vertical structure: PCA of anomaly profiles"),
("code", """p = S["pca_anomaly_profiles_train"]
print("components for 90%:", p["n_components_90pct"], "| for 95%:", p["n_components_95pct"])
display(Image(filename=str(FIGURES/"phase3"/"10_depth_correlation_and_pca.png")))"""),
("md", "## Regions, seasons, Hovmöller"),
("code", """for f in ["07_profiles_region_season_variance.png","06_hovmoller_T100_anomaly_10N.png","02_target_mean_maps.png"]:
    display(Image(filename=str(FIGURES/"phase3"/f)))"""),
("md", "## Outliers: measurement error or real event?"),
("code", """o = json.loads((AUDIT/"outlier_report.json").read_text())
print("random ocean value near a cyclone:", round(o["random_ocean_value_frac_near_cyclone"], 3))
display(pd.DataFrame(o["variables"]).T[["n_flagged","frac_of_ocean_values","frac_flags_near_cyclone_300km_7d","action"]])
display(Image(filename=str(FIGURES/"phase3"/"12_outliers_cyclones.png")))"""),
],
"04_features.ipynb": [
("md", """# 04 · Feature engineering (Phase 4)
Features are computed **on the grid** (so neighbours exist), then flattened into one row per ocean cell-day.
Definitions: `configs/features.yaml`; code: `src/oceanembed_ml/features/`. Leakage tests: `tests/test_features.py`."""),
("code", SETUP),
("code", """F = load_yaml("features.yaml")["groups"]
pd.DataFrame([(g, ", ".join(c), len(c)) for g, c in F.items()], columns=["group","features","n"])"""),
("code", """fs = json.loads((AUDIT/"features_summary.json").read_text())
pd.DataFrame({k: {kk: v[kk] for kk in ["rows","days","columns","months","date_range","size_MB"]} for k, v in fs["tables"].items()}).T"""),
("md", "## Train-table sample (300k rows) — how each feature relates to the anomaly at 100 m and 1000 m"),
("code", """import pyarrow.parquet as pq
feat = [c for g in F.values() for c in g]
tr = pq.read_table(FINAL/"features"/"train.parquet").to_pandas().sample(300_000, random_state=42)
corr = pd.DataFrame({d: tr[feat].corrwith(tr[f"a_d{k:02d}"], method="spearman") for d, k in [("0 m",0),("100 m",7),("300 m",11),("1000 m",14)]})
corr.round(2).sort_values("100 m", key=abs, ascending=False)"""),
("code", """fig, ax = plt.subplots(1, 3, figsize=(15, 4))
tr.plot.hexbin(x="sla", y="a_d07", gridsize=60, bins="log", ax=ax[0], title="SLA vs anomaly at 100 m")
tr.plot.hexbin(x="ekman_mean7", y="a_d07", gridsize=60, bins="log", ax=ax[1], title="7-day Ekman pumping vs anomaly 100 m"); ax[1].set_xlim(-2, 2)
tr.plot.hexbin(x="sst_anom", y="a_d00", gridsize=60, bins="log", ax=ax[2], title="SST anomaly vs anomaly at 0 m")
plt.tight_layout(); plt.show()"""),
("md", "## Missing values per feature (handled inside model pipelines in Phase 5, not here)"),
("code", """nan = pd.DataFrame({k: v["feature_nan_frac"] for k, v in fs["tables"].items()})
nan[nan.max(axis=1) > 0].sort_values("train", ascending=False)"""),
("md", "## PCA surface embedding (fit on train days only)"),
("code", """e = np.load(FINAL/"features"/"embedding_pca.npz")
plt.bar(range(1, 9), e["explained_variance_ratio"]); plt.plot(range(1, 9), np.cumsum(e["explained_variance_ratio"]), "ko-")
plt.title("explained variance of 3×3×7 surface patches"); plt.xlabel("component"); plt.show()"""),
],
}


def build(name: str, cells: list) -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in cells]
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(NB)}}).execute()
    nbf.write(nb, NB / name)
    print("executed ->", (NB / name).relative_to(ROOT), flush=True)


if __name__ == "__main__":
    NB.mkdir(exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    for n, c in NOTEBOOKS.items():
        if n.startswith(only):
            build(n, c)
