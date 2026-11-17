"""Phase 5 figures — all numbers read from results/phase5/*.json and saved models."""
from __future__ import annotations

import json
import warnings

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from oceanembed_ml.config import FIGURES, ROOT  # noqa: E402
from oceanembed_ml.grid import DEPTHS  # noqa: E402
from oceanembed_ml.models import data as D  # noqa: E402
from oceanembed_ml.models.metrics import evaluate  # noqa: E402

warnings.filterwarnings("ignore")
RES, MOD = ROOT / "results" / "phase5", ROOT / "models" / "phase5"
OUT = FIGURES / "phase5"
DZ = [int(d) for d in DEPTHS]


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=110)
    plt.close(fig)


def model_comparison(T, cv):
    models = T["models"]
    order = sorted(models, key=lambda m: models[m]["overall"]["rmse"])
    fig, ax = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)
    for a in ax:
        a.set_prop_cycle(color=plt.cm.tab20(np.linspace(0, 1, 20))[: len(order)])
    for m in order:
        r = [models[m]["per_depth"][str(d)]["rmse"] for d in DZ]
        s = [models[m]["per_depth"][str(d)]["skill_vs_clim"] for d in DZ]
        lw = 3 if m == T.get("final_model") else 2 if m == T["selected_by_cv"] else 1.3
        ls = "--" if m == "climatology" else "-"
        ax[0].plot(r, DZ, marker="o", ms=3, lw=lw, ls=ls, label=m)
        ax[1].plot(s, DZ, marker="o", ms=3, lw=lw, ls=ls, label=m)
    for a, t in zip(ax, ["RMSE (°C) by depth: test months", "skill vs climatology by depth (1 = perfect, 0 = climatology)"]):
        a.invert_yaxis(); a.set_ylabel("depth (m)"); a.set_title(t); a.grid(alpha=0.3)
    ax[0].set_xlabel("RMSE (°C)"); ax[1].set_xlabel("skill"); ax[1].axvline(0, c="k", lw=0.8)
    ax[1].legend(fontsize=8, loc="lower left")
    _save(fig, "01_rmse_skill_by_depth.png")

    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    x = np.arange(len(order))
    rm = [models[m]["overall"]["rmse"] for m in order]
    ax.bar(x, rm, color=["tab:red" if m == T.get("final_model") else "tab:orange" if m == T["selected_by_cv"] else "tab:blue" for m in order])
    for i, m in enumerate(order):
        ax.text(i, rm[i] + 0.01, f"skill {models[m]['mean_skill_over_depths']:.2f}\nfit {models[m]['fit_seconds']:.0f}s", ha="center", fontsize=7)
    ax.set_xticks(x, order, rotation=40, ha="right"); ax.set_ylabel("overall RMSE on test months (°C)")
    ax.set_title(f"All models, identical 200k test rows (orange = family chosen by CV, red = final model with CV-chosen target)")
    _save(fig, "02_overall_comparison.png")

    M = np.array([[models[m]["per_depth"][str(d)]["rmse"] for d in DZ] for m in order])
    fig, ax = plt.subplots(figsize=(13, 6), constrained_layout=True)
    im = ax.imshow(M, cmap="viridis_r", aspect="auto")
    ax.set_yticks(range(len(order)), order); ax.set_xticks(range(len(DZ)), DZ); ax.set_xlabel("depth (m)")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6, color="w" if M[i, j] > M.mean() else "k")
    fig.colorbar(im, label="RMSE (°C)"); ax.set_title("RMSE per model and depth (test months)")
    _save(fig, "03_rmse_heatmap.png")

    common = [m for m in order if m in cv and "best_cv_rmse" in cv[m]]
    fig, ax = plt.subplots(figsize=(6.5, 5.5), constrained_layout=True)
    xs = [cv[m]["best_cv_rmse"] for m in common]
    ys = [np.mean([models[m]["per_depth"][str(DZ[k])]["rmse"] for k in (0, 5, 7, 11, 14)]) for m in common]
    ax.scatter(xs, ys)
    for m, a_, b_ in zip(common, xs, ys):
        ax.annotate(m, (a_, b_), fontsize=7)
    lim = [min(xs + ys) * 0.95, max(xs + ys) * 1.05]
    ax.plot(lim, lim, "k:", lw=0.8); ax.set_xlabel("CV anomaly RMSE (train months)"); ax.set_ylabel("test RMSE (same 5 depths)")
    ax.set_title("Does cross-validation rank models like the test set?")
    _save(fig, "04_cv_vs_test.png")


def best_model_breakdown(T):
    best = T.get("final_model", T["selected_by_cv"])
    z = np.load(RES / "eval_predictions.npz", allow_pickle=True)
    Y, C, P = z["Y"], z["C"], z[f"pred_{best}"]
    fig, ax = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for r in ["arabian_sea", "bay_of_bengal", "other"]:
        m = z["region"] == r
        e = evaluate(Y[m], P[m], C[m])
        ax[0].plot([e["per_depth"][str(d)]["rmse"] for d in DZ], DZ, "o-", label=f"{r} (n={m.sum():,})")
    names = {2: "Feb", 5: "May", 8: "Aug", 11: "Nov"}
    for mo in (2, 5, 8, 11):
        m = z["month"] == mo
        e = evaluate(Y[m], P[m], C[m])
        ax[1].plot([e["per_depth"][str(d)]["rmse"] for d in DZ], DZ, "o-", label=names[mo])
    for a, t in zip(ax, ["by region", "by test month (season)"]):
        a.invert_yaxis(); a.legend(); a.grid(alpha=0.3); a.set_xlabel("RMSE (°C)"); a.set_title(f"{best}: RMSE {t}")
    ax[0].set_ylabel("depth (m)")
    _save(fig, "05_best_model_region_season.png")

    rng = np.random.default_rng(3)
    fig, ax = plt.subplots(1, 4, figsize=(16, 6), sharey=True, constrained_layout=True)
    full = np.isfinite(Y).all(1)
    for a, r in zip(ax, ["arabian_sea", "arabian_sea", "bay_of_bengal", "bay_of_bengal"]):
        i = rng.choice(np.where(full & (z["region"] == r))[0])
        a.plot(Y[i], DZ, "k-o", ms=3, label="GLORYS (truth)")
        a.plot(C[i], DZ, "--", c="gray", label="climatology")
        a.plot(C[i] + P[i], DZ, "r-s", ms=3, label=f"{best}")
        a.set_title(f"{r}\n{z['lat'][i]:.2f}N {z['lon'][i]:.2f}E, month {z['month'][i]}", fontsize=9); a.grid(alpha=0.3)
        a.set_xlabel("°C")
    ax[0].invert_yaxis(); ax[0].set_ylabel("depth (m)"); ax[0].legend(fontsize=8)
    _save(fig, "06_example_profiles.png")


def linear_models_insight():
    feats = D.ALL_FEATURES
    gd = joblib.load(MOD / "linear_gd_scratch.joblib")["model"]
    k = 7
    lr_gd = gd.models_[k].steps[-1][1]
    fig, ax = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    ax[0].plot(range(1, len(lr_gd.loss_history_) + 1), lr_gd.loss_history_, "o-")
    ax[0].set_xlabel("epoch"); ax[0].set_ylabel("cost J = MSE/2"); ax[0].set_title("Gradient descent from scratch: convergence (100 m)")
    ridge = joblib.load(MOD / "ridge.joblib")["model"].models_[k].steps[-1][1]
    ax[1].scatter(ridge.coef_, lr_gd.coef_)
    lim = [min(ridge.coef_.min(), lr_gd.coef_.min()), max(ridge.coef_.max(), lr_gd.coef_.max())]
    ax[1].plot(lim, lim, "k:"); ax[1].set_xlabel("Ridge coefficient (sklearn)"); ax[1].set_ylabel("GD coefficient (scratch)")
    ax[1].set_title("Coefficients at 100 m: from-scratch GD vs sklearn")
    _save(fig, "07_gradient_descent.png")

    lasso = joblib.load(MOD / "lasso.joblib")["model"]
    Cf = np.array([lasso.models_[j].steps[-1][1].coef_ for j in range(len(DZ))]).T
    fig, ax = plt.subplots(figsize=(11, 10), constrained_layout=True)
    v = np.abs(Cf).max()
    im = ax.imshow(Cf, cmap="RdBu_r", vmin=-v, vmax=v, aspect="auto")
    ax.set_yticks(range(len(feats)), feats, fontsize=7); ax.set_xticks(range(len(DZ)), DZ); ax.set_xlabel("depth (m)")
    nz = (Cf != 0).sum(0)
    ax.set_title("Lasso coefficients (standardised features). Zero = feature dropped.\nnon-zero per depth: " + ", ".join(map(str, nz)), fontsize=9)
    fig.colorbar(im)
    _save(fig, "08_lasso_coefficients.png")


def ablation_figs():
    p = RES / "ablation.json"
    if not p.exists():
        return
    ab = json.loads(p.read_text())
    fig, ax = plt.subplots(1, 3, figsize=(18, 5.5), constrained_layout=True)
    f = ab["features"]
    names = list(f)
    ax[0].barh(names, [f[n]["overall_rmse"] for n in names], color="tab:blue")
    ax[0].set_xlabel("overall RMSE (°C)"); ax[0].set_title("feature-group ablation (boosting)")
    ax[0].set_xlim(min(f[n]["overall_rmse"] for n in names) * 0.95, max(f[n]["overall_rmse"] for n in names) * 1.02)
    t = dict(ab["target"])
    fm = RES / "final_model.json"
    if fm.exists():
        f_ = json.loads(fm.read_text())
        t["anomaly + clim feature (final)"] = {"overall_rmse": f_["overall"]["rmse"], "rmse_per_depth": {k: v["rmse"] for k, v in f_["per_depth"].items()}}
    for n, c in zip(t, ["tab:green", "tab:orange", "tab:red"]):
        ax[1].plot([t[n]["rmse_per_depth"][str(d)] for d in DZ], DZ, "o-", c=c, label=f"{n}: {t[n]['overall_rmse']:.3f}")
    ax[1].invert_yaxis(); ax[1].legend(); ax[1].set_xlabel("RMSE (°C)"); ax[1].set_title("target formulation (test months)")
    ds = ab["data_size"]
    ns = sorted(ds, key=int)
    ax[2].plot([int(n) for n in ns], [ds[n]["overall_rmse"] for n in ns], "o-")
    ax[2].set_xscale("log"); ax[2].set_xlabel("training rows"); ax[2].set_ylabel("overall RMSE (°C)"); ax[2].set_title("learning curve")
    _save(fig, "09_ablation.png")

    gi = ab["group_permutation_importance"]
    fig, ax = plt.subplots(1, len(gi), figsize=(16, 5), constrained_layout=True)
    for a, (d, r) in zip(ax, gi.items()):
        s = dict(sorted(r["rmse_increase_when_group_permuted"].items(), key=lambda kv: kv[1]))
        a.barh(list(s), list(s.values()), color="tab:purple")
        a.set_title(f"{d} m: RMSE increase when group is shuffled"); a.set_xlabel("°C")
    _save(fig, "10_group_permutation_importance.png")


def main():
    T = json.loads((RES / "test_metrics.json").read_text())
    cv = json.loads((RES / "cv_selection.json").read_text())
    model_comparison(T, cv)
    best_model_breakdown(T)
    linear_models_insight()
    ablation_figs()
    print("figures ->", OUT)


if __name__ == "__main__":
    main()
