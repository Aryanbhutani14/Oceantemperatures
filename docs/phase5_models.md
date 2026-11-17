# Phase 5: Models, cross-validation and test evaluation (completed 2026-11-17)

- **Code:** `src/oceanembed_ml/models/`: `zoo.py` (all models), `scratch.py` (gradient descent from scratch), `metrics.py`, `train_eval.py`, `ablation.py`
- **Run:** `python scripts/05_models.py`, then `python scripts/05_ablation.py`, then `python scripts/05_plots.py`
- **Results:** `results/phase5/*.json`. Figures: `reports/figures/phase5/`. Notebook: `notebooks/05_models.ipynb`

## Formulation

- **Target:** the temperature **anomaly** at each of the 15 depths, `a = T − external climatology`.
- **Prediction:** `T̂ = climatology + â`.
- **Scoring:** all metrics are on **absolute temperature** (°C), per depth and pooled.

Handling the 15 outputs (rows below the seafloor have missing deep levels):

| Wrapper | Used by | How |
|---|---|---|
| `DepthwiseModel` | linear models, SVR, trees, boosting | One pipeline per depth, trained on rows where that depth exists |
| `NaNAwareKNN` | KNN | Neighbours are found once; each depth averages the neighbours that have a value there |
| `PCARegression` | PCA + boosting | PCA of the standardised 15-depth anomaly profile; boosting predicts K scores; inverse PCA reconstructs all depths |

**Preprocessing** (median imputation, then standardisation) lives **inside each pipeline**, so it is refitted on the training folds only.

## Protocol (no leakage, decided by CV, never by test)

1. **Tuning set:** 120k random rows from the 8 train months.
2. **Cross-validation:** `GroupKFold(4)`, **groups = calendar month**, so each fold holds out 2 whole months. Hyper-parameters are chosen by mean anomaly RMSE at 0, 50, 100, 300 and 1000 m.
3. **Ensemble rule (D-022):** average the two best non-linear models on the CV folds, and adopt the average only if it improves CV RMSE by **≥ 1%**.
4. **Final fit:** each model is refitted with its chosen settings on a train sample: 400k rows (KNN 150k, SVR 10k, for compute reasons).
5. **Test:** every model predicts the **same 200,000 rows** of the 4 test months (subset fingerprint `bd7624ba0cec7b89`).

## Cross-validation results (train months)

| Model | Syllabus topic | Chosen settings | CV RMSE (anomaly, °C) |
|---|---|---|---|
| **gradient_boosting** | Boosting | lr 0.05, 63 leaves, 400 iterations | **0.5772** |
| ensemble_avg (GB + RF) | Ensemble | n/a | 0.5771: gain **0.004% < 1%**, so **not adopted** |
| random_forest | Decision forest | 60 trees, max_features 0.66, depth 20 | 0.5873 |
| pca_regression | PCA + Boosting | K = 8 vertical modes | 0.5944 |
| bagging_trees | Bagging | 30 trees, depth 20 | 0.5978 |
| svr_rbf | SVM | RBF, C = 1 | 0.6185 |
| ridge / lasso / linear_regression | Linear, L2, L1 | ridge α = 10, lasso α = 0.0005 | 0.6268 |
| linear_gd_scratch | Gradient descent | lr 0.01, 20 epochs | 0.6293 |
| knn | KNN | k = 40 | 0.6534 |
| decision_tree | Decision tree | max_depth 8 | 0.6564 |
| sst_only_linear | Baseline | n/a | 0.7008 |
| climatology | Baseline | n/a | 0.8209 |

➡ **Selected model: Gradient Boosting**, chosen by CV. The test ranking below agrees: CV and test order the models almost identically (fig 04).

## Test-month results (identical 200k rows; absolute temperature)

| Model | RMSE °C | MAE °C | Bias °C | R² | r | Mean skill vs clim | RMSE @0 m | @50 | @100 | @300 | @1000 | Fit s | Predict s (200k) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ensemble_avg *(not adopted)* | 0.629 | 0.395 | −0.002 | 0.9930 | 0.9965 | 0.598 | 0.39 | 0.74 | 1.10 | 0.32 | 0.17 | 490 | 15.0 |
| **gradient_boosting** ✅ | **0.634** | **0.398** | **−0.002** | 0.9929 | 0.9965 | **0.593** | 0.38 | 0.75 | 1.12 | 0.32 | 0.17 | 102 | 10.7 |
| random_forest | 0.639 | 0.402 | −0.002 | 0.9928 | 0.9964 | 0.585 | 0.40 | 0.74 | 1.11 | 0.32 | 0.17 | 388 | 4.2 |
| bagging_trees | 0.651 | 0.408 | −0.002 | 0.9926 | 0.9963 | 0.571 | 0.41 | 0.76 | 1.13 | 0.33 | 0.17 | 346 | 7.7 |
| pca_regression | 0.653 | 0.415 | −0.007 | 0.9925 | 0.9963 | 0.556 | 0.43 | 0.78 | 1.12 | 0.33 | 0.18 | 27 | 3.2 |
| svr_rbf | 0.702 | 0.441 | −0.010 | 0.9914 | 0.9957 | 0.481 | 0.42 | 0.81 | 1.24 | 0.37 | 0.21 | 70 | **2729** |
| knn | 0.721 | 0.467 | −0.017 | 0.9909 | 0.9954 | 0.440 | 0.51 | 0.82 | 1.24 | 0.37 | 0.21 | 0 | 21.0 |
| ridge | 0.738 | 0.467 | 0.017 | 0.9904 | 0.9952 | 0.452 | 0.37 | 0.88 | 1.31 | 0.38 | 0.21 | 20 | 1.1 |
| linear_regression | 0.738 | 0.467 | 0.017 | 0.9904 | 0.9952 | 0.452 | 0.37 | 0.88 | 1.31 | 0.38 | 0.21 | 22 | 1.0 |
| lasso | 0.739 | 0.468 | 0.018 | 0.9904 | 0.9952 | 0.452 | 0.37 | 0.88 | 1.31 | 0.38 | 0.21 | 234 | 1.0 |
| linear_gd_scratch | 0.743 | 0.472 | 0.019 | 0.9903 | 0.9952 | 0.444 | 0.39 | 0.88 | 1.32 | 0.38 | 0.22 | 45 | 1.3 |
| decision_tree | 0.743 | 0.467 | 0.003 | 0.9903 | 0.9952 | 0.447 | 0.43 | 0.85 | 1.30 | 0.38 | 0.20 | 226 | 1.0 |
| sst_only_linear | 0.862 | 0.538 | 0.019 | 0.9870 | 0.9935 | 0.306 | 0.42 | 0.94 | 1.59 | 0.41 | 0.23 | 1 | 0.1 |
| climatology | 0.999 | 0.663 | **−0.320** | 0.9825 | 0.9921 | 0.000 | 0.72 | 1.04 | 1.76 | 0.46 | 0.24 | n/a | n/a |

**The selected model per depth** (Gradient Boosting; RMSE °C / skill / per-depth R²):

| Depth (m) | 0 | 10 | 30 | 50 | 75 | 100 | 125 | 150 | 200 | 300 | 500 | 700 | 1000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RMSE | 0.38 | 0.39 | 0.53 | 0.75 | 0.98 | **1.12** | 1.04 | 0.89 | 0.59 | 0.32 | 0.21 | 0.20 | 0.17 |
| skill | 0.72 | 0.68 | 0.51 | 0.48 | 0.59 | 0.60 | 0.61 | 0.61 | 0.58 | 0.52 | 0.59 | 0.62 | 0.47 |
| R² | 0.96 | 0.95 | 0.91 | 0.85 | 0.80 | **0.73** | 0.74 | 0.80 | 0.90 | 0.95 | 0.97 | 0.98 | 0.97 |

## What the results say

1. **Every model beats the climatology baseline.**
   - The best model cuts the error by 37% (RMSE 0.999 → 0.634 °C).
   - It also **removes the climatology's −0.32 °C bias**: 2021 was warmer than the long-term mean, and the satellite inputs carry that signal.
2. **Ensembles of trees win** (Boosting > Random Forest > Bagging > single Decision Tree).
   - Tree models capture nonlinear interactions (for example, SLA × region × season).
   - Averaging or boosting many trees fixes the high variance of a single tree: decision tree 0.743 vs random forest 0.639. This is the bias–variance trade-off from the syllabus.
3. **Linear models are a strong, interpretable baseline** (skill 0.45).
   - **Ridge and Lasso equal OLS here**: with 2.25M rows and 40 features the model is not overfitting, so regularisation has nothing to fix. CV picked a small α.
   - Lasso still shows which features carry the signal (fig 08).
4. **Gradient descent from scratch converges to the sklearn solution:**
   - 0.743 vs 0.738 RMSE
   - coefficients almost identical (fig 07)
   - the unit test asserts agreement with closed-form OLS
5. **The thermocline (75–150 m) is the hardest layer:** RMSE peaks at 1.12 °C at 100 m, as the EDA predicted. In relative terms (skill ≈ 0.6) the models do as well there as anywhere.
6. **There is a skill dip at 30–50 m**, the base of the mixed layer. A sharp, shifting gradient is hard to place from the surface alone.
7. **PCA regression** with 8 vertical modes comes close to per-depth boosting (0.653 vs 0.634) using 8 models instead of 15, and its profiles are vertically consistent by construction.
8. **Cost matters:** SVR needed **45 minutes** just to predict 200k rows (kernel methods scale badly), while boosting needs 11 s. Boosting gives the best accuracy per unit of compute.
9. **The ensemble was not adopted:** a 0.004% CV gain does not justify about 5× the training cost. That decision was made on CV, before looking at test scores.

## Ablations (boosting, same 200k test rows; `results/phase5/ablation.json`, fig 09–10)

**Feature groups**

| Feature set | Test RMSE °C | Skill |
|---|---|---|
| 7 raw inputs only | 0.787 | 0.31 |
| raw + lat/lon + season | 0.671 | 0.51 |
| all 40 | **0.634** | **0.59** |
| all − geographic (lat, lon) | 0.688 | 0.51 ← biggest single loss |
| all − temporal (7-day memory) | 0.638 | 0.59 |
| all − gradients & neighbourhood | 0.635 | 0.59 |
| all − wind forcing | 0.634 | 0.59 |
| all − PCA embedding | 0.634 | 0.59 |

**Group permutation importance** (RMSE increase in °C when a whole group is shuffled):

| Depth | Most important | Next | Then |
|---|---|---|---|
| 0 m | SST anomaly +0.44 | raw inputs +0.25 | 5×5 neighbourhood +0.19 |
| 100 m | lat/lon +0.43 | 7-day memory +0.22 | season +0.21 |
| 500 m | lat/lon +0.12 | season +0.05 | n/a |

Interpretation:
- Engineered features take skill from 0.31 to 0.59; most of the gain comes from location, season and the derived SST and SLA features.
- **Wind forcing, gradients and the PCA embedding add nothing for boosting.** The trees reconstruct the same information from the raw fields. The linear models do use the embedding heavily in the thermocline (fig 08).
- **Heavy reliance on lat/lon at depth** means the model partly learns the regional regime. That is fine for reconstruction over this fixed domain, but it is a limitation for unseen regions. This is listed for Phase 6.

**Learning curve:** 25k rows → 0.659, 100k → 0.638, 400k → 0.634. The curve is saturating, so more rows would add little and the 400k sample is adequate (D-023).

## Target formulation, decided by cross-validation (`results/phase5/target_cv.json`)

The test-set ablation suggested that predicting absolute temperature (0.586) beats the anomaly (0.634). **Test results may not drive choices**, so the question was re-asked on the **train months with the same GroupKFold-by-month CV**:

| Target | CV RMSE (absolute T, °C) |
|---|---|
| anomaly a = T − clim (used for the model comparison) | 0.5772 |
| absolute T | 0.5562 |
| **anomaly + climatology at that depth as an input feature** | **0.5385** ← chosen |

**Why:** the external climatology is itself imperfect for 2021 (bias −0.32 °C; a different 1/12° coastline). Subtracting it injects its errors into the target. Giving it to the model as a feature lets the trees learn when to trust it. The per-depth climatology feature was already specified in `configs/features.yaml` but had been left out of the first implementation; this fixes that (D-024).

## ✅ Final model: Gradient Boosting + climatology feature (`models/phase5/final_model.joblib`)

- Same 400k training rows; same 200k test rows (fingerprint checked).
- Fit 95 s; predict 200k rows in about 10 s.

| | Test RMSE °C | MAE | Bias | R² | Mean skill vs clim |
|---|---|---|---|---|---|
| Climatology | 0.999 | 0.663 | −0.320 | 0.9825 | 0 |
| Gradient Boosting (anomaly) | 0.634 | 0.398 | −0.002 | 0.9929 | 0.593 |
| **Final: GB + climatology feature** | **0.579** | **0.370** | **-0.014** | **0.9941** | **0.636** |

| Depth (m) | 0 | 10 | 30 | 50 | 75 | 100 | 125 | 150 | 200 | 300 | 500 | 700 | 1000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RMSE °C | 0.38 | 0.39 | 0.51 | 0.68 | 0.87 | 0.98 | 0.93 | 0.82 | 0.55 | 0.31 | 0.21 | 0.19 | 0.17 |
| skill | 0.72 | 0.69 | 0.54 | 0.58 | 0.68 | 0.69 | 0.69 | 0.67 | 0.63 | 0.56 | 0.61 | 0.64 | 0.51 |
| R² | 0.96 | 0.95 | 0.92 | 0.88 | 0.84 | 0.80 | 0.79 | 0.83 | 0.91 | 0.96 | 0.97 | 0.98 | 0.97 |

**Honest caveat:** the model comparison table above uses the anomaly formulation for every model, so that comparison is fair. Only the selected family (boosting) was refitted with the CV-chosen target. The other models would probably gain from the climatology feature too; that was not run, for lack of time.
