# Whole-project validation audit (2026-11-17)

- **Run:** `python scripts/08_audit.py`
- **Code:** `src/oceanembed_ml/validation/audit.py`
- **Output:** `results/validation/audit.json`

The goal is to check that every number in the project is real and realistic, and to state honestly where it is optimistic.

## A. Data integrity: all checks passed

| Check | Result |
|---|---|
| Rows = days × 11,880 ocean cells (train and test) | ✅ exact (2,245,320 / 1,425,600) |
| Duplicate (time, cell) keys | 0 |
| Test months | Feb, May, Aug, Nov only; closest train and test days are 8 days apart |
| Target range | 6.0 to 35.7 °C (physical) |
| Mean profile cools with depth | ✅ |
| Profiles with an inversion > 0.5 °C below 200 m | 0.2% (physically plausible) |
| Processed target vs raw GLORYS (25 random cell-days, interpolation redone by hand) | max difference **0.00 °C** |
| Processed SST vs raw OSTIA pixels (24 random cell-days) | mean difference **0.008 °C** |
| Any single feature with \|r\| > 0.95 against the target (leakage symptom) | **No**; the strongest is sst_anom at 0.78 (0 m), sla_mean7 at 0.54 (100 m) |

## B. Stricter, more realistic tests (final model configuration)

The main test holds out whole months but trains on the months around them, so the model has seen the same year and the same ocean state. The harder setups below (150,000 scored rows each) show the realistic error.

| Setup | RMSE °C | Climatology °C | Skill | RMSE 100 m | R² 100 m |
|---|---|---|---|---|---|
| Main: whole months held out | 0.579 | 1.002 | 0.64 | 0.98 | 0.80 |
| Unseen months ahead (train Jan–Jun → test Aug, Nov) | 0.801 | 1.019 | 0.37 | 1.32 | 0.70 |
| Unseen regions (12 of 47 5° blocks held out) | 0.703 | 1.138 | 0.53 | 1.20 | 0.73 |
| Unseen regions, without lat/lon | 0.733 | 1.138 | 0.49 | 1.26 | 0.70 |
| **Unseen months and unseen regions (hardest)** | **0.869** | 1.155 | **0.33** | 1.34 | 0.76 |

**Reading:**
- The error grows by about 50% under the hardest test, but the model still beats the climatology everywhere.
- Removing lat/lon does not help on unseen regions (0.733 vs 0.703), so the model is not just memorising locations.
- The realistic expectation for genuinely new data is an RMSE of about **0.8–0.9 °C**, not 0.58.

**Classifier (TCHP ≥ 60) accuracy:**

| Model | Main | Unseen regions | Hardest |
|---|---|---|---|
| Logistic L1 | 0.928 | 0.931 | 0.951 |
| Gradient boosting | 0.938 | 0.943 | 0.929 |
| Climatology rule | 0.825 | 0.835 | 0.863 |

The accuracy stays high because most locations are far from the threshold:

| Distance of true TCHP from 60 kJ cm⁻² | Share of rows | Model accuracy | Climatology rule |
|---|---|---|---|
| Within ±10 (hard cases) | 16% | **67%** | 54% |
| 10–25 away | 25% | 93% | 72% |
| More than 25 away | 58% | 99.5% | 94% |

## C. Bootstrap confidence intervals (block bootstrap over the 120 test days, 1,000 resamples)

- Test RMSE: 0.579 °C, 95% CI [0.573, 0.585]
- Pooled skill: 0.67, 95% CI [0.66, 0.67]
- Classifier accuracy (logistic L1): 0.926, 95% CI [0.923, 0.929]

These intervals only reflect day-to-day sampling variation. Section B is the better guide to real-world error.

## Known limitations (stated in the report)

- Only one year of data (2021). Test months are interleaved with training months, so the main test is optimistic.
- GLORYS, used as the truth, is itself a model and assimilates satellite data and ARGO.
- Predictions are smoother than reality: fine eddies are underestimated.
- Accuracy for the classification task is inflated by easy cases far from the threshold.
