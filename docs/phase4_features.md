# Phase 4: Feature engineering (completed 2026-11-17)

## Approach

Features are computed **on the 0.25° grid first**, so that spatial features (gradients, neighbourhood means, wind-stress curl, patch embedding) can use neighbouring cells. Then the cube is flattened into **one row per ocean cell-day**.

- **Code:** `src/oceanembed_ml/features/physics.py` holds the pure functions (unit-tested); `features/build.py` holds the pipeline.
- **Definitions:** `configs/features.yaml`
- **Run:** `python scripts/04_features.py` (about 1 minute)

## Feature set: 40 features in 11 groups (groups are switched on and off in Phase 5 ablations)

| Group | Features | Physical reason |
|---|---|---|
| direct (7) | sst, sss, sla, uo, vo, u10, v10 | The problem-statement inputs |
| kinematic (2) | wind_speed, current_speed | Wind mixing deepens the mixed layer; advection |
| wind forcing (4) | taux, tauy (bulk stress, Large & Pond Cd), curl_tau, **ekman_w** = curl(τ/f)/ρ₀ (m/day) | Ekman upwelling and downwelling lift or depress the thermocline (Somali, Oman, Sri Lanka dome) |
| gradients (5) | \|∇SST\|, ∂SLA/∂x, ∂SLA/∂y, \|∇SLA\|, ∇²SLA | Fronts, geostrophic slope, eddy curvature (cyclonic eddies lift isotherms) |
| neighbourhood (3) | 5×5 (1.25°) NaN-aware means of SLA, SST, SSS | Spatial context around each cell |
| temporal (5) | 7-day **trailing** means of SLA, SST and Ekman pumping; 7-day change in SLA and SST | The subsurface responds to forcing with a lag |
| anomaly (1) | sst_anom = SST − external climatology (0 m) | Matches the anomaly target |
| geographic (2) | lat, lon | Regional regime. sin/cos of lon are not used: a 60° span has no wrap-around. |
| seasonal (2) | sin(2π·doy/365.25), cos(…) | Seasonal cycle without a Dec/Jan jump |
| static (1) | bottom_depth (deepest valid standard depth) | Shelf vs open ocean |
| **embedding (8)** | PCA of standardised **3×3 × 7-variable surface patches** (63 → 8 dims) | **Compact surface summary (PCA)**: dimension reduction of the local surface pattern, a syllabus method. 8 components explain **95.2%** of the patch variance. |

**Per depth,** the table also holds `clim_dXX` (external climatology), `y_dXX` (absolute temperature) and **`a_dXX` = y − clim** (the anomaly, primary target, decision D-018).

## ML-ready tables (`data/final/features/`, Parquet + zstd, git-ignored)

| Table | Rows | Days | Months | Size |
|---|---|---|---|---|
| `train.parquet` | 2,245,320 | 189 | Jan, Mar, Apr, Jun, Jul, Sep, Oct, Dec | 617 MB |
| `test.parquet` | 1,425,600 | 120 | Feb, May, Aug, Nov | 409 MB |

- **Columns:** 92 = metadata (time, cell_id, lat/lon index, month, split, region) + 40 features + 3 × 15 depth columns.
- **Rows by region (train):** Arabian Sea 1.21M, Bay of Bengal 0.78M, other 0.26M.
- **Valid target rows (test):** 1,425,600 at 0 m, falling to 1,102,560 at 1000 m (the shelf drops out).

## Leakage controls (tested in `tests/test_features.py`, 12/12 passing)

| Risk | Control |
|---|---|
| Temporal leakage through rolling features | Windows are **trailing** (day t uses days ≤ t). The test changes future values and asserts the past features are unchanged. The 7-day window equals the 7-day buffer, so no train day's window needs a test day's target. Only surface **inputs** are averaged; the target never is. |
| Embedding / normalisation fitted on test data | PCA and its standardisation statistics are fitted on **train days only**. |
| Climatology leakage | The climatology is **external** (a multi-decade GLORYS12 product), not computed from 2021 (D-010). |
| Train/test overlap | The test asserts the month sets are disjoint and that the closest train and test days are more than 7 days apart. |
| Scaling / imputation leakage | **Not done here.** These happen inside each model's scikit-learn `Pipeline`, fitted per CV fold (Phase 5). |

## Missing values (left as NaN, documented)

- **Gradient-type features** (`sla_lap` 11%, `sla_grad`, `ekman_w`, `sst_grad` ~6%): central differences need both neighbours, so they are NaN in cells next to land.
- **`sla_change7` / `sst_change7`** (~3.7%): undefined for the first 7 days of January.
- **Raw inputs** < 0.3% (a few coastal cells).

Tree models handle NaN natively. Linear models, KNN and SVR impute with the train median inside their pipeline.

## First look at the new features (train sample, Spearman correlation with the anomaly; `notebooks/04_features.ipynb`)

| Feature | 0 m | 100 m | 300 m | 1000 m |
|---|---|---|---|---|
| sla_mean7 | 0.18 | **0.51** | 0.32 | 0.23 |
| sla | 0.19 | 0.50 | 0.32 | 0.24 |
| emb_1 (embedding) | −0.24 | **−0.44** | −0.10 | −0.18 |
| sss | −0.11 | −0.29 | 0.05 | −0.11 |
| sst_anom | **0.75** | 0.12 | 0.01 | 0.12 |
| sst | 0.26 | 0.22 | 0.03 | 0.08 |
| ekman_w | 0.04 | 0.08 | 0.03 | 0.09 |

Takeaways:
- **SST anomaly is far more informative near the surface than raw SST** (0.75 vs 0.26).
- **The PCA embedding carries thermocline information** beyond any single input.
- Wind-forcing features are weak in rank correlation, but may help nonlinear models through interactions. Phase 5 ablations will test this.
