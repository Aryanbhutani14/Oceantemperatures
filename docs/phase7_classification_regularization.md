# Phase 7: Classification and regularization (completed 2026-11-17)

- **Run:** `python scripts/07_classification.py`
- **Code:** `src/oceanembed_ml/classification/{task,train_eval}.py`, `src/oceanembed_ml/models/regularization.py`
- **Results:** `results/phase7/*.json`. Figures: `reports/figures/phase7/`. Notebook: `notebooks/07_classification_regularization.ipynb`

## 1. Classification task

**Question:** *is this ocean location favourable for cyclone intensification today?* It is answered from **surface satellite data only**.

| | |
|---|---|
| Label | 1 if **TCHP ≥ 60 kJ cm⁻²** else 0. TCHP comes from the GLORYS temperature profile, using the unit-tested function from Phase 6. Values of about 50–60 kJ cm⁻² are the commonly used level above which tropical cyclones tend to intensify (Leipper & Volgenau 1972; Shay et al. 2000). |
| Why this task | It turns the regression into a decision people can act on, and is directly relevant to cyclone and disaster management. |
| Class balance | **47% positive** (balanced), so accuracy is meaningful. F1 and ROC-AUC are also reported. |
| Inputs | The same 40 surface features + `clim_tchp` (TCHP of the external climatology, known in advance, so no leakage) |
| Split | The same months as everywhere: train 8 months, test Feb, May, Aug, Nov |
| Rows | Train pool 2.07M (shelf cells without a defined TCHP removed); tuning 60k; final fit 300k (KNN 100k, SVM 8k); **identical 100k test rows** for every model |
| Tuning | `GridSearchCV`, `GroupKFold(4)` by **month**, scored by ROC-AUC |

## 2. Results: test months (100k rows)

| Model (syllabus topic) | Tuned settings (CV) | CV AUC | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|---|---|
| Majority class (baseline) | n/a | n/a | 0.534 | 0.000 | 0.000 | 0.000 | n/a |
| Climatology rule (baseline: clim TCHP ≥ 60) | n/a | n/a | 0.821 | 0.934 | **0.663** | 0.775 | n/a |
| Logistic Regression, L2 | C = 0.01 | 0.9773 | 0.927 | 0.908 | 0.937 | 0.922 | 0.983 |
| **Logistic Regression, L1** ✅ selected by CV | C = 0.01 | **0.9780** | 0.926 | 0.908 | 0.936 | 0.922 | 0.983 |
| SVM (RBF kernel) | C = 1 | 0.9740 | 0.929 | 0.920 | 0.927 | 0.924 | 0.984 |
| Decision Tree | max_depth = 4 | 0.9488 | 0.904 | 0.881 | 0.919 | 0.899 | 0.947 |
| KNN | k = 41 | 0.9572 | 0.922 | 0.902 | 0.934 | 0.918 | 0.977 |
| Random Forest (bagging ensemble) | max_features 0.2, 150 trees | 0.9734 | 0.930 | 0.920 | 0.932 | 0.926 | 0.985 |
| Gradient Boosting (boosting ensemble) | lr 0.1, 31 leaves | 0.9740 | **0.937** | **0.931** | 0.934 | **0.932** | **0.987** |

What the results show:
1. **All ML classifiers beat both baselines.**
   - The climatology rule has high precision but **misses one third of the favourable areas** (recall 0.66, 15,711 missed cases), because the climatology is too cold for 2021.
   - The ML models catch **93–94%** of them.
   - For a cyclone warning, missed cases (false negatives) are the costly error.
2. **The selected model is Logistic Regression with L1, chosen by CV AUC.**
   - On test, the ensembles are marginally better (Gradient Boosting: accuracy 0.937 vs 0.926).
   - The difference is about 1 percentage point, and logistic regression is far simpler and fully interpretable: its coefficients show which features drive the decision.
   - The model was chosen on CV, not test; **the ensembles are the best performers if pure accuracy is the goal.**
3. **A single decision tree is the weakest** (0.904). Averaging (Random Forest) or boosting trees fixes its variance: 0.930 and 0.937. This is the ensemble principle in action.
4. **Why a linear model does so well:** TCHP depends mostly on two things: how warm the surface is (SST, SST anomaly) and how deep the warm layer reaches (SLA, the climatological TCHP). The boundary between the classes is nearly linear in these features.

## 3. Regularization: overfitting shown and controlled (fig 04, GroupKFold by month)

| Experiment | Without / weak regularization | With tuned regularization | Lesson |
|---|---|---|---|
| **A. Ridge (L2)**: degree-2 polynomial features (861) on 2,000 rows, anomaly at 100 m | train RMSE 0.60 °C, **CV RMSE 5.31 °C** (severe overfitting) | α ≈ 3,000: **CV RMSE 1.25 °C** | L2 shrinks the 861 coefficients, so the model stops memorising noise |
| **B. Lasso (L1)**: same model | 346 non-zero coefficients, CV 1.69 °C | α = 0.1: **only 17 of 861 features kept**, CV 1.24 °C | L1 also does **feature selection** |
| **C. Decision-tree depth** (classification) | depth 30: train accuracy **1.000**, CV **0.873** | depth 4: CV **0.895** | Depth and leaf size are a tree's regularisers |
| **D. Logistic C = 1/λ** (classification) | C = 10⁻⁵ (too strong): CV AUC 0.962 (underfits) | C ≈ 0.01–1: CV AUC 0.978 | Too much regularization underfits; the optimum is a plateau |
| **E. Boosting shrinkage** (regression, 100 m) | learning rate 0.3: CV error **rises** after 25 trees (1.22 → 1.26) while training error keeps falling | learning rate 0.05: CV keeps improving to 400 trees (1.18) | A small learning rate is boosting's regularization |

**Why Ridge and Lasso did not beat OLS in Phase 5:** that problem has 400,000 rows and only 40 features, so there is nothing to overfit and CV correctly chose a small α. Experiment A shows that once a model is complex relative to the data, regularization matters. This explains, rather than contradicts, the Phase 5 result.

**Regularization used in the final models:**
- Gradient boosting: learning rate 0.05, L2 = 1.0, 63 leaves
- Random forest: max_depth 20, min_samples_leaf 5, bootstrap
- Logistic regression: L1 with C = 0.01
