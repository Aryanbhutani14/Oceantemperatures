# Phase 6: Evaluation, ARGO validation and ocean indicators (completed 2026-11-17)

- **Run:** `python scripts/06_evaluate.py`
- **Code:** `src/oceanembed_ml/evaluation/predict_grid.py`, `validation/argo.py`, `science/{indicators,evaluate}.py`, `viz/phase6.py`
- **Results:** `results/phase6/*.json`. Figures: `reports/figures/phase6/`. Notebook: `notebooks/06_evaluation.ipynb`

## 1. Full test grid

The final model (Gradient Boosting + climatology feature, chosen in Phase 5) predicted **all 1,425,600 ocean cell-days of the 4 test months** (120 days × 11,880 cells × 15 depths). The output is `data/final/predictions/test_predictions.nc`, which also feeds the dashboard.

| | RMSE °C | Mean skill vs climatology |
|---|---|---|
| Full test set (1.43M rows) | **0.579** | **0.637** |
| 200k evaluation subset (Phase 5) | 0.579 | 0.636 |

The 200k subset used to compare models is representative of the full test set.

**Figures:**
- `01_map_T100_tauktae.png`: truth vs prediction vs error at 100 m on 2021-05-15, during cyclone Tauktae
- `02_map_rmse_test_period.png`: error maps at 0, 100 and 300 m
- `07_daily_rmse.png`: daily error vs climatology. The ML model is better on every test day, including the cyclone days.

## 2. Independent validation against ARGO floats

| Item | Value |
|---|---|
| ARGO index entries on test days | 1,365 |
| Rejected (QC, position/time flags, land cell) | 83 |
| Matched profiles | 1,282 |
| Cell-day matchups | 1,279 (88 floats; 1,175 delayed-mode; Arabian Sea 901, Bay of Bengal 311, other 67) |
| Conversion | In-situ T → **potential temperature** with TEOS-10 (`gsw`), because GLORYS and the model predict potential temperature. For 363 profiles salinity QC was not good, so SP = 35 was assumed (effect on θ < 0.01 °C at 1000 m). |
| Collocation | Same UTC day, nearest 0.25° cell, ocean only. Several profiles in one cell-day are averaged. Vertical interpolation is allowed only across gaps ≤ 50 m (≤ 150 m below 300 m). |

| Compared with ARGO (all depths) | RMSE °C | Bias °C | r |
|---|---|---|---|
| Climatology (baseline) | 1.119 | −0.424 | 0.989 |
| **ML model** (never saw ARGO) | **0.718** | **−0.050** | **0.995** |
| GLORYS (the training target; **assimilates ARGO**, so it is the upper bound) | 0.599 | +0.004 | 0.996 |

**The model closes 77% of the gap between the climatology and GLORYS**, measured against real in-situ observations.

**Per depth** (RMSE °C: ML / GLORYS / climatology):

| Depth (m) | 0 | 10 | 30 | 50 | 100 | 125 | 200 | 300 | 500 | 1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| ML | **0.38** | **0.38** | 0.72 | 0.96 | 0.99 | 1.04 | 0.77 | 0.66 | 0.34 | 0.25 |
| GLORYS | 0.40 | 0.39 | 0.64 | 0.75 | 0.83 | 0.84 | 0.60 | 0.54 | 0.24 | 0.23 |
| Climatology | 0.76 | 0.75 | 0.95 | 1.29 | 1.66 | 1.74 | 1.22 | 0.83 | 0.43 | 0.25 |

- **At 0–10 m the ML model is closer to ARGO than GLORYS is**, because it uses satellite SST directly.
- **Climatology bias:** the climatology is up to −0.87 °C too cold at 125–150 m. The model reduces this to about −0.1 °C (fig 04).

**By region** (ML / GLORYS / climatology RMSE): Arabian Sea 0.70 / 0.60 / 1.05; Bay of Bengal 0.67 / 0.55 / 1.15.

**Caveat:** GLORYS assimilates ARGO. ARGO is therefore independent of our model and its inputs, but not of the training target.

## 3. Oceanographic indicators (`science/indicators.py`, unit-tested on profiles with known answers)

| Indicator | Definition | ML RMSE vs GLORYS | r | Climatology RMSE |
|---|---|---|---|---|
| **D20** | Depth of the 20 °C isotherm (thermocline proxy) | **10.9 m** | 0.92 | 20.6 m |
| **D26** | Depth of the 26 °C isotherm | **9.9 m** | 0.90 | 14.9 m |
| **TCHP** | ρ·cp·∫₀^D26 (T − 26) dz, cyclone heat potential | **9.5 kJ cm⁻²** | **0.97** | 19.8 kJ cm⁻² |
| **MLD** | First depth below 10 m with T < T(10 m) − 0.5 °C | **11.1 m** | 0.87 | 14.6 m |
| **OHC300** | ρ·cp·∫₀^300 T dz, upper-ocean heat content | **0.51 GJ m⁻²** | 0.93 | 1.06 GJ m⁻² |

The ML model **halves the climatology's error** for D20, TCHP and OHC300.

**Cyclones (fig 03):**
- **Tauktae** (Arabian Sea, 14 May 2021): the prediction shows the high-TCHP band along the track.
- **Yaas** (Bay of Bengal, 24 May 2021): the prediction shows the warm eddies.
- The climatology misses both, which is directly relevant to the problem statement's Disaster Management theme.

**Limits:**
- The 15 standard depths limit MLD precision (levels are 10–20 m apart near the base of the mixed layer).
- Density-based MLD and barrier-layer thickness need salinity profiles, which are not predicted.
