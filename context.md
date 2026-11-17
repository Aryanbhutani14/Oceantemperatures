# context.md: working reference for this project

A quick-reference file, so anyone picking this up (including the AI assistant) has the full picture without re-reading every document. **The source of truth stays in `configs/` and `docs/`**; update this file at the end of every phase.

## What and why

- **Project:** OceanEmbed-ML. Reconstruct subsurface ocean temperature at 15 depths (0–1000 m) from satellite surface data over the North Indian Ocean.
- **Origin:** SIH 2026 problem statement SIH26066 (INCOIS / Ministry of Earth Sciences). The problem statement asks for deep learning; **we deliberately use classical ML only (no neural networks)**.
- **Context:** end-semester project for **CSE2032 Machine Learning** at BMU (2026-27).
  - Grading: report + code + notebooks + presentation, demo and viva.
  - **Keep models close to the syllabus:** Linear Regression (+ gradient descent from scratch), Ridge, Lasso, Logistic Regression, SVM/SVR, Decision Tree, KNN, Random Forest, Bagging, Boosting, K-Means/DBSCAN/BIRCH, PCA/Kernel PCA, cross-validation, bootstrap, R². "Slightly more" is OK (e.g. XGBoost, ElasticNet).
- **Deadline:** submission on **2026-11-18**. Only one year of data (2021) is used for that reason.
- **Repo:** https://github.com/Aryanbhutani14/Oceantemperatures (branch `main`). Local folder: `D:\Ml project`.

## Working rules agreed with the owner

1. **Stop after every phase** and wait for explicit confirmation. Push only when asked.
2. Keep the README updated every phase (status table + reproduce commands).
3. It must be a proper GitHub Python project:
   - reusable code in `src/oceanembed_ml/`
   - thin CLIs in `scripts/`
   - notebooks in `notebooks/` for exploration and EDA only
   - raw data never committed
   - every phase produces reproducible outputs
4. No fabricated data or metrics; no data leakage; document every decision in `docs/decisions.md`.

## Fixed facts

| Item | Value |
|---|---|
| Grid | Cell centres lat 5.00–30.00, lon 45.00–105.00, step 0.25 → 101 × 241 (`configs/grid.yaml`) |
| Ocean cells | 11,880 (valid at 1000 m: 9,188) |
| Depths (m) | 0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000 |
| Period | 2021-01-01 → 2021-12-31 (365 days) |
| Split (D-008) | **test months** Feb, May, Aug, Nov; train = the other 8 months; 7-day buffers dropped → train 189 days, test 120 days, buffer 56 days |
| Cross-validation | GroupKFold, groups = month (train months only) |

## Datasets (all Copernicus Marine unless noted)

| Role | Dataset | Variables |
|---|---|---|
| Target | GLORYS ensemble member 0.25° `GLOBAL_MULTIYEAR_PHY_ENS_001_031` | `thetao_glor` (potential temperature) |
| Baseline | GLORYS12 monthly climatology `GLOBAL_MULTIYEAR_PHY_001_030` (`..._0.083deg-climatology_P1M-m`) | `thetao` |
| Inputs | OSTIA `SST_GLO_SST_L4_REP_OBSERVATIONS_010_011` | SST (K → °C) |
| | Multi-obs SSS `MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013` | SSS |
| | DUACS `SEALEVEL_GLO_PHY_L4_MY_008_047` | sla, ugos/vgos → uo/vo |
| | L4 winds `WIND_GLO_PHY_L4_MY_012_006` (hourly → daily) | u10, v10 |
| Validation | ARGO GDAC: 4,071 profiles, 99 floats, 2021 | TEMP, PSAL, PRES |
| Events | IBTrACS North Indian (NOAA) | cyclone tracks |

## Phase status

| Phase | Status | Key outputs |
|---|---|---|
| 0 Audit | ✅ pushed | `docs/dataset_inventory.md`, `data/audit/*.json` |
| 1 Download | ✅ pushed | `data/raw/**` (6.8 GB, git-ignored), `data/audit/raw_verification.json` |
| 2 Harmonise | ✅ pushed | `data/interim/*.nc`, conservative regridder in `src/oceanembed_ml/grid.py`, 6 unit tests |
| 3 Cube + EDA | ✅ pushed | `data/processed/cube.nc`, `reports/figures/phase3/`, `docs/phase3_eda.md` |
| 4 Features | ✅ committed (awaiting push approval) | `data/final/features/{train,test}.parquet` (2.25M / 1.43M rows, 40 features + 15×(clim, y, a)), `configs/features.yaml`, notebooks 01–04 |
| 5 Models | ⏳ | baselines → linear → KNN/SVR → trees → ensembles; PCA regression |
| 6 Evaluation + ARGO | ⏳ | per depth, region, season, cyclone; ARGO matchups |
| 7 Indicators + report | ⏳ | D20, D26, TCHP, MLD; final report and slides |

## Key findings so far (for the report and viva)

- **Regridding:** one conservative operator for every source. It is the identity for GLORYS, an exact 2×2/3×3 block mean for nested grids, and partial-cell weights for OSTIA.
- **Real extremes are not errors.**
  - A 35 °C cap would have deleted real Persian Gulf summer SST (up to 36.7 °C), so it was raised to 38 °C.
  - SST extremes are about 10× more likely near 2021 cyclone tracks than chance (cold wakes), so they are kept.
- **Predictors:**
  - SLA is the best predictor of the thermocline (Spearman 0.71 at 100 m).
  - SST matters only in the top ~30 m (0.94 at 0 m).
  - SSS and lon correlate with deep temperature mostly through regional differences.
- **Target:** predict the anomaly vs the external climatology. Anomaly std: 0.67 °C at 0 m, **peak 1.58 °C at 100 m**, 0.22 °C at 1000 m.
- **Vertical structure:** 6 PCA components explain 90% of the anomaly profiles (7 explain 95%).
- **Phase 4 features:**
  - sst_anom correlates 0.75 with the 0 m anomaly (raw SST 0.26).
  - The PCA patch embedding emb_1 reaches −0.44 at 100 m.
  - sla_mean7 reaches 0.51 at 100 m.
  - Gradient features are NaN next to coasts (6–11%); impute inside the pipelines.

## Code layout (Phase 4 restructure, D-021)

- **Package:** `src/oceanembed_ml` (editable install). `config.ROOT` finds the repo root (override with the `OCEANEMBED_ROOT` env var).
- **CLIs:** `scripts/NN_*.py` are thin `runpy` wrappers.
- **Notebooks:** generated and executed by `scripts/make_notebooks.py`. Add a new notebook there for each phase.
- **Phase 5 plan:**
  - Read the Parquet tables and subsample train (e.g. 300k–1M rows) for slow models (KNN, SVR).
  - Use sklearn `Pipeline` (imputer + scaler + model) inside GroupKFold by month.
  - Per-depth models on the anomaly target.
  - Write metrics JSON to `results/`.

## Environment

- Windows 11, Python 3.13 venv at `.venv/`.
- Machine: 24 GB RAM, 14-core i7-13650HX, D: drive ~98 GB free.
- Copernicus login is done (credentials stored by the toolbox; never handled in code).
- **Gotchas:**
  - PowerShell needs `& "path\to\exe"` to run a quoted path.
  - argopy 1.4 needs `erddapy<2.3`.
  - NASA CMR times out from Python requests, so use curl.
