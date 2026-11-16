# Decision log

Every methodological decision is recorded here with its date, rationale and
status.

| ID | Date | Decision | Status | Rationale |
|---|---|---|---|---|
| D-001 | 2026-11-17 | **Pure classical ML only**: no neural networks. The SIH26066 problem statement asks for deep learning; this project studies how far classical ML can go. PCA gives a classical "surface embedding". | Accepted | Academic project for CSE2032 |
| D-002 | 2026-11-17 | Canonical grid = problem-statement grid: cell centres 5–30°N × 45–105°E at 0.25° (101 × 241), daily UTC, 15 standard depths. | Accepted | Fixed by the problem statement |
| D-003 | 2026-11-17 | **Study period = one year, 2021-01-01 → 2021-12-31.** | Accepted | Submission deadline. 2021 includes cyclones Tauktae, Yaas, Gulab, Shaheen and Jawad, plus 4,071 ARGO profiles. |
| D-004 | 2026-11-17 | Target: GLORYS member of the CMEMS ensemble reanalysis (`thetao_glor`, 0.25°). Its grid centres coincide exactly with ours, so no horizontal regridding is needed. | Accepted | Audit: centre offset (0, 0) |
| D-005 | 2026-11-17 | Winds: CMEMS L4 scatterometer winds (ASCAT-based, `WIND_GLO_PHY_L4_MY_012_006`, hourly 0.125°) averaged to daily. CCMP v3.1 is optional. | Accepted | The problem statement names ASCAT; same login and server-side subsetting as the other CMEMS products |
| D-006 | 2026-11-17 | ARGO is used for validation only and never for training or tuning. | Accepted | Independence |
| D-007 | 2026-11-17 | Satellite gaps are never filled in the data cube; NaN is preserved. | Accepted | No fabricated observations |
| D-008 | 2026-11-17 | **Split by whole months:** test months = Feb, May, Aug, Nov (one per season); train months = the other 8. A 7-day buffer next to each test month is dropped from training. Cross-validation is GroupKFold with groups = month. | Accepted | With only one year, a chronological split would leave whole seasons unseen. Month blocks plus buffers limit autocorrelation leakage. **Never a random row split.** |
| D-009 | 2026-11-17 | Surface currents: DUACS geostrophic currents (`ugos`, `vgos`). OSCAR v2 is optional (needs a NASA Earthdata login). | Accepted | Same download as SLA; documented deviation from the problem statement (OSCAR = geostrophic + Ekman) |
| D-010 | 2026-11-17 | Climatology for the baseline and anomaly target = **external** GLORYS12 multi-decade monthly climatology, not computed from 2021. | Accepted | One year can't produce a climatology without leaking test months. An external climatology is leakage-free. |
| D-011 | 2026-11-17 | Model shortlist follows the CSE2032 syllabus: Linear Regression (incl. gradient descent from scratch), Ridge, Lasso, KNN, Decision Tree, Random Forest, Bagging, Gradient Boosting / AdaBoost, SVR (subsample), PCA. Optional extras: ElasticNet, XGBoost. | Accepted | Course scope, plus a little extra |
| D-012 | 2026-11-17 | Corrected product IDs: SSS = `MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013` (the planned `..._014_001` does not exist); CCMP = `CCMP_WINDS_10M6HR_L4_V3.1`. | Accepted | Phase 0 audit |
| D-013 | 2026-11-17 | Downloads are subset on the server (padded bbox 44.5–105.5°E, 4.5–30.5°N; depth 0–1046 m), month by month, written atomically (`.part` → `.nc`) and never modified afterwards. A SHA-256 manifest is kept. | Accepted | Reproducibility; restarting a run is safe |
| D-014 | 2026-11-17 | SSS dataset version `202311` is flagged for retirement on 2026-11-24. The exact version used is recorded in the download log, and the raw files are kept. | Noted | Provenance |
