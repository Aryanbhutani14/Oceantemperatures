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
| 4 Features | ✅ pushed | `data/final/features/{train,test}.parquet` (2.25M / 1.43M rows, 40 features + 15×(clim, y, a)), `configs/features.yaml`, notebooks 01–04 |
| 5 Models | ✅ done (awaiting approval) | `results/phase5/*.json`, `models/phase5/*.joblib` (git-ignored), notebook 05. **Final: GB + clim feature** (target chosen by CV, D-024) → test RMSE 0.579 °C, skill 0.636; GB anomaly-only 0.634 |
| 6 Evaluation + ARGO | ✅ done (awaiting push) | `data/final/predictions/test_predictions.nc` (120 test days × 15 × 101 × 241: pred/glorys/clim), `test_indicators.nc`, `argo_matchups.parquet`, results/phase6 |
| 7 Dashboard, report, PPT | ⏳ | **The owner will provide the report and PPT formats; do NOT write them before that.** Dashboard first (owner shared a ChatGPT link for inspiration). |

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

## Phase 5 headline numbers (test months, 200k rows, absolute temperature)

| Model | RMSE °C | Skill |
|---|---|---|
| Gradient Boosting (selected) | 0.634 | 0.593 |
| Random Forest | 0.639 | 0.585 |
| Bagging | 0.651 | 0.571 |
| PCA regression | 0.653 | 0.556 |
| SVR | 0.702 | 0.481 |
| KNN | 0.721 | 0.440 |
| Linear / Ridge / Lasso | 0.738 | 0.452 |
| GD from scratch | 0.743 | 0.444 |
| Decision Tree | 0.743 | 0.447 |
| SST-only | 0.862 | 0.306 |
| Climatology | 0.999 | 0 |

- **GB per depth:** RMSE 0.38 at 0 m, 1.12 at 100 m, 0.17 at 1000 m.
- **Ensemble GB+RF:** 0.629, not adopted (CV gain 0.004% < 1%).
- **Next (Phase 6):**
  - Full-grid test predictions with the saved GB model (`models/phase5/gradient_boosting.joblib`)
  - Maps
  - ARGO collocation (convert in-situ T to θ with gsw; same UTC day, nearest cell)
  - Cyclone windows (IBTrACS)

- **Target revision (D-024):** a test ablation hinted at a better target, so the choice was re-made by CV.
  - CV RMSE: anomaly 0.5772, absolute 0.5562, **anomaly + clim feature 0.5385**.
  - Final model `models/phase5/final_model.joblib` (DepthwiseWithClim; features = 40 base + 15 clim columns).
  - Test RMSE 0.579, skill 0.636, 0.98 °C at 100 m.
- **Ablation:**
  - lat/lon matter most at depth (removing them gives 0.688).
  - Wind forcing, gradients and the embedding add nothing for boosting (they help linear models).
  - The learning curve saturates by 400k rows.

## Phase 6 headline numbers

- **Full test set (1.43M rows):** RMSE 0.579, skill 0.637.
- **ARGO** (1,279 matchups, 88 floats), RMSE / bias:
  - ML 0.718 / −0.05
  - GLORYS 0.599 / 0.00
  - Climatology 1.119 / −0.42
  - The model closes 77% of the gap. At 0–10 m ML (0.38) beats GLORYS (0.40).
- **Indicators**, ML vs clim RMSE:
  - D20 10.9 vs 20.6 m
  - D26 9.9 vs 14.9 m
  - TCHP 9.5 vs 19.8 kJ/cm² (r 0.97)
  - MLD 11.1 vs 14.6 m
  - OHC300 0.51 vs 1.06 GJ/m²
- **Cyclone figure:** Tauktae on 2021-05-14 and Yaas on 2021-05-24 (both in May, a test month).
- **Owner's priority:** time is short, so avoid extras. Dashboard next, then the report and PPT in the owner's format.
