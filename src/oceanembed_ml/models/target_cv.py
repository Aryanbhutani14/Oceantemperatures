"""Phase 5 — decide the TARGET formulation by cross-validation (train months only).

The test-set ablation suggested absolute temperature beats the anomaly target.
Test results must not drive choices, so the three formulations are compared with
the same GroupKFold-by-month protocol used for model selection:

  anomaly            learn a = T - clim, predict clim + a_hat
  absolute           learn T directly
  anomaly+clim_feat  learn a, with clim at that depth added as an input feature

Scored on absolute temperature RMSE at the 5 representative depths.
Output: results/phase5/target_cv.json
"""
from __future__ import annotations

import json
import sys
import warnings

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

from oceanembed_ml.config import ROOT
from oceanembed_ml.grid import DEPTHS
from oceanembed_ml.models import data as D

warnings.filterwarnings("ignore")
RES = ROOT / "results" / "phase5"
REP = [0, 5, 7, 11, 14]


def main() -> int:
    cv = json.loads((RES / "cv_selection.json").read_text())
    p = cv["gradient_boosting"]["best_params"]
    train = D.load("train")
    tune = train.sample(n=120_000, random_state=1).reset_index(drop=True)   # same tuning set as model selection
    X, A, Y, C = D.matrices(tune, D.ALL_FEATURES)
    g = tune["month"].to_numpy()
    out = {"params": p, "protocol": "GroupKFold(4), groups=month, train months only; RMSE on absolute T", "variants": {}}
    for variant in ("anomaly", "absolute", "anomaly+clim_feat"):
        per = {str(int(DEPTHS[k])): [] for k in REP}
        for tr, va in GroupKFold(4).split(X, groups=g):
            for k in REP:
                Xk = np.column_stack([X, C[:, k]]) if variant == "anomaly+clim_feat" else X
                tgt = Y[:, k] if variant == "absolute" else A[:, k]
                m = np.isfinite(tgt[tr])
                mdl = HistGradientBoostingRegressor(max_iter=400, learning_rate=p["lr"], max_leaf_nodes=p["leaves"],
                                                    l2_regularization=1.0, random_state=42).fit(Xk[tr][m], tgt[tr][m])
                pred = mdl.predict(Xk[va])
                pred_T = pred if variant == "absolute" else pred + C[va, k]
                mv = np.isfinite(Y[va, k]) & np.isfinite(C[va, k])   # same rows for every variant (= Phase 5 scoring rows)
                per[str(int(DEPTHS[k]))].append(float(np.sqrt(np.mean((pred_T[mv] - Y[va, k][mv]) ** 2))))
        s = np.array(list(per.values()))
        out["variants"][variant] = {"cv_rmse_mean": float(s.mean()), "fold_std": float(s.mean(0).std()),
                                    "per_depth": {d: float(np.mean(v)) for d, v in per.items()}}
        print(f"  {variant:20s} CV RMSE (abs T) = {s.mean():.4f} ± {s.mean(0).std():.4f}  {out['variants'][variant]['per_depth']}", flush=True)
    best = min(out["variants"], key=lambda v: out["variants"][v]["cv_rmse_mean"])
    out["selected_target"] = best
    (RES / "target_cv.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("selected target by CV:", best)
    return 0


if __name__ == "__main__":
    sys.exit(main())
