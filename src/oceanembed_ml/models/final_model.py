"""Phase 5 — fit and test the FINAL model.

Model family chosen by CV (gradient boosting, results/phase5/cv_selection.json);
target formulation chosen by CV (results/phase5/target_cv.json). Same training
sample (400k rows, seed 0) and the same 200k-row test subset as every other model.

Outputs: models/phase5/final_model.joblib, results/phase5/final_model.json,
and the prediction is added to results/phase5/eval_predictions.npz.
"""
from __future__ import annotations

import json
import sys
import time
import warnings

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from oceanembed_ml.config import ROOT
from oceanembed_ml.models import data as D
from oceanembed_ml.models.metrics import evaluate
from oceanembed_ml.models.zoo import DepthwiseModel, DepthwiseWithClim

warnings.filterwarnings("ignore")
RES, MOD = ROOT / "results" / "phase5", ROOT / "models" / "phase5"
NAME = "final_gb_clim_feature"


def main() -> int:
    cv = json.loads((RES / "cv_selection.json").read_text())
    tcv = json.loads((RES / "target_cv.json").read_text())
    p = cv["gradient_boosting"]["best_params"]
    target = tcv["selected_target"]
    base = D.ALL_FEATURES
    est = HistGradientBoostingRegressor(max_iter=400, learning_rate=p["lr"], max_leaf_nodes=p["leaves"], l2_regularization=1.0, random_state=42)
    train = D.load("train").sample(n=400_000, random_state=0)
    ev = D.load("test", n=200_000, seed=7)
    assert D.index_hash(ev) == json.loads((RES / "test_metrics.json").read_text())["eval_subset"]["fingerprint"]
    _, A, Y, C = D.matrices(train, base)
    _, _, Ye, Ce = D.matrices(ev, base)
    if target == "anomaly+clim_feat":
        feats = base + D.C_COLS
        model, tgt = DepthwiseWithClim(est, n_base=len(base)), A
    elif target == "absolute":
        feats, model, tgt = base, DepthwiseModel(est), Y
    else:
        feats, model, tgt = base, DepthwiseModel(est), A
    X, Xe = train[feats].to_numpy("float32"), ev[feats].to_numpy("float32")
    t0 = time.time(); model.fit(X, tgt); t_fit = time.time() - t0
    t0 = time.time(); P = model.predict(Xe); t_pred = time.time() - t0
    if target == "absolute":
        P = P - Ce
    met = evaluate(Ye, P, Ce)
    res = {"name": NAME, "model": "gradient_boosting (HistGradientBoostingRegressor), one per depth", "params": p,
           "target": target, "chosen_by": "GroupKFold-by-month CV on train months (target_cv.json); test never used for the choice",
           "n_train_rows": len(train), "n_features": len(base) + (1 if target == "anomaly+clim_feat" else 0),
           "fit_seconds": round(t_fit, 1), "predict_seconds_200k": round(t_pred, 2), **met}
    (RES / "final_model.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    joblib.dump({"model": model, "features": feats, "target": target, "params": p}, MOD / "final_model.joblib", compress=3)
    T = json.loads((RES / "test_metrics.json").read_text())
    T["models"][NAME] = {"topic": "Final: Boosting + climatology feature (CV-selected)", **{k: res[k] for k in ("params", "n_train_rows", "n_features", "fit_seconds", "predict_seconds_200k")}, **met}
    T["final_model"] = NAME
    (RES / "test_metrics.json").write_text(json.dumps(T, indent=1), encoding="utf-8")
    z = dict(np.load(RES / "eval_predictions.npz", allow_pickle=True))
    z[f"pred_{NAME}"] = P.astype("float32")
    np.savez_compressed(RES / "eval_predictions.npz", **z)
    print(f"[final] {NAME}: RMSE={met['overall']['rmse']:.4f} skill={met['mean_skill_over_depths']:.3f} "
          f"RMSE@100m={met['per_depth']['100']['rmse']:.3f} (fit {t_fit:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
