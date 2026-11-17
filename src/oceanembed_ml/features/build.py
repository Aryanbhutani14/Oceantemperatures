"""Phase 4 — feature engineering on the grid, then ML-ready Parquet tables.

Why on the grid first: spatial features (gradients, neighbourhood means, curl,
patch embedding) need neighbouring cells, which no longer exist once the cube
is flattened into rows.

Leakage controls (tests/test_features.py):
  * features use surface inputs, static grid info and the EXTERNAL climatology only
  * temporal features are trailing (past-only) 7-day windows
  * the PCA embedding (and its standardisation) is fitted on TRAIN days only
  * buffer days are dropped; train/test tables never share a day
  * NO scaling/imputation here — that happens inside the model pipelines (Phase 5)

Outputs
  data/final/features/train.parquet, test.parquet   (one row per ocean cell-day)
  data/final/features/embedding_pca.npz             (fitted PCA, for inference)
  data/audit/features_summary.json                   (columns, NaN rates, sizes)
"""
from __future__ import annotations

import json
import sys
import time
import warnings

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr
from sklearn.decomposition import PCA

from oceanembed_ml.config import AUDIT, FINAL, PROCESSED, load_yaml
from oceanembed_ml.features import physics as P
from oceanembed_ml.grid import DEPTHS, REGIONS

warnings.filterwarnings("ignore")
OUT = FINAL / "features"
FCFG = load_yaml("features.yaml")
DIRECT = ["sst", "sss", "sla", "uo", "vo", "u10", "v10"]


def grid_features(ds: xr.Dataset) -> dict[str, np.ndarray]:
    lat, lon = ds.lat.values, ds.lon.values
    g = {v: ds[v].values.astype("float32") for v in DIRECT}
    g["wind_speed"] = np.hypot(g["u10"], g["v10"]).astype("float32")
    g["current_speed"] = np.hypot(g["uo"], g["vo"]).astype("float32")
    g["taux"], g["tauy"] = P.wind_stress(g["u10"], g["v10"])
    g["curl_tau"], g["ekman_w"] = P.ekman_pumping(g["taux"], g["tauy"], lat, lon)
    sx, sy = P.gradients(g["sst"], lat, lon)
    g["sst_grad"] = np.hypot(sx, sy)
    g["sla_dx"], g["sla_dy"] = P.gradients(g["sla"], lat, lon)
    g["sla_grad"] = np.hypot(g["sla_dx"], g["sla_dy"])
    g["sla_lap"] = P.laplacian(g["sla"], lat, lon)
    k = FCFG["neighbourhood_size"]
    for v in ("sla", "sst", "sss"):
        g[f"{v}_box{k}"] = P.box_mean(g[v], k)
    w = FCFG["temporal_window_days"]
    g[f"sla_mean{w}"] = P.trailing_mean(g["sla"], w)
    g[f"sst_mean{w}"] = P.trailing_mean(g["sst"], w)
    g[f"ekman_mean{w}"] = P.trailing_mean(g["ekman_w"], w)
    g[f"sla_change{w}"] = P.lagged_change(g["sla"], w)
    g[f"sst_change{w}"] = P.lagged_change(g["sst"], w)
    month = ds.month_of_time.values
    clim0 = ds.thetao_clim.sel(depth=0.0).values[month - 1]
    g["sst_anom"] = (g["sst"] - clim0).astype("float32")
    # mask every derived field to the ocean (land stays NaN)
    ocean = ds.ocean_mask.values.astype(bool)
    for kname in list(g):
        g[kname] = np.where(ocean[None], g[kname], np.nan).astype("float32")
    return g


def patch_embedding(ds: xr.Dataset, g: dict, train_days: np.ndarray):
    """PCA of standardised 3x3 x 7-variable surface patches -> 8 components.

    Standardisation statistics and PCA are fitted on TRAIN days only. Missing
    values inside a patch (coast) are set to the train mean (0 after
    standardisation) for the embedding ONLY; the raw features keep their NaN.
    """
    cfg = FCFG["embedding"]
    vars_, p = cfg["variables"], cfg["patch_size"]
    r = p // 2
    ocean = ds.ocean_mask.values.astype(bool)
    stats = {v: (float(np.nanmean(g[v][train_days][:, ocean])), float(np.nanstd(g[v][train_days][:, ocean]))) for v in vars_}

    def patches(t: int) -> np.ndarray:
        cols = []
        for v in vars_:
            m, s = stats[v]
            z = np.nan_to_num((g[v][t] - m) / s, nan=0.0)
            zp = np.pad(z, r, mode="edge")
            for dy in range(p):
                for dx in range(p):
                    cols.append(zp[dy:dy + z.shape[0], dx:dx + z.shape[1]])
        return np.stack(cols, axis=-1)                       # (lat, lon, 7*9)

    rng = np.random.default_rng(cfg["seed"])
    tr_idx = np.where(train_days)[0]
    yy, xx = np.where(ocean)
    per_day = max(1, cfg["fit_sample"] // tr_idx.size)
    sample = []
    for t in tr_idx:
        P_ = patches(t)
        c = rng.choice(yy.size, per_day, replace=False)
        sample.append(P_[yy[c], xx[c]])
    X = np.concatenate(sample)
    pca = PCA(n_components=cfg["n_components"], random_state=cfg["seed"]).fit(X)
    emb = np.full((ds.sizes["time"], cfg["n_components"]) + ocean.shape, np.nan, dtype="float32")
    for t in range(ds.sizes["time"]):
        Z = pca.transform(patches(t)[yy, xx]).astype("float32")
        emb[t][:, yy, xx] = Z.T
    for k in range(cfg["n_components"]):
        g[f"emb_{k}"] = emb[:, k]
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(OUT / "embedding_pca.npz", components=pca.components_, mean=pca.mean_,
             explained_variance_ratio=pca.explained_variance_ratio_,
             std_stats=np.array([stats[v] for v in vars_]), variables=np.array(vars_), patch_size=p)
    return pca.explained_variance_ratio_


def region_of(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    out = np.full(lat.shape, "other", dtype=object)
    for name, b in REGIONS.items():
        m = (lat >= b["lat"][0]) & (lat <= b["lat"][1]) & (lon >= b["lon"][0]) & (lon <= b["lon"][1])
        out[m] = name
    return out.astype(str)


def to_table(ds, g, split_name: str) -> pd.DataFrame:
    split = ds.split.values
    tidx = np.where(split == split_name)[0]
    ocean = ds.ocean_mask.values.astype(bool)
    yy, xx = np.where(ocean)
    nt, nc = tidx.size, yy.size
    T = np.repeat(tidx, nc)
    Y = np.tile(yy, nt)
    X = np.tile(xx, nt)
    times = pd.DatetimeIndex(ds.time.values)
    lat, lon = ds.lat.values[Y].astype("float32"), ds.lon.values[X].astype("float32")
    doy = times.dayofyear.values[T]
    cols = {
        "time": times.values[T], "cell_id": (Y * ds.sizes["lon"] + X).astype("int32"),
        "lat_idx": Y.astype("int16"), "lon_idx": X.astype("int16"),
        "month": times.month.values[T].astype("int8"), "split": np.full(T.size, split_name),
        "region": region_of(lat, lon), "lat": lat, "lon": lon,
        "sin_doy": np.sin(2 * np.pi * doy / 365.25).astype("float32"),
        "cos_doy": np.cos(2 * np.pi * doy / 365.25).astype("float32"),
        "bottom_depth": ds.deepest_valid_depth.values[Y, X].astype("float32"),
    }
    for k, arr in g.items():
        cols[k] = arr[T, Y, X]
    month = times.month.values
    th = ds.thetao.values
    cl = ds.thetao_clim.values
    for k, d in enumerate(DEPTHS):
        y = th[T, k, Y, X]
        c = cl[month[T] - 1, k, Y, X]
        cols[f"clim_d{k:02d}"] = c.astype("float32")
        cols[f"y_d{k:02d}"] = y.astype("float32")
        cols[f"a_d{k:02d}"] = (y - c).astype("float32")
    df = pd.DataFrame(cols)
    df["region"] = df["region"].astype("category")
    df["split"] = df["split"].astype("category")
    return df


def main() -> int:
    t0 = time.time()
    ds = xr.open_dataset(PROCESSED / "cube.nc").load()
    train_days = ds.split.values == "train"
    print("[features] grid features ...", flush=True)
    g = grid_features(ds)
    print(f"[features] PCA patch embedding (fit on {int(train_days.sum())} train days) ...", flush=True)
    evr = patch_embedding(ds, g, train_days)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {"embedding_explained_variance_ratio": np.round(evr, 4).tolist(),
               "embedding_cumulative": float(evr.sum()), "tables": {}}
    feature_cols = [c for grp in FCFG["groups"].values() for c in grp]
    for sp in ("train", "test"):
        df = to_table(ds, g, sp)
        missing = [c for c in feature_cols if c not in df]
        assert not missing, missing
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), OUT / f"{sp}.parquet", compression="zstd")
        summary["tables"][sp] = {
            "rows": int(len(df)), "days": int(df["time"].nunique()), "columns": int(df.shape[1]),
            "months": sorted(int(m) for m in df["month"].unique()),
            "date_range": [str(df["time"].min())[:10], str(df["time"].max())[:10]],
            "rows_by_region": df["region"].value_counts().astype(int).to_dict(),
            "feature_nan_frac": {c: round(float(df[c].isna().mean()), 5) for c in feature_cols},
            "target_valid_rows_per_depth": {str(int(d)): int(df[f"y_d{k:02d}"].notna().sum()) for k, d in enumerate(DEPTHS)},
            "size_MB": round((OUT / f"{sp}.parquet").stat().st_size / 1e6, 1),
        }
        print(f"[features] {sp}: {len(df):,} rows x {df.shape[1]} cols -> {summary['tables'][sp]['size_MB']} MB", flush=True)
        del df
    tr, te = summary["tables"]["train"], summary["tables"]["test"]
    assert set(tr["months"]).isdisjoint(te["months"]), "train/test share a month!"
    summary["feature_groups"] = FCFG["groups"]
    summary["n_features"] = len(feature_cols)
    summary["seconds"] = round(time.time() - t0, 1)
    (AUDIT / "features_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"[features] {len(feature_cols)} features; embedding explains {evr.sum():.1%} of patch variance; {summary['seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
