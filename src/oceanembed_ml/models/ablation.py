"""Phase 5 — ablation studies with the boosting model (same CV-chosen parameters).

  * feature groups : what each group contributes (drop-one-group and build-up)
  * target         : anomaly (y - climatology) vs absolute temperature
  * data size      : learning curve on 25k / 100k / 400k training rows
  * importance     : permutation importance by FEATURE GROUP at 0, 100, 500 m
                     (interpretation only; computed on a 20k slice of the eval subset)

Every run is scored on the same 200k test rows as the main comparison.
Output: results/phase5/ablation.json
"""
from __future__ import annotations

import json
import sys
import time
import warnings

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from oceanembed_ml.config import ROOT
from oceanembed_ml.grid import DEPTHS
from oceanembed_ml.models import data as D
from oceanembed_ml.models.metrics import evaluate
from oceanembed_ml.models.zoo import DepthwiseModel

warnings.filterwarnings("ignore")
RES = ROOT / "results" / "phase5"


def hgb(params):
    return DepthwiseModel(HistGradientBoostingRegressor(max_iter=400, learning_rate=params["lr"], max_leaf_nodes=params["leaves"],
                                                        l2_regularization=1.0, random_state=42))


def run(train, ev, feats, params, n=400_000, target="anomaly"):
    tr = train.sample(n=n, random_state=0)
    X, A, Y, C = D.matrices(tr, feats)
    Xe, _, Ye, Ce = D.matrices(ev, feats)
    t0 = time.time()
    if target == "anomaly":
        P = hgb(params).fit(X, A).predict(Xe)
    else:                                   # learn absolute temperature, convert back to anomaly for scoring
        P = hgb(params).fit(X, Y).predict(Xe) - Ce
    m = evaluate(Ye, P, Ce)
    return {"n_features": len(feats), "n_train": n, "target": target, "seconds": round(time.time() - t0, 1),
            "overall_rmse": m["overall"]["rmse"], "mean_skill": m["mean_skill_over_depths"],
            "rmse_per_depth": {k: v["rmse"] for k, v in m["per_depth"].items()}}


def group_permutation_importance(model, ev, feats, depths=(0, 7, 12), n=20_000, seed=0):
    rng = np.random.default_rng(seed)
    sub = ev.sample(n=n, random_state=seed)
    X, A, _, _ = D.matrices(sub, feats)
    base = model.predict(X)
    out = {}
    for k in depths:
        m = np.isfinite(A[:, k])
        b = np.sqrt(np.mean((base[m, k] - A[m, k]) ** 2))
        res = {}
        for g, cols in D.GROUPS.items():
            idx = [feats.index(c) for c in cols if c in feats]
            Xp = X.copy()
            Xp[:, idx] = Xp[rng.permutation(len(Xp))][:, idx]       # permute the whole group jointly
            p = model.models_[k].predict(Xp)
            res[g] = float(np.sqrt(np.mean((p[m] - A[m, k]) ** 2)) - b)
        out[str(int(DEPTHS[k]))] = {"baseline_rmse": float(b), "rmse_increase_when_group_permuted": res}
    return out


def main() -> int:
    cv = json.loads((RES / "cv_selection.json").read_text(encoding="utf-8"))
    params = cv.get("gradient_boosting", {}).get("best_params", {"lr": 0.1, "leaves": 63})
    train = D.load("train")
    ev = D.load("test", n=200_000, seed=7)
    allf = D.ALL_FEATURES
    out = {"model": "gradient_boosting", "params": params, "eval_fingerprint": D.index_hash(ev), "features": {}, "target": {}, "data_size": {}}

    feature_sets = {
        "direct_only (7 raw inputs)": D.features_for(["direct"]),
        "direct+geo+season": D.features_for(["direct", "geographic", "seasonal"]),
        "all_minus_embedding": D.features_for(drop=["embedding"]),
        "all_minus_geographic": D.features_for(drop=["geographic"]),
        "all_minus_temporal": D.features_for(drop=["temporal"]),
        "all_minus_wind_forcing": D.features_for(drop=["wind_forcing"]),
        "all_minus_gradients+neighbourhood": D.features_for(drop=["gradients", "neighbourhood"]),
        "all (40)": allf,
    }
    for name, f in feature_sets.items():
        out["features"][name] = r = run(train, ev, f, params)
        print(f"  features {name:36s} RMSE={r['overall_rmse']:.4f} skill={r['mean_skill']:.3f} ({r['seconds']}s)", flush=True)
    out["target"]["anomaly (y - climatology)"] = out["features"]["all (40)"]
    out["target"]["absolute temperature"] = r = run(train, ev, allf, params, target="absolute")
    print(f"  target absolute                         RMSE={r['overall_rmse']:.4f} skill={r['mean_skill']:.3f}", flush=True)
    for n in (25_000, 100_000):
        out["data_size"][str(n)] = r = run(train, ev, allf, params, n=n)
        print(f"  data {n:>7d}                            RMSE={r['overall_rmse']:.4f} skill={r['mean_skill']:.3f}", flush=True)
    out["data_size"]["400000"] = out["features"]["all (40)"]

    tr = train.sample(n=400_000, random_state=0)
    X, A, _, _ = D.matrices(tr, allf)
    model = hgb(params)
    model.depths = [0, 7, 12]
    model.fit(X, A)
    out["group_permutation_importance"] = group_permutation_importance(model, ev, allf)
    (RES / "ablation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("[ablation] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
