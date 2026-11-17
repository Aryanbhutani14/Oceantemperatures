# Phase 3: Data cube and exploratory data analysis (completed 2026-11-17)

## 1. Integrated data cube: `data/processed/cube.nc` (259 MB, not committed)

All harmonised sources are joined with an **exact coordinate join**: any mismatch in time, lat, lon or depth raises an error instead of silently aligning (`scripts/integrate/build_cube.py`).

| Content | Shape |
|---|---|
| Inputs `sst, sss, sla, uo, vo, u10, v10` | 365 days × 101 × 241 |
| Target `thetao` | 365 × 15 depths × 101 × 241 |
| External climatology `thetao_clim` | 12 months × 15 × 101 × 241 |
| Masks and day labels (`split`, `month_of_time`) | n/a |

**Train / test split** (decision D-008: whole months, never random rows):

| Split | Days | Months | Surface samples (days × 11,880 ocean cells) |
|---|---|---|---|
| train | 189 | Jan, Mar, Apr, Jun, Jul, Sep, Oct, Dec (minus buffers) | 2,245,320 |
| test | 120 | **Feb, May, Aug, Nov**: one per season | 1,425,600 |
| buffer (unused) | 56 | the 7 days on each side of every test month | 665,280 |

**Leakage rule for EDA.** Descriptive statistics use all days. Every **relationship** analysis that could influence feature or model choices (correlations, PCA) uses **train days only**.

## 2. Key findings

Numbers are from `data/audit/eda_stats.json`; figures are in `reports/figures/phase3/`.

### Physics the model must learn (fig 07)

- **Bay of Bengal vs Arabian Sea:**
  - The Bay of Bengal is warmer at the surface (~29 °C vs ~28 °C, and fresher), but **colder below 150 m** (by about 1.5–2 °C at 300–1000 m).
  - The Arabian Sea's deep water is warmer and saltier, because high-salinity water flows in from the Persian Gulf and Red Sea.
- **Seasons** change only the top ~200 m; below 300 m the profiles are almost identical.
- **Variability peaks in the thermocline:** the std of temperature is 2.2 °C at 75–100 m, against 1.0 °C at 1000 m.

### Climatology removes most of the "easy" signal (fig 07, right)

| Depth (m) | Std of absolute temperature (°C) | Std of anomaly vs climatology (°C) |
|---|---|---|
| 0 | 1.73 | **0.67** |
| 100 | 2.18 | **1.58** ← hardest |
| 300 | 1.47 | 0.40 |
| 1000 | 0.97 | **0.22** |

So the ML model has to learn the **anomaly**, which is largest at 75–150 m. Predicting deep layers is easy in absolute terms but the signal there is weak. This supports the planned target `T = climatology + ML-predicted anomaly`.

### Which inputs carry information (fig 09; Spearman correlation, train days)

| Feature | vs absolute T | vs anomaly | Interpretation |
|---|---|---|---|
| **SST** | 0.94 at 0 m, falling to ~0 by 125 m | 0.25 near the surface | Controls the mixed layer only |
| **SLA** | **0.71 at 100 m** (0.63–0.64 at 75/125 m) | **0.50–0.53 at 100–150 m** | Higher sea level means a deeper, warmer thermocline. **The key predictor at depth.** |
| **SSS** | +0.84 at 300–1000 m | ~0.1–0.3 | Mostly **regional** (salty, warm Arabian Sea vs fresh Bay of Bengal), not a day-to-day signal |
| lon / lat | up to ±0.8 at depth | small | Regional regime. Risk of the model just memorising location, so lat/lon will be ablated. |
| winds, currents | weak (≤ 0.2) | weak (≤ 0.17) | Little direct linear signal. May help through derived physics features (wind stress, Ekman pumping) in Phase 4. |
| cos(day of year) | −0.46 near the surface | small | Seasonal cycle, mostly removed by the climatology |

### Inputs are only mildly collinear (fig 08)

The strongest relationships are SST–SSS (spatial) and u10–v10. This is a reason to include Ridge, and to use Lasso for feature selection.

### Vertical structure is low-dimensional (fig 10)

- Anomalies at neighbouring depths are strongly correlated.
- **PCA:** 6 components explain 90% and 7 explain 95% of the variance of the 15-depth anomaly profiles.
- This motivates a **PCA (EOF) regression** variant: predict about 6 component scores instead of 15 depths.

### Missingness (fig 04)

Missing input data is confined to a handful of coastal cells (SST 20, SSS 30, currents 8 never valid). It is not informative, so no missing-flag features are needed. Tree models handle the few NaNs, and linear models will impute inside the training pipeline.

### Distributions (fig 11)

- SST is left-skewed (cold upwelling tail).
- SSS is left-skewed (Bay of Bengal river freshwater).
- The target at 100 m is bimodal (two regional regimes).
- Standardisation is therefore needed for linear models, KNN and SVR.

## 3. Outliers: measurement error vs real event (`scripts/eda/outliers_cyclones.py`, fig 12)

Physically impossible values were already handled in Phase 2: none remained after fixing the Persian Gulf limit.

This step **only flags** values: robust z-score > 6 against each cell's own median and MAD, or a 7-day temporal spike.

| Variable | Flagged values | Share of ocean values | Flags near a cyclone (≤300 km, ±7 days) |
|---|---|---|---|
| SST | 909 | 0.021% | **30.3%** |
| SLA | 212 | 0.005% | 0% |
| SSS | 613 | 0.014% | 1.1% |
| *random ocean value* | n/a | n/a | *2.9%* |

**SST extremes are about 10× more likely near a cyclone than chance.** They are **cyclone cold wakes**, real events (2021 storms: Tauktae 120 kt, Yaas, Gulab/Shaheen, Jawad, plus two weak systems), so **all values are kept**. SSS and SLA flags are coastal river-plume and eddy extremes, also kept. Nothing was deleted.

## 4. Implications for Phase 4 (features) and Phase 5 (models)

1. **Target:** predict the **anomaly** relative to the external climatology, then add the climatology back.
2. **Features:**
   - the 7 inputs
   - SLA-based features (SLA gradients, smoothed neighbourhood SLA)
   - wind-stress and Ekman-pumping proxies
   - wind speed
   - sin/cos of day of year
   - lat/lon, with an ablation that drops them
3. **Models:** compare linear models (Ridge/Lasso), KNN, trees and ensembles. Also try PCA regression with about 6 components.
4. **Evaluate per depth.** The 75–150 m thermocline is where models will differ most.

## Reproduce

```bash
.venv/Scripts/python scripts/integrate/build_cube.py
.venv/Scripts/python scripts/eda/eda.py
.venv/Scripts/python scripts/eda/outliers_cyclones.py
```
