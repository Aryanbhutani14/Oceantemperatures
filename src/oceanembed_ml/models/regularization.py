"""Regularisation study: show overfitting and how regularisation controls it.

Validation curves (training score vs cross-validated score, GroupKFold by month,
train months only) for:

  A. Ridge on a deliberately over-complex model: degree-2 polynomial features
     (40 -> 860 features) fitted on only 2,000 rows, target = anomaly at 100 m.
     Without regularisation it overfits badly; alpha restores generalisation.
     (On the full 400k-row problem Ridge = OLS, because 400k rows >> 40 features:
     regularisation only matters when model complexity is high relative to data.)
  B. Lasso on the same polynomial model: alpha vs CV error AND number of
     non-zero coefficients (L1 = built-in feature selection).
  C. Decision-tree classifier (TCHP >= 60): max_depth vs train/CV accuracy
     -> depth limit / min_samples_leaf are tree regularisers.
  D. Logistic regression (TCHP >= 60): C = 1/lambda vs train/CV AUC.
  E. Gradient boosting regression (100 m): number of boosting iterations at
     two learning rates (shrinkage = boosting's regulariser).

Output: results/phase7/regularization.json, reports/figures/phase7/04_regularization_curves.png
"""
from __future__ import annotations

import json
import sys
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import Lasso, LinearRegression, LogisticRegression, Ridge  # noqa: E402
from sklearn.model_selection import GroupKFold, validation_curve  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import PolynomialFeatures, StandardScaler  # noqa: E402
from sklearn.tree import DecisionTreeClassifier  # noqa: E402

from oceanembed_ml.classification import task  # noqa: E402
from oceanembed_ml.config import FIGURES, ROOT  # noqa: E402
from oceanembed_ml.models import data as D  # noqa: E402

warnings.filterwarnings("ignore")
RES, FIG = ROOT / "results" / "phase7", FIGURES / "phase7"
K100 = 7
CV = GroupKFold(n_splits=4)


def vc(est, X, y, g, name, rng, scoring):
    tr, te = validation_curve(est, X, y, groups=g, param_name=name, param_range=rng, cv=CV, scoring=scoring, n_jobs=-1)
    return tr.mean(1), te.mean(1), te.std(1)


def main() -> int:
    RES.mkdir(parents=True, exist_ok=True); FIG.mkdir(parents=True, exist_ok=True)
    out = {}
    train = D.load("train")
    small = train[np.isfinite(train[D.A_COLS[K100]])].sample(n=2000, random_state=3)
    X, y, g = small[D.ALL_FEATURES].to_numpy("float64"), small[D.A_COLS[K100]].to_numpy(), small["month"].to_numpy()
    poly = lambda est: make_pipeline(SimpleImputer(strategy="median"), PolynomialFeatures(2), StandardScaler(), est)  # noqa: E731

    # A. Ridge on polynomial features
    alphas = np.logspace(-3, 4, 15)
    tr, te, sd = vc(poly(Ridge()), X, y, g, "ridge__alpha", alphas, "neg_root_mean_squared_error")
    ols_tr, ols_te, _ = vc(poly(LinearRegression()), X, y, g, "linearregression__fit_intercept", [True], "neg_root_mean_squared_error")
    out["ridge_poly"] = {"alpha": alphas.tolist(), "train_rmse": (-tr).tolist(), "cv_rmse": (-te).tolist(),
                         "unregularised_train_rmse": float(-ols_tr[0]), "unregularised_cv_rmse": float(-ols_te[0]),
                         "best_alpha": float(alphas[np.argmax(te)]), "best_cv_rmse": float(-te.max()), "n_features": 861}
    print(f"  ridge poly: OLS train {-ols_tr[0]:.3f} / CV {-ols_te[0]:.3f}  -> best alpha {alphas[np.argmax(te)]:.3g} CV {-te.max():.3f}", flush=True)

    # B. Lasso on polynomial features (+ sparsity)
    la = np.logspace(-3, 0, 10)
    trl, tel, _ = vc(poly(Lasso(max_iter=5000)), X, y, g, "lasso__alpha", la, "neg_root_mean_squared_error")
    nnz = [int((poly(Lasso(alpha=a, max_iter=5000)).fit(X, y)[-1].coef_ != 0).sum()) for a in la]
    out["lasso_poly"] = {"alpha": la.tolist(), "train_rmse": (-trl).tolist(), "cv_rmse": (-tel).tolist(), "nonzero_coefs": nnz}
    print(f"  lasso poly: best alpha {la[np.argmax(tel)]:.3g} CV {-tel.max():.3f}, non-zero {nnz[int(np.argmax(tel))]} of 861", flush=True)

    # C/D. classification curves (TCHP >= 60)
    cl = task.load("train", n=40_000, seed=5)
    Xc, yc, gc = cl[task.FEATURES].to_numpy("float32"), cl["label"].to_numpy(), cl["month"].to_numpy()
    depths = [1, 2, 4, 6, 8, 10, 12, 16, 20, 25, 30]
    trd, ted, _ = vc(make_pipeline(SimpleImputer(strategy="median"), DecisionTreeClassifier(random_state=0)), Xc, yc, gc,
                     "decisiontreeclassifier__max_depth", depths, "accuracy")
    out["tree_depth"] = {"max_depth": depths, "train_acc": trd.tolist(), "cv_acc": ted.tolist(), "best_depth": depths[int(np.argmax(ted))]}
    print(f"  tree depth: best {depths[int(np.argmax(ted))]} CV acc {ted.max():.3f}; depth 30 train {trd[-1]:.3f} vs CV {ted[-1]:.3f}", flush=True)
    Cs = np.logspace(-5, 2, 10)
    trc, tec, _ = vc(make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=500)), Xc, yc, gc,
                     "logisticregression__C", Cs, "roc_auc")
    out["logistic_C"] = {"C": Cs.tolist(), "train_auc": trc.tolist(), "cv_auc": tec.tolist(), "best_C": float(Cs[int(np.argmax(tec))])}

    # E. boosting shrinkage
    big = train[np.isfinite(train[D.A_COLS[K100]])].sample(n=60_000, random_state=4)
    Xb, yb, gb = big[D.ALL_FEATURES].to_numpy("float32"), big[D.A_COLS[K100]].to_numpy(), big["month"].to_numpy()
    iters = [25, 50, 100, 200, 400, 800]
    out["boosting"] = {"iterations": iters}
    for lr in (0.05, 0.3):
        t1, t2, _ = vc(HistGradientBoostingRegressor(learning_rate=lr, random_state=0), Xb, yb, gb, "max_iter", iters, "neg_root_mean_squared_error")
        out["boosting"][f"lr_{lr}"] = {"train_rmse": (-t1).tolist(), "cv_rmse": (-t2).tolist()}
    (RES / "regularization.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    plot(out)
    return 0


def plot(o):
    fig, ax = plt.subplots(1, 5, figsize=(26, 5), constrained_layout=True)
    r = o["ridge_poly"]
    ax[0].semilogx(r["alpha"], r["train_rmse"], "o-", label="training"); ax[0].semilogx(r["alpha"], r["cv_rmse"], "s-", label="cross-validation")
    ax[0].axhline(r["unregularised_cv_rmse"], c="r", ls=":", label=f"no regularisation (CV {r['unregularised_cv_rmse']:.2f})")
    ax[0].set_ylim(0, min(3, max(r["cv_rmse"]) * 1.3)); ax[0].set_xlabel("Ridge alpha (λ)"); ax[0].set_ylabel("RMSE (°C), anomaly at 100 m")
    ax[0].set_title("A. Ridge, 861 polynomial features, 2k rows"); ax[0].legend(fontsize=8)
    l = o["lasso_poly"]
    ax[1].semilogx(l["alpha"], l["train_rmse"], "o-", label="training"); ax[1].semilogx(l["alpha"], l["cv_rmse"], "s-", label="cross-validation")
    a2 = ax[1].twinx(); a2.semilogx(l["alpha"], l["nonzero_coefs"], "g^--", label="non-zero coefficients"); a2.set_ylabel("non-zero coefficients", color="g")
    ax[1].set_xlabel("Lasso alpha"); ax[1].set_title("B. Lasso: error and sparsity"); ax[1].legend(fontsize=8, loc="upper left")
    t = o["tree_depth"]
    ax[2].plot(t["max_depth"], t["train_acc"], "o-", label="training"); ax[2].plot(t["max_depth"], t["cv_acc"], "s-", label="cross-validation")
    ax[2].axvline(t["best_depth"], c="k", ls=":"); ax[2].set_xlabel("max_depth"); ax[2].set_ylabel("accuracy"); ax[2].set_title("C. Decision tree (TCHP ≥ 60)"); ax[2].legend(fontsize=8)
    c = o["logistic_C"]
    ax[3].semilogx(c["C"], c["train_auc"], "o-", label="training"); ax[3].semilogx(c["C"], c["cv_auc"], "s-", label="cross-validation")
    ax[3].set_xlabel("C = 1/λ (smaller = stronger regularisation)"); ax[3].set_ylabel("ROC-AUC"); ax[3].set_title("D. Logistic regression (TCHP ≥ 60)"); ax[3].legend(fontsize=8)
    b = o["boosting"]
    for lr, cc in (("0.05", "tab:blue"), ("0.3", "tab:red")):
        ax[4].semilogx(b["iterations"], b[f"lr_{lr}"]["train_rmse"], "o--", c=cc, label=f"training, lr {lr}")
        ax[4].semilogx(b["iterations"], b[f"lr_{lr}"]["cv_rmse"], "s-", c=cc, label=f"CV, lr {lr}")
    ax[4].set_xlabel("boosting iterations"); ax[4].set_ylabel("RMSE (°C), anomaly at 100 m"); ax[4].set_title("E. Gradient boosting: shrinkage"); ax[4].legend(fontsize=8)
    for a in ax:
        a.grid(alpha=0.3)
    fig.savefig(FIG / "04_regularization_curves.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
