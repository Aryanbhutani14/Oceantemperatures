"""Loading ML tables and building model matrices."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from oceanembed_ml.config import FINAL, load_yaml
from oceanembed_ml.grid import DEPTHS

FCFG = load_yaml("features.yaml")
GROUPS: dict[str, list[str]] = FCFG["groups"]
ALL_FEATURES = [c for g in GROUPS.values() for c in g]
NZ = len(DEPTHS)
A_COLS = [f"a_d{k:02d}" for k in range(NZ)]   # anomaly targets
Y_COLS = [f"y_d{k:02d}" for k in range(NZ)]   # absolute temperature
C_COLS = [f"clim_d{k:02d}" for k in range(NZ)]
META = ["time", "cell_id", "month", "region", "lat", "lon"]


def features_for(groups: list[str] | None = None, drop: list[str] | None = None) -> list[str]:
    gs = list(GROUPS) if groups is None else groups
    gs = [g for g in gs if g not in (drop or [])]
    return [c for g in gs for c in GROUPS[g]]


def load(split: str, n: int | None = None, seed: int = 0, features: list[str] | None = None) -> pd.DataFrame:
    """Load a split; optionally a uniform random subsample of n rows (fixed seed -> reproducible)."""
    cols = list(dict.fromkeys(META + (features or ALL_FEATURES) + A_COLS + Y_COLS + C_COLS))
    df = pq.read_table(FINAL / "features" / f"{split}.parquet", columns=cols).to_pandas()
    if n is not None and n < len(df):
        df = df.sample(n=n, random_state=seed).reset_index(drop=True)
    return df


def matrices(df: pd.DataFrame, features: list[str]):
    X = df[features].to_numpy(dtype="float32")
    A = df[A_COLS].to_numpy(dtype="float32")
    Y = df[Y_COLS].to_numpy(dtype="float32")
    C = df[C_COLS].to_numpy(dtype="float32")
    return X, A, Y, C


def index_hash(df: pd.DataFrame) -> str:
    """Fingerprint of an evaluation subset, so every model is provably scored on the same rows."""
    key = (df["time"].astype("int64").to_numpy() * 100_000 + df["cell_id"].to_numpy()).astype("int64")
    return hashlib.sha256(np.sort(key).tobytes()).hexdigest()[:16]
