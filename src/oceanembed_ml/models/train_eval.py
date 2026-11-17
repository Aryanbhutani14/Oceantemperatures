"""Phase 5 — model selection by cross-validation, then one-shot test evaluation.

Protocol (docs/phase5_models.md)
  1. Tuning set: 120k random rows of the TRAIN months.
     GroupKFold(4) with groups = calendar month -> each fold holds out 2 whole
     months (never random rows). Hyper-parameters are chosen by mean anomaly RMSE
     at 5 representative depths (0, 50, 100, 300, 1000 m). The test months are
     never touched here.
  2. Ensemble: the two best non-linear models by CV are averaged ON THE CV FOLDS;
     the average is kept only if it beats the best single model there.
  3. Final fit: each model is refitted with its chosen parameters on a train
     sample (size per model, see zoo.REGISTRY) for all 15 depths.
  4. Test: every model predicts the SAME fixed 200k-row subset of the test months
     (fingerprint stored). Metrics on absolute temperature per depth.

Outputs: results/phase5/{cv_selection,test_metrics}.json, predictions npz,
fitted models in models/phase5/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings

import joblib
import numpy as np
from sklearn.model_selection import GroupKFold

from oceanembed_ml.config import ROOT
from oceanembed_ml.grid import DEPTHS
from oceanembed_ml.models import data as D
from oceanembed_ml.models.metrics import evaluate, rmse_anomaly
from oceanembed_ml.models.zoo import REGISTRY, Average

warnings.filterwarnings("ignore")
RES = ROOT / "results" / "phase5"
MODELS_DIR = ROOT / "models" / "phase5"
REP = [0, 5, 7, 11, 14]                         # 0, 50, 100, 300, 1000 m
N_TUNE, N_EVAL = 120_000, 200_000
FEATURE_OVERRIDE = {"sst_only_linear": ["sst_anom", "sst"]}
MIN_ENSEMBLE_GAIN = 0.01   # an ensemble must beat the best single model's CV RMSE by >= 1% to be adopted (D-022)
NONLINEAR = {"knn", "svr_rbf", "decision_tree", "bagging_trees", "random_forest", "gradient_boosting", "pca_regression"}


def _restrict(model, depths):
    if hasattr(model, "depths"):
        model.depths = depths
    return model


def select_by_cv(cv: dict) -> str:
    """Lowest CV RMSE wins; the ensemble only if it was adopted (>= MIN_ENSEMBLE_GAIN). Never uses test scores."""
    cands = [n for n in cv if n != "climatology" and "best_cv_rmse" in cv[n] and (n != "ensemble_avg" or cv[n].get("kept"))]
    return min(cands, key=lambda n: cv[n]["best_cv_rmse"])


def cross_validate(names, tune, feats):
    gkf = GroupKFold(n_splits=4)
    groups = tune["month"].to_numpy()
    out, fold_preds = {}, {}
    for name in names:
        build, grid, n_train, topic = REGISTRY[name]
        fcols = FEATURE_OVERRIDE.get(name, feats)
        X, A, _, _ = D.matrices(tune, fcols)
        if n_train < len(tune):                    # e.g. SVR: CV on a matching-size subsample
            sub = np.random.default_rng(0).choice(len(tune), n_train, replace=False)
            X, A, g = X[sub], A[sub], groups[sub]
        else:
            g = groups
        trials = []
        for params in grid:
            t0 = time.time()
            scores, preds = [], np.full_like(A, np.nan)
            for tr, va in gkf.split(X, groups=g):
                m = _restrict(build(params), REP).fit(X[tr], A[tr])
                p = m.predict(X[va])
                preds[va] = p
                scores.append(rmse_anomaly(A[va][:, REP], p[:, REP]))
            s = np.array(scores)                  # (folds, rep depths)
            trials.append({"params": params, "cv_rmse_mean": float(s.mean()), "cv_rmse_fold_std": float(s.mean(1).std()),
                           "cv_rmse_per_rep_depth": dict(zip([str(int(DEPTHS[k])) for k in REP], s.mean(0).round(4).tolist())),
                           "seconds": round(time.time() - t0, 1)})
            if len(grid) == 1 or trials[-1]["cv_rmse_mean"] <= min(t["cv_rmse_mean"] for t in trials):
                if n_train >= len(tune):
                    fold_preds[name] = preds
        best = min(trials, key=lambda t: t["cv_rmse_mean"])
        out[name] = {"topic": topic, "best_params": best["params"], "best_cv_rmse": best["cv_rmse_mean"],
                     "best_cv_fold_std": best["cv_rmse_fold_std"], "trials": trials}
        print(f"  CV {name:20s} best {best['params']}  rmse={best['cv_rmse_mean']:.4f} ± {best['cv_rmse_fold_std']:.4f}", flush=True)
    return out, fold_preds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(REGISTRY))
    a = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    feats = D.ALL_FEATURES

    print("[phase5] loading train/test ...", flush=True)
    train = D.load("train")
    test_eval = D.load("test", n=N_EVAL, seed=7)
    tune = train.sample(n=N_TUNE, random_state=1).reset_index(drop=True)
    eval_hash = D.index_hash(test_eval)

    # ---------------- 1. cross-validated selection (train months only)
    print("[phase5] cross-validation (GroupKFold by month) ...", flush=True)
    cv, fold_preds = cross_validate(a.models, tune, feats)

    # ---------------- 2. ensemble decision on CV folds
    _, A_tune, _, _ = D.matrices(tune, feats)
    ranked = sorted((n for n in cv if n in NONLINEAR and n in fold_preds), key=lambda n: cv[n]["best_cv_rmse"])
    ensemble = None
    if len(ranked) >= 2:
        pair = ranked[:2]
        avg = np.nanmean(np.stack([fold_preds[n] for n in pair]), axis=0)
        ens_rmse = float(rmse_anomaly(A_tune[:, REP], avg[:, REP]).mean())
        best_single = cv[ranked[0]]["best_cv_rmse"]
        gain = (best_single - ens_rmse) / best_single
        keep = gain >= MIN_ENSEMBLE_GAIN
        cv["ensemble_avg"] = {"topic": "Ensemble (averaging)", "members": pair, "best_cv_rmse": ens_rmse,
                              "best_single": ranked[0], "best_single_cv_rmse": best_single,
                              "relative_gain": gain, "min_gain_required": MIN_ENSEMBLE_GAIN, "kept": bool(keep)}
        print(f"  CV ensemble {pair}: {ens_rmse:.4f} vs best single {best_single:.4f} (gain {gain:.2%}) -> {'KEEP' if keep else 'not adopted'}", flush=True)
        ensemble = pair      # always evaluated on test for the report; only ADOPTED if keep
    (RES / "cv_selection.json").write_text(json.dumps(cv, indent=1), encoding="utf-8")

    # ---------------- 3. final fits + 4. test evaluation on the identical subset
    results = {"eval_subset": {"rows": len(test_eval), "fingerprint": eval_hash, "months": sorted(test_eval.month.unique().tolist())},
               "models": {}}
    preds_store = {}
    Xe_all, _, Ye, Ce = D.matrices(test_eval, feats)
    fitted = {}
    for name in a.models:
        build, _, n_train, topic = REGISTRY[name]
        params = cv[name]["best_params"]
        fcols = FEATURE_OVERRIDE.get(name, feats)
        tr = train.sample(n=min(n_train, len(train)), random_state=0)
        X, A, _, _ = D.matrices(tr, fcols)
        Xe = test_eval[fcols].to_numpy(dtype="float32")
        t0 = time.time(); model = build(params).fit(X, A); t_fit = time.time() - t0
        t0 = time.time(); P = model.predict(Xe); t_pred = time.time() - t0
        met = evaluate(Ye, P, Ce)
        results["models"][name] = {"topic": topic, "params": params, "n_train_rows": len(tr), "n_features": len(fcols),
                                   "fit_seconds": round(t_fit, 1), "predict_seconds_200k": round(t_pred, 2), **met}
        preds_store[name] = P.astype("float32")
        fitted[name] = model
        print(f"  TEST {name:20s} RMSE={met['overall']['rmse']:.3f}  skill={met['mean_skill_over_depths']:.3f}  "
              f"RMSE@100m={met['per_depth']['100']['rmse']:.3f}  fit {t_fit:.0f}s", flush=True)
        if name in ("gradient_boosting", "random_forest", "ridge", "lasso", "linear_gd_scratch", "pca_regression"):
            joblib.dump({"model": model, "features": fcols, "params": params}, MODELS_DIR / f"{name}.joblib", compress=3)
    if ensemble:
        P = np.nanmean(np.stack([preds_store[n] for n in ensemble]), axis=0)
        met = evaluate(Ye, P, Ce)
        results["models"]["ensemble_avg"] = {"topic": "Ensemble (averaging)", "params": {"members": ensemble},
                                             "fit_seconds": sum(results["models"][n]["fit_seconds"] for n in ensemble),
                                             "predict_seconds_200k": sum(results["models"][n]["predict_seconds_200k"] for n in ensemble), **met}
        preds_store["ensemble_avg"] = P
        joblib.dump({"model": Average([fitted[n] for n in ensemble]), "features": feats, "params": {"members": ensemble}},
                    MODELS_DIR / "ensemble_avg.joblib", compress=3)
        print(f"  TEST ensemble_avg       RMSE={met['overall']['rmse']:.3f}  skill={met['mean_skill_over_depths']:.3f}", flush=True)

    # model chosen by CV (NOT by test score)
    results["selected_by_cv"] = select_by_cv(cv)
    (RES / "test_metrics.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    np.savez_compressed(RES / "eval_predictions.npz", Y=Ye, C=Ce, region=test_eval["region"].astype(str).to_numpy(),
                        month=test_eval["month"].to_numpy(), lat=test_eval["lat"].to_numpy(), lon=test_eval["lon"].to_numpy(),
                        **{f"pred_{k}": v for k, v in preds_store.items()})
    print(f"[phase5] model selected by CV: {results['selected_by_cv']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
