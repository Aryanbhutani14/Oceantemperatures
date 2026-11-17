"""Whole-project realism audit.

A. Data integrity     row counts, duplicate keys, split integrity, physical sanity,
                      spot-checks of processed values against the RAW source files,
                      search for suspiciously perfect features (leakage symptom)
B. Stricter tests     the main test holds out whole months but trains on the months
                      around them, so the model has seen the same year, place and
                      ocean state. Three harder setups (gradient boosting + climatology
                      feature, the final model's settings):
                        B1 temporal  train Jan–Jun  -> test Aug, Nov (1–4 months ahead)
                        B2 spatial   hold out 25% of 5°x5° ocean blocks entirely
                        B3 both      train Jan–Jun outside the held blocks -> test Aug, Nov inside them
                      plus the TCHP>=60 classifier under B2/B3.
C. Uncertainty        block bootstrap over test DAYS (days resampled with replacement)
                      -> 95% confidence intervals for RMSE, skill and classification accuracy.

Outputs: results/validation/audit.json
"""
from __future__ import annotations

import json
import sys
import time
import warnings

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from oceanembed_ml.classification import task
from oceanembed_ml.config import FINAL, INTERIM, PROCESSED, RAW, ROOT
from oceanembed_ml.grid import DEPTHS, LAT, LON, vertical_interp
from oceanembed_ml.models import data as D
from oceanembed_ml.models.metrics import evaluate
from oceanembed_ml.models.zoo import DepthwiseWithClim

warnings.filterwarnings("ignore")
OUT = ROOT / "results" / "validation"
RNG = np.random.default_rng(2026)


# ----------------------------------------------------------------------------- A
def data_integrity() -> dict:
    out = {}
    tr = D.load("train", features=D.ALL_FEATURES)
    te = D.load("test", features=D.ALL_FEATURES)
    ocean = int(xr.open_dataset(INTERIM / "masks.nc").ocean_mask.sum())
    for name, df in (("train", tr), ("test", te)):
        out[f"{name}_rows"] = len(df)
        out[f"{name}_days"] = int(df.time.nunique())
        out[f"{name}_rows_equal_days_x_ocean_cells"] = bool(len(df) == df.time.nunique() * ocean)
        out[f"{name}_duplicate_keys"] = int(df.duplicated(["time", "cell_id"]).sum())
        out[f"{name}_months"] = sorted(int(m) for m in df.month.unique())
    tdays, edays = np.sort(tr.time.unique()), np.sort(te.time.unique())
    out["min_gap_days_train_test"] = int(min(np.abs((edays[:, None] - tdays[None, :]).astype("timedelta64[D]").astype(int)).min(), 999))
    Y = te[D.Y_COLS].to_numpy()
    out["target_range_C"] = [float(np.nanmin(Y)), float(np.nanmax(Y))]
    mean_prof = np.nanmean(np.concatenate([tr[D.Y_COLS].to_numpy(), Y]), axis=0)
    out["mean_profile_monotonic_cooling"] = bool(np.all(np.diff(mean_prof) <= 0.05))
    deep = Y[:, 10:]                                   # 200 m and below
    inv = np.nanmax(np.diff(deep, axis=1), axis=1)     # positive diff = warmer deeper (inversion)
    out["pct_profiles_with_inversion_gt_0p5C_below_200m"] = float(100 * np.mean(inv[np.isfinite(inv)] > 0.5))

    # spot-check processed target vs RAW GLORYS (vertical interpolation redone by hand)
    raw = xr.open_dataset(RAW / "glorys" / "2021-05.nc")
    cube = xr.open_dataset(PROCESSED / "cube.nc")
    oc = xr.open_dataset(INTERIM / "masks.nc").ocean_mask.values.astype(bool)
    yy, xx = np.where(oc)
    diffs = []
    for _ in range(25):
        k = RNG.integers(yy.size); day = int(RNG.integers(0, 31))
        la, lo = float(LAT[yy[k]]), float(LON[xx[k]])
        prof = raw.thetao_glor.isel(time=day).sel(latitude=la, longitude=lo, method="nearest").values
        mine = vertical_interp(prof[:, None], raw.depth.values.astype(float), DEPTHS, axis=0)[:, 0]
        theirs = cube.thetao.sel(time=raw.time.values[day], lat=la, lon=lo).values
        m = np.isfinite(mine) & np.isfinite(theirs)
        diffs.append(float(np.max(np.abs(mine[m] - theirs[m]))) if m.any() else 0.0)
    out["spotcheck_target_vs_raw_glorys_max_abs_diff_C"] = max(diffs)

    # spot-check SST: processed value vs mean of raw OSTIA pixels whose centres fall in the cell
    rs = xr.open_dataset(RAW / "sst" / "2021-05.nc")
    sdiff = []
    for _ in range(25):
        k = RNG.integers(yy.size); day = int(RNG.integers(0, 31))
        la, lo = float(LAT[yy[k]]), float(LON[xx[k]])
        box = rs.analysed_sst.isel(time=day).sel(latitude=slice(la - 0.125, la + 0.125), longitude=slice(lo - 0.125, lo + 0.125)).values - 273.15
        mine = cube.sst.sel(time=rs.time.values[day], lat=la, lon=lo).values
        if np.isfinite(box).mean() > 0.9 and np.isfinite(mine):
            sdiff.append(float(abs(np.nanmean(box) - mine)))
    out["spotcheck_sst_vs_raw_ostia_mean_abs_diff_C"] = float(np.mean(sdiff)) if sdiff else None
    out["spotcheck_sst_n"] = len(sdiff)

    # leakage symptom: any single feature that predicts the ANOMALY almost perfectly?
    s = tr.sample(200_000, random_state=0)
    worst = {}
    for k_, d in ((0, "0"), (7, "100"), (12, "500")):
        a = s[D.A_COLS[k_]]
        c = s[D.ALL_FEATURES].corrwith(a).abs().sort_values(ascending=False)
        worst[d] = {"feature": c.index[0], "abs_r": float(c.iloc[0])}
    out["strongest_single_feature_vs_anomaly"] = worst
    out["any_feature_abs_r_gt_0p95"] = any(v["abs_r"] > 0.95 for v in worst.values())
    return out


# ----------------------------------------------------------------------------- B
def blocks(df: pd.DataFrame) -> np.ndarray:
    return ((df.lat.to_numpy() - 5) // 5).astype(int) * 100 + ((df.lon.to_numpy() - 45) // 5).astype(int)


def gb(p):
    return HistGradientBoostingRegressor(max_iter=400, learning_rate=p["lr"], max_leaf_nodes=p["leaves"], l2_regularization=1.0, random_state=42)


def fit_eval(train_df, test_df, p, n=400_000, use_geo=True):
    base = [c for c in D.ALL_FEATURES if use_geo or c not in ("lat", "lon")]
    feats = base + D.C_COLS
    tr = train_df.sample(n=min(n, len(train_df)), random_state=0)
    m = DepthwiseWithClim(gb(p), n_base=len(base)).fit(tr[feats].to_numpy("float32"), tr[D.A_COLS].to_numpy("float32"))
    P = m.predict(test_df[feats].to_numpy("float32"))
    _, _, Y, C = D.matrices(test_df, base)
    return evaluate(Y, P, C), P


def summarise(met):
    return {"rmse": met["overall"]["rmse"], "mae": met["overall"]["mae"], "bias": met["overall"]["bias"],
            "mean_skill": met["mean_skill_over_depths"], "rmse_100m": met["per_depth"]["100"]["rmse"],
            "r2_100m": met["per_depth"]["100"]["r2"], "rmse_clim": met["overall"]["rmse_clim"]}


def stricter_tests() -> dict:
    p = json.loads((ROOT / "results" / "phase5" / "cv_selection.json").read_text())["gradient_boosting"]["best_params"]
    tr = D.load("train"); te = D.load("test")
    tr["block"], te["block"] = blocks(tr), blocks(te)
    ub = np.unique(tr["block"])
    held = set(np.random.default_rng(7).choice(ub, size=int(round(0.25 * ub.size)), replace=False).tolist())
    early = tr.month.isin([1, 3, 4, 6])
    late_test = te.month.isin([8, 11])
    in_held_tr, in_held_te = tr.block.isin(held), te.block.isin(held)
    out = {"held_out_blocks": len(held), "total_blocks": int(ub.size), "params": p, "setups": {}}
    setups = {
        "A_main_month_holdout": (tr, te),
        "B1_temporal_train_JanJun_test_AugNov": (tr[early], te[late_test]),
        "B2_spatial_unseen_regions": (tr[~in_held_tr], te[in_held_te]),
        "B3_temporal_and_spatial": (tr[early & ~in_held_tr], te[late_test & in_held_te]),
    }
    for name, (a, b) in setups.items():
        t0 = time.time()
        b_ = b.sample(n=min(150_000, len(b)), random_state=3)
        met, _ = fit_eval(a, b_, p)
        out["setups"][name] = {"train_rows": int(len(a)), "test_rows_scored": int(len(b_)), **summarise(met), "seconds": round(time.time() - t0)}
        print(f"  {name:40s} RMSE={met['overall']['rmse']:.3f} skill={met['mean_skill_over_depths']:.3f} clim={met['overall']['rmse_clim']:.3f}", flush=True)
    # does location memorisation explain B2? same spatial test without lat/lon
    b_ = te[in_held_te].sample(n=150_000, random_state=3)
    met, _ = fit_eval(tr[~in_held_tr], b_, p, use_geo=False)
    out["setups"]["B2_spatial_without_lat_lon"] = {**summarise(met)}
    print(f"  {'B2 without lat/lon':40s} RMSE={met['overall']['rmse']:.3f} skill={met['mean_skill_over_depths']:.3f}", flush=True)

    # classifier (TCHP >= 60) under the same stricter splits
    ctr, cte = task.load("train"), task.load("test")
    ctr["block"], cte["block"] = blocks(ctr), blocks(cte)
    F = task.FEATURES
    out["classification"] = {}
    for name, (a, b) in {"main": (ctr, cte), "B2_spatial": (ctr[~ctr.block.isin(held)], cte[cte.block.isin(held)]),
                         "B3_temporal_and_spatial": (ctr[ctr.month.isin([1, 3, 4, 6]) & ~ctr.block.isin(held)], cte[cte.month.isin([8, 11]) & cte.block.isin(held)])}.items():
        a_ = a.sample(n=min(300_000, len(a)), random_state=0); b_ = b.sample(n=min(100_000, len(b)), random_state=3)
        res = {}
        for mname, mdl in (("logistic_l1", make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(penalty="l1", C=0.01, solver="liblinear", max_iter=500))),
                           ("gradient_boosting", HistGradientBoostingClassifier(max_iter=400, learning_rate=0.1, max_leaf_nodes=31, random_state=42))):
            mdl.fit(a_[F].to_numpy("float32"), a_.label.to_numpy())
            s = mdl.predict_proba(b_[F].to_numpy("float32"))[:, 1]
            y = b_.label.to_numpy()
            res[mname] = {"accuracy": accuracy_score(y, s >= 0.5), "f1": f1_score(y, s >= 0.5), "roc_auc": roc_auc_score(y, s)}
        rule = (b_.clim_tchp.fillna(0).to_numpy() >= task.THRESHOLD)
        res["climatology_rule"] = {"accuracy": accuracy_score(b_.label, rule), "f1": f1_score(b_.label, rule)}
        res["positive_rate"] = float(b_.label.mean())
        out["classification"][name] = res
        print(f"  clf {name:28s} logistic acc={res['logistic_l1']['accuracy']:.3f} GB acc={res['gradient_boosting']['accuracy']:.3f} rule acc={res['climatology_rule']['accuracy']:.3f}", flush=True)
    return out


# ----------------------------------------------------------------------------- C
def bootstrap(n_boot: int = 1000) -> dict:
    pr = xr.open_dataset(FINAL / "predictions" / "test_predictions.nc")
    P, G, C = pr.pred.values, pr.glorys.values, pr.clim.values
    m = np.isfinite(P) & np.isfinite(G) & np.isfinite(C)
    se = np.where(m, (P - G) ** 2, 0).reshape(P.shape[0], -1).sum(1)
    sc = np.where(m, (C - G) ** 2, 0).reshape(P.shape[0], -1).sum(1)
    n = m.reshape(P.shape[0], -1).sum(1)
    rng = np.random.default_rng(0)
    rm, sk = [], []
    for _ in range(n_boot):
        d = rng.integers(0, len(n), len(n))                 # resample whole DAYS (block bootstrap)
        rm.append(np.sqrt(se[d].sum() / n[d].sum())); sk.append(1 - se[d].sum() / sc[d].sum())
    out = {"method": f"block bootstrap over {len(n)} test days, {n_boot} resamples",
           "rmse": {"estimate": float(np.sqrt(se.sum() / n.sum())), "ci95": [float(np.percentile(rm, 2.5)), float(np.percentile(rm, 97.5))]},
           "pooled_skill": {"estimate": float(1 - se.sum() / sc.sum()), "ci95": [float(np.percentile(sk, 2.5)), float(np.percentile(sk, 97.5))]}}
    # classification accuracy CI (logistic L1, selected model) on its 100k test rows, grouped by day
    import joblib
    te = task.load("test", n=100_000, seed=7)
    mdl = joblib.load(ROOT / "models" / "phase7" / "logistic_l1.joblib")["model"]
    correct = (mdl.predict_proba(te[task.FEATURES].to_numpy("float32"))[:, 1] >= 0.5) == te.label.to_numpy()
    g = pd.DataFrame({"day": te.time.to_numpy(), "c": correct}).groupby("day").c.agg(["sum", "count"])
    acc = []
    for _ in range(n_boot):
        d = rng.integers(0, len(g), len(g))
        acc.append(g["sum"].to_numpy()[d].sum() / g["count"].to_numpy()[d].sum())
    out["classification_accuracy_logistic_l1"] = {"estimate": float(correct.mean()), "ci95": [float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5))]}
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    print("[audit] A. data integrity ...", flush=True)
    res["A_data_integrity"] = data_integrity()
    print(json.dumps(res["A_data_integrity"], indent=1, default=str), flush=True)
    print("[audit] C. bootstrap ...", flush=True)
    res["C_bootstrap"] = bootstrap()
    print(json.dumps(res["C_bootstrap"], indent=1), flush=True)
    print("[audit] B. stricter generalisation tests ...", flush=True)
    res["B_stricter_tests"] = stricter_tests()
    (OUT / "audit.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print("[audit] wrote results/validation/audit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
