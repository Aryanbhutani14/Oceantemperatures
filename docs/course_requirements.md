# CSE2032: the 7 required components, and where each one is

| # | Requirement | What we did | Where (code · notebook · doc · figure) | Key result |
|---|---|---|---|---|
| 1 | **Exploratory Data Analysis** | Statistics (mean, std, quantiles, skew); maps; seasonal and regional patterns; time series; Hovmöller; depth profiles; correlations (train only); missingness; outliers vs cyclones | `src/oceanembed_ml/eda/` · `notebooks/03_eda.ipynb` · [phase3_eda.md](phase3_eda.md) · `reports/figures/phase3/` | SLA is the best predictor at 100 m (ρ 0.71); the anomaly peaks at 100 m; SST extremes are 10× more frequent near cyclones (real events, kept); data issues: Persian Gulf extremes, Tibetan lakes, land values in winds, coastal gaps |
| 2 | **Feature derivation** | 40 features in 11 justified groups: wind stress, Ekman pumping, SLA gradients and Laplacian, neighbourhood means, 7-day past-only means, SST anomaly, season, location, bottom depth, **PCA embedding** of surface patches; climatology feature | `src/oceanembed_ml/features/` · `configs/features.yaml` · `notebooks/04_features.ipynb` · [phase4_features.md](phase4_features.md) | SST anomaly ρ 0.75 vs raw SST 0.26; the PCA embedding explains 95% of patch variance; ablation: features raise skill from 0.31 to 0.59, and the climatology feature cuts RMSE 0.634 → 0.579 |
| 3 | **Classification** | "Favourable for cyclone intensification" (TCHP ≥ 60 kJ cm⁻²): Logistic Regression (L1, L2), SVM, Decision Tree, KNN, Random Forest, Gradient Boosting vs 2 baselines | `src/oceanembed_ml/classification/` · `notebooks/07_…ipynb` · [phase7_classification_regularization.md](phase7_classification_regularization.md) | Accuracy 0.93–0.94, F1 0.92–0.93, AUC 0.98–0.99; recall 0.94 vs 0.66 for the climatology rule |
| 4 | **Regularization** | Ridge (L2), Lasso (L1) for regression; L1/L2 logistic; tree depth and leaf size; boosting learning rate and L2; validation curves showing overfitting and its control | `src/oceanembed_ml/models/regularization.py`, `models/zoo.py` · `notebooks/07`, `05` · fig `phase7/04_regularization_curves.png`, `phase5/08_lasso_coefficients.png` | 861-feature model: CV RMSE 5.31 → 1.25 °C with Ridge; Lasso keeps 17 of 861 features; tree depth 30 train acc 1.00 vs CV 0.87 |
| 5 | **Hyperparameter tuning** | Grid search with **GroupKFold by month** (whole months held out) for every model: α (Ridge/Lasso), learning rate (GD), k (KNN), C (SVM/logistic), max_depth, max_features, learning rate, leaves, iterations, PCA components; target formulation | `models/train_eval.py`, `classification/train_eval.py`, `models/target_cv.py` · `results/phase5/cv_selection.json`, `results/phase7/classification.json` (every grid point stored) | e.g. ridge α = 10, KNN k = 40, tree depth 8 (regression) / 4 (classification), boosting lr 0.05 with 63 leaves |
| 6 | **Ensemble techniques** | Bagging, Random Forest, Gradient Boosting, averaging ensemble (with a ≥1% CV-gain rule) | `models/zoo.py` · `notebooks/05`, `07` · [phase5_models.md](phase5_models.md) | Tree RMSE 0.743 → RF 0.639 → GB 0.634 (variance reduction); classification tree 0.904 → RF 0.930 → GB 0.937 |
| 7 | **Performance analysis** | 13 regression and 9 classification models on identical test rows; RMSE, MAE, bias, R², r, skill vs climatology, % within ±1 °C; accuracy, precision, recall, F1, ROC/AUC, confusion matrices; by depth, region, season, day; **independent ARGO validation**; ocean indicators; cost (fit/predict time) | `models/metrics.py`, `evaluation/`, `validation/argo.py`, `science/` · `notebooks/05`, `06`, `07` · [phase5_models.md](phase5_models.md), [phase6_evaluation.md](phase6_evaluation.md) | Final regression RMSE 0.579 °C (clim 0.999), 92% of predictions within ±1 °C; vs ARGO 0.718 °C (clim 1.119); TCHP error halved |


## Alignment with the CSE2032 handout

| Method used | Handout topic | Status |
|---|---|---|
| Linear regression, cost function, gradient descent (from scratch) | Regression; cost function and gradient descent | In syllabus |
| Ridge, Lasso, validation curves, bias–variance | Regularization; under/overfitting | In syllabus |
| Logistic regression (L1/L2), SVM, decision tree, KNN | Classification | In syllabus |
| Bagging, random forest, gradient boosting, averaging ensemble | Ensemble learning | In syllabus |
| PCA regression, PCA summary of surface patterns | Dimension reduction (PCA) | In syllabus |
| GroupKFold CV, GridSearchCV, learning curve | Cross-validation, hyperparameter tuning | In syllabus (month grouping needed: neighbouring days are near-duplicates) |
| Accuracy, precision, recall, F1, confusion matrix, ROC/AUC, R², bootstrap CIs | Model validation and selection | In syllabus |
| Robust z-score outlier screening | Anomaly detection (density estimation) | In syllabus (z-score threshold = Gaussian density threshold) |

**Small extensions, each with a reason:**
- **SVR and KNN regression:** the syllabus teaches SVM and KNN for classification; here the same algorithms are applied to a regression target.
- **Data harmonisation, ARGO collocation, oceanographic indicators:** domain-specific data preparation needed to build a valid dataset (the course overview covers importing, processing and transforming data). These are not extra modelling methods.
- **Permutation importance and ablation:** used only to explain the results.

**Syllabus topics not used:** clustering (DBSCAN, BIRCH, K-Means), reinforcement learning, Bayesian learning, kernel PCA, neural networks, deployment. None of them is among the 7 required components.
