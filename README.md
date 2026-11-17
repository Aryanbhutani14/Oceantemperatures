# OceanEmbed-ML: Subsurface Ocean Temperature from Satellite Surface Data with Classical Machine Learning

> **Smart India Hackathon 2026, SIH26066 (INCOIS, Ministry of Earth Sciences)**, built as the end-semester project for **CSE2032 Machine Learning** (BMU, 2026-27).

We reconstruct ocean temperature at **15 depths (0–1000 m)** over the **North Indian Ocean** from what satellites see at the surface: sea surface temperature, salinity, sea level, currents and winds.

**This project uses only classical machine learning, no neural networks.** The official problem statement suggests deep learning. We deliberately ask: *how far can carefully engineered classical ML go on this problem?*

---

## Project status

| Phase | What | Status |
|---|---|---|
| 0 | Problem and dataset audit | ✅ Complete: [inventory](docs/dataset_inventory.md) |
| 1 | Data download (6.8 GB, all files verified) | ✅ Complete: [details](docs/phase1_acquisition.md) |
| 2 | Harmonisation onto one common grid (11,880 ocean cells × 365 days × 15 depths) | ✅ Complete: [details](docs/phase2_harmonisation.md) |
| 3 | Data cube + EDA + outlier/cyclone check | ✅ Complete: [details](docs/phase3_eda.md) |
| **4** | Feature engineering (40 features, PCA surface embedding) + ML tables | ✅ **Complete**, awaiting approval: [details](docs/phase4_features.md) |
| 5 | Models (baselines → linear → KNN/SVR → trees → ensembles; PCA regression) | ⏳ |
| 6 | Evaluation (per depth, region, season, cyclone) + ARGO validation | ⏳ |
| 7 | Ocean indicators (D20, D26, TCHP, MLD) + report | ⏳ |

---

## The problem

| | |
|---|---|
| **Region** | North Indian Ocean, 5°N–30°N, 45°E–105°E (Arabian Sea + Bay of Bengal) |
| **Grid** | 0.25° × 0.25° (101 × 241 cells, 11,880 of them ocean), daily |
| **Period** | 2021 (365 days) |
| **Inputs** | SST, SSS, sea-level anomaly, surface currents U/V, 10 m winds U/V |
| **Output** | Temperature at 0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000 m |
| **Target ("truth")** | GLORYS ocean reanalysis |
| **Independent check** | 4,071 ARGO float profiles |
| **Train / test** | Test = whole months **Feb, May, Aug, Nov** (one per season); train = the other 8 months; 7-day buffers between them. **Never a random row split.** |

## Datasets

| Role | Dataset | Native resolution | Mapped to our grid by |
|---|---|---|---|
| Target | GLORYS reanalysis 0.25° (`GLOBAL_MULTIYEAR_PHY_ENS_001_031`) | 0.25°, daily, 75 levels | Exact match + linear interpolation to the 15 depths |
| Baseline | GLORYS12 monthly climatology (`GLOBAL_MULTIYEAR_PHY_001_030`) | 1/12°, monthly | 3×3 block mean |
| SST | OSTIA L4 (`SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`) | 0.05°, daily | Area-weighted conservative; K → °C |
| SSS | SMOS/SMAP multi-obs L4 (`MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013`) | 0.125°, daily | 2×2 block mean |
| SLA + currents | DUACS L4 (`SEALEVEL_GLO_PHY_L4_MY_008_047`) | 0.125°, daily | 2×2 block mean |
| Winds | ASCAT-based L4 (`WIND_GLO_PHY_L4_MY_012_006`) | 0.125°, hourly | Daily mean → 2×2 block mean |
| Validation | ARGO floats (GDAC) | profiles | Nearest cell, same day |
| Events | IBTrACS North Indian cyclone tracks | n/a | Event-based evaluation only |

Full details: [docs/dataset_inventory.md](docs/dataset_inventory.md). All decisions: [docs/decisions.md](docs/decisions.md).

## Repository layout

```text
src/oceanembed_ml/        # reusable, importable package (pip install -e .)
  config.py               #   paths + config loading
  grid.py                 #   canonical grid, conservative regridder, vertical interpolation
  audit/                  #   Phase 0: catalogue queries, grid-alignment analysis
  data/                   #   Phase 1-3: download, verify, harmonise, build cube
  eda/                    #   Phase 3: statistics/figures, outlier vs cyclone screening
  features/               #   Phase 4: physics features (pure functions) + table builder
  models/                 #   Phase 5: model pipelines (next)
  viz/                    #   figure helpers
scripts/                  # thin CLIs, one per phase: 00_audit.py ... 04_features.py, make_notebooks.py
notebooks/                # executed exploration notebooks (read outputs; no pipeline logic)
  01_data_audit.ipynb  02_harmonisation.ipynb  03_eda.ipynb  04_features.ipynb
configs/                  # grid.yaml, datasets.yaml, features.yaml (single source of truth)
tests/                    # pytest: regridding, physics features, leakage checks
docs/                     # dataset inventory, decision log, one write-up per phase
reports/figures/          # generated figures (committed)
data/audit/               # small JSON outputs of every phase (committed)
data/raw|interim|processed|final/   # pipeline data (git-ignored, rebuilt by the scripts)
```

**Raw data never goes into GitHub.** Every phase is reproducible from the commands below, and its machine-readable summary is committed in `data/audit/`.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[data,dev]"        # Windows; use .venv/bin/ on Linux/macOS
```

Downloading needs a free [Copernicus Marine](https://data.marine.copernicus.eu) account. Log in once with `copernicusmarine login` (in PowerShell: `& ".venv/Scripts/copernicusmarine.exe" login`).

## Reproduce every phase

```bash
.venv/Scripts/python -m pytest -q                                # 12 tests: regridding, features, leakage
.venv/Scripts/python scripts/00_audit.py                         # Phase 0  catalogue audit (no login)
.venv/Scripts/python scripts/01_download.py cmems --source all   # Phase 1  ~6.8 GB, resumable
.venv/Scripts/python scripts/01_download.py argo
.venv/Scripts/python scripts/01_download.py verify
.venv/Scripts/python scripts/02_harmonise.py --source glorys     # Phase 2  target + masks first
.venv/Scripts/python scripts/02_harmonise.py --source all
.venv/Scripts/python scripts/02_plots.py
.venv/Scripts/python scripts/03_build_cube.py                    # Phase 3  data cube + split labels
.venv/Scripts/python scripts/03_eda.py
.venv/Scripts/python scripts/04_features.py                      # Phase 4  features -> Parquet
.venv/Scripts/python scripts/make_notebooks.py                   # re-execute notebooks
```

## Key results so far

- **One regridding operator for every source** (area-conservative; unit-tested): identity for GLORYS, exact block means for nested grids, partial-cell weights for OSTIA.
- **Real extremes are kept, not deleted:**
  - Persian Gulf summer SST reaches 36.7 °C, so the plausibility cap is 38 °C.
  - SST extremes are **~10× more likely near 2021 cyclone tracks** than chance: they are cold wakes.
- **Sea level anomaly is the best predictor of the thermocline** (Spearman 0.71 with temperature at 100 m). **SST matters only in the top ~30 m.**
- After removing the climatology, the anomaly to learn peaks at **1.58 °C std at 100 m** (0.22 °C at 1000 m).
- **Derived features help:**
  - SST anomaly correlates 0.75 with the surface target anomaly (raw SST: 0.26).
  - The **PCA surface embedding** (8 components, 95% of patch variance) reaches −0.44 at 100 m.

![Feature-target correlation by depth](reports/figures/phase3/09_feature_target_corr_by_depth.png)

## References

- SIH26066 problem statement (INCOIS)
- Reference deep-learning implementation (methodology inspiration only): <https://github.com/AshmanRaut/OceanEmbed>
- Copernicus Marine Service products above (DOIs in [docs/dataset_inventory.md](docs/dataset_inventory.md))
- Argo (2000). Argo float data and metadata from the Global Data Assembly Centre (Argo GDAC). SEANOE. doi:10.17882/42182
- Knapp et al. (2010), IBTrACS. Bull. Amer. Meteor. Soc.
- Large & Pond (1981), drag coefficient for wind stress. J. Phys. Oceanogr.
