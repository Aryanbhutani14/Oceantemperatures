"""Classification models: tuning (GridSearchCV + GroupKFold by month) and test evaluation.

Models (CSE2032 syllabus): Logistic Regression (L2 and L1 regularisation), SVM (RBF),
Decision Tree, KNN, Random Forest, Gradient Boosting; baselines: majority class and the
"climatology rule" (predict 1 if the climatological TCHP >= 60).

Selection metric: ROC-AUC on GroupKFold(4) by month (train months only).
Test: the same fixed 100k test rows for every model -> accuracy, precision, recall,
F1, ROC-AUC, confusion matrix, ROC curve.
Outputs: results/phase7/classification.json, models/phase7/*.joblib, figures.
"""
from __future__ import annotations

import json
import sys
import time
import warnings

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score, recall_score,  # noqa: E402
                             roc_auc_score, roc_curve)
from sklearn.model_selection import GridSearchCV, GroupKFold  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402
from sklearn.tree import DecisionTreeClassifier  # noqa: E402

from oceanembed_ml.classification import task  # noqa: E402
from oceanembed_ml.config import FIGURES, ROOT  # noqa: E402

warnings.filterwarnings("ignore")
RES, MOD, FIG = ROOT / "results" / "phase7", ROOT / "models" / "phase7", FIGURES / "phase7"
SEED = 42


def lin(est):
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("clf", est)])


def tree(est):
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("clf", est)])


# name -> (pipeline, grid, n_train, syllabus topic)
MODELS = {
    "logistic_l2": (lin(LogisticRegression(max_iter=500)), {"clf__C": [0.001, 0.01, 0.1, 1, 10]}, 300_000, "Logistic Regression (L2)"),
    "logistic_l1": (lin(LogisticRegression(penalty="l1", solver="liblinear", max_iter=500)), {"clf__C": [0.001, 0.01, 0.1, 1]}, 300_000, "Logistic Regression (L1 / Lasso-style)"),
    "svm_rbf": (lin(SVC(kernel="rbf", gamma="scale", cache_size=2000)), {"clf__C": [0.3, 1, 3]}, 8_000, "SVM (RBF kernel)"),
    "decision_tree": (tree(DecisionTreeClassifier(random_state=SEED)), {"clf__max_depth": [4, 8, 12, 16, 24], "clf__min_samples_leaf": [1, 20]}, 300_000, "Decision Tree"),
    "knn": (lin(KNeighborsClassifier(n_jobs=-1)), {"clf__n_neighbors": [5, 15, 41]}, 100_000, "KNN"),
    "random_forest": (tree(RandomForestClassifier(n_estimators=150, max_depth=20, min_samples_leaf=5, n_jobs=-1, random_state=SEED)),
                      {"clf__max_features": [0.2, 0.5]}, 300_000, "Random Forest (bagging ensemble)"),
    "gradient_boosting": (HistGradientBoostingClassifier(max_iter=400, random_state=SEED),
                          {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [31, 63], "l2_regularization": [0.0, 1.0]}, 300_000, "Gradient Boosting (boosting ensemble)"),
}


def scores(y, s, thr=0.5):
    p = (s >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0, 1]).ravel()
    return {"accuracy": accuracy_score(y, p), "precision": precision_score(y, p, zero_division=0),
            "recall": recall_score(y, p, zero_division=0), "f1": f1_score(y, p, zero_division=0),
            "roc_auc": roc_auc_score(y, s) if len(np.unique(s)) > 2 else float("nan"),
            "specificity": tn / (tn + fp), "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def main() -> int:
    for d in (RES, MOD, FIG):
        d.mkdir(parents=True, exist_ok=True)
    F = task.FEATURES
    print("[clf] building labels ...", flush=True)
    train = task.load("train")
    test = task.load("test", n=100_000, seed=7)
    tune = train.sample(n=60_000, random_state=1).reset_index(drop=True)
    out = {"task": f"TCHP >= {task.THRESHOLD} kJ cm-2 (favourable for cyclone intensification)",
           "positive_rate": {"train": float(train.label.mean()), "test_eval": float(test.label.mean())},
           "n_rows": {"train_total": len(train), "tune": len(tune), "test_eval": len(test)},
           "features": len(F), "models": {}}
    Xt, yt = test[F].to_numpy("float32"), test["label"].to_numpy()
    roc_store = {}

    # baselines
    maj = int(train.label.mean() >= 0.5)
    out["models"]["majority_class"] = {"topic": "baseline", **scores(yt, np.full(len(yt), float(maj)))}
    rule = (test["clim_tchp"].fillna(0).to_numpy() >= task.THRESHOLD).astype(float)
    out["models"]["climatology_rule"] = {"topic": "baseline (clim TCHP >= 60)", **scores(yt, rule)}
    roc_store["climatology_rule"] = rule

    gkf = GroupKFold(n_splits=4)
    for name, (pipe, grid, n_train, topic) in MODELS.items():
        sub = tune if n_train >= len(tune) else tune.sample(n=n_train, random_state=2)
        t0 = time.time()
        gs = GridSearchCV(pipe, grid, scoring="roc_auc", cv=gkf, n_jobs=1 if name in ("random_forest", "knn") else -1, refit=False)
        gs.fit(sub[F].to_numpy("float32"), sub["label"].to_numpy(), groups=sub["month"].to_numpy())
        best = gs.best_params_
        trials = [{"params": {k.replace("clf__", ""): v for k, v in p.items()}, "cv_auc": float(m), "cv_std": float(s)}
                  for p, m, s in zip(gs.cv_results_["params"], gs.cv_results_["mean_test_score"], gs.cv_results_["std_test_score"])]
        tr = train.sample(n=min(n_train, len(train)), random_state=0)
        model = pipe.set_params(**best)
        t1 = time.time(); model.fit(tr[F].to_numpy("float32"), tr["label"].to_numpy()); t_fit = time.time() - t1
        s = model.decision_function(Xt) if name == "svm_rbf" else model.predict_proba(Xt)[:, 1]
        thr = 0.0 if name == "svm_rbf" else 0.5
        res = scores(yt, s, thr)
        out["models"][name] = {"topic": topic, "best_params": {k.replace("clf__", ""): v for k, v in best.items()},
                               "cv_auc": float(gs.best_score_), "cv_trials": trials, "n_train_rows": len(tr),
                               "fit_seconds": round(t_fit, 1), "tune_seconds": round(time.time() - t0 - t_fit, 1), **res}
        roc_store[name] = s
        joblib.dump({"model": model, "features": F}, MOD / f"{name}.joblib", compress=3)
        print(f"  {name:18s} CV AUC={gs.best_score_:.4f} {out['models'][name]['best_params']} | TEST acc={res['accuracy']:.3f} "
              f"F1={res['f1']:.3f} AUC={res['roc_auc']:.4f}", flush=True)

    ranked = sorted((n for n in MODELS), key=lambda n: out["models"][n]["cv_auc"], reverse=True)
    out["selected_by_cv"] = ranked[0]
    (RES / "classification.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    np.savez_compressed(RES / "classification_scores.npz", y=yt, **{k: v for k, v in roc_store.items()})
    figures(out, yt, roc_store, test)
    print("[clf] selected by CV:", out["selected_by_cv"])
    return 0


def figures(out, y, roc_store, test):
    fig, ax = plt.subplots(figsize=(7, 6.5), constrained_layout=True)
    for n, s in roc_store.items():
        if n == "climatology_rule":
            fpr, tpr, _ = roc_curve(y, s)
            ax.plot(fpr[1], tpr[1], "ks", ms=8, label="climatology rule (single point)")
            continue
        fpr, tpr, _ = roc_curve(y, s)
        ax.plot(fpr, tpr, lw=2.5 if n == out["selected_by_cv"] else 1.2, label=f"{n} (AUC {out['models'][n]['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], "k:", lw=0.8); ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate (recall)")
    ax.set_title("ROC curves: TCHP ≥ 60 kJ cm⁻², test months"); ax.legend(fontsize=8)
    fig.savefig(FIG / "01_roc_curves.png", dpi=110); plt.close(fig)

    names = ["climatology_rule", out["selected_by_cv"], "decision_tree", "gradient_boosting"]
    fig, ax = plt.subplots(1, 4, figsize=(18, 4.3), constrained_layout=True)
    for a, n in zip(ax, names):
        c = out["models"][n]["confusion_matrix"]
        M = np.array([[c["tn"], c["fp"]], [c["fn"], c["tp"]]])
        a.imshow(M, cmap="Blues")
        for i in range(2):
            for j in range(2):
                a.text(j, i, f"{M[i, j]:,}\n({M[i, j] / M.sum():.1%})", ha="center", va="center", fontsize=10)
        a.set_xticks([0, 1], ["pred: not favourable", "pred: favourable"], fontsize=8); a.set_yticks([0, 1], ["true: no", "true: yes"], fontsize=8)
        a.set_title(f"{n}\nacc {out['models'][n]['accuracy']:.3f}, F1 {out['models'][n]['f1']:.3f}", fontsize=9)
    fig.savefig(FIG / "02_confusion_matrices.png", dpi=110); plt.close(fig)

    order = [n for n in out["models"]]
    mets = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    fig, ax = plt.subplots(figsize=(14, 5), constrained_layout=True)
    w = 0.16
    for i, m in enumerate(mets):
        ax.bar(np.arange(len(order)) + i * w, [out["models"][n].get(m, np.nan) for n in order], w, label=m)
    ax.set_xticks(np.arange(len(order)) + 2 * w, order, rotation=30, ha="right"); ax.set_ylim(0.4, 1.0); ax.legend(ncol=5)
    ax.set_title("Classification metrics on the same 100k test rows"); ax.grid(axis="y", alpha=0.3)
    fig.savefig(FIG / "03_metrics_comparison.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
