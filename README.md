# OceanEmbed-ML: Subsurface Ocean Temperature from Satellite Surface Data with Classical Machine Learning

> **Smart India Hackathon 2026, SIH26066 (INCOIS, Ministry of Earth Sciences)**, built as the end-semester project for **CSE2032 Machine Learning** (BMU, 2026-27).

We reconstruct ocean temperature at **15 depths (0–1000 m)** over the **North Indian Ocean** from what satellites see at the surface: sea surface temperature, salinity, sea level, currents and winds.

**This project uses only classical machine learning, no neural networks.** The official problem statement suggests deep learning. We deliberately ask a different question: *how far can carefully engineered classical ML go on this problem?*

---

## Project status

| Phase | What | Status |
|---|---|---|
| **0** | Problem and dataset audit | ✅ **Complete**, awaiting approval |
| 1 | Data download | ⏳ Not started |
| 2 | Harmonisation onto one common grid | ⏳ |
| 3 | Integration (data cube) + EDA | ⏳ |
| 4 | Feature engineering + train/test split | ⏳ |
| 5 | Models (baselines → linear → trees → ensembles) | ⏳ |
| 6 | Evaluation (per depth, region, season) + ARGO validation | ⏳ |
| 7 | Ocean indicators (D20, D26, TCHP, MLD) + report | ⏳ |

---

## The problem

| | |
|---|---|
| **Region** | North Indian Ocean, 5°N–30°N, 45°E–105°E (Arabian Sea + Bay of Bengal) |
| **Grid** | 0.25° × 0.25° (101 × 241 = 24,341 cells), daily |
| **Period** | 2021 (one year: 365 days) |
| **Inputs (surface)** | SST, SSS, sea-level anomaly, surface currents U/V, 10 m winds U/V |
| **Output** | Temperature at 0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000 m |
| **Target ("truth")** | GLORYS ocean reanalysis |
| **Independent check** | ARGO float profiles |

## Datasets (verified in Phase 0)

| Role | Dataset | Native resolution | How it's mapped to our grid |
|---|---|---|---|
| Target | GLORYS reanalysis, 0.25° (CMEMS `GLOBAL_MULTIYEAR_PHY_ENS_001_031`) | 0.25°, daily, 75 levels | Exact match (same grid points); linear interpolation to the 15 depths |
| Baseline | GLORYS12 monthly climatology (CMEMS `GLOBAL_MULTIYEAR_PHY_001_030`) | 1/12°, monthly | 3×3 block mean |
| SST | OSTIA L4 (CMEMS `SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`) | 0.05°, daily | Area-weighted conservative regridding; Kelvin → °C |
| SSS | Multi-obs SMOS/SMAP L4 (CMEMS `MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013`) | 0.125°, daily | 2×2 block mean |
| SLA + currents | DUACS L4 (CMEMS `SEALEVEL_GLO_PHY_L4_MY_008_047`) | 0.125°, daily | 2×2 block mean |
| Winds | ASCAT-based L4 winds (CMEMS `WIND_GLO_PHY_L4_MY_012_006`) | 0.125°, hourly | Daily mean, then 2×2 block mean |
| Validation | ARGO floats (GDAC) | profiles | Nearest grid cell, same day: 4,071 profiles / 99 floats in 2021 |

Full details (units, coverage, caveats, volumes): [docs/dataset_inventory.md](docs/dataset_inventory.md).

## Key methodological choices

- **One common grid.** Every dataset is converted onto the same grid (0.25°, daily, UTC) *before* anything is joined. The regridding method for each source was chosen by measuring how its grid lines up with ours ([details](docs/dataset_inventory.md#2-grid-alignment--regridding-operator-computed-grid_alignmentjson)).
- **No invented data.** Satellite gaps stay as missing values; nothing is filled in silently.
- **No data leakage.** Test data is held out by **whole months** (Feb, May, Aug, Nov: one per season), with a 7-day buffer, never by a random row split. Ocean data is strongly correlated in space and time, so random splits would inflate scores.
- **Leakage-free baseline.** The climatology comes from an external multi-decade product, not from 2021.
- **Models from the CSE2032 syllabus:** Linear Regression (including gradient descent from scratch), Ridge, Lasso, KNN, Decision Tree, Random Forest, Bagging, Boosting, SVR and PCA.

All decisions and their reasons: [docs/decisions.md](docs/decisions.md).

## Repository layout

```text
configs/
  grid.yaml            # canonical grid, depths, regions (single source of truth)
  datasets.yaml        # every dataset: product ID, variables, role, period, splits
scripts/audit/         # Phase 0: catalogue queries + grid-alignment analysis
data/audit/            # Phase 0 results (JSON, committed)
data/raw|interim|processed|final/   # created by later phases, not committed
docs/
  dataset_inventory.md # what each dataset is, how it maps to our grid
  decisions.md         # decision log
```

## Reproduce Phase 0

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows (use .venv/bin/ on Linux/macOS)
.venv/Scripts/python scripts/audit/audit_cmems.py
.venv/Scripts/python scripts/audit/audit_podaac_argo.py
.venv/Scripts/python scripts/audit/grid_alignment_and_volume.py
```

No login is needed for the audit. Phase 1 (download) needs a free [Copernicus Marine](https://data.marine.copernicus.eu) account.

## References

- SIH26066 problem statement (INCOIS)
- Reference deep-learning implementation (methodology inspiration only): <https://github.com/AshmanRaut/OceanEmbed>
- Copernicus Marine Service products listed above (DOIs in the inventory)
- Argo (2000). Argo float data and metadata from the Global Data Assembly Centre (Argo GDAC). SEANOE. doi:10.17882/42182
