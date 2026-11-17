"""Classification task: is the ocean 'favourable for cyclone intensification'?

Label (per ocean cell-day):  y = 1 if TCHP >= 60 kJ cm-2 else 0
  TCHP is computed from the GLORYS temperature profile (truth) with the same,
  unit-tested function used in Phase 6 (science.indicators.tchp). Values of
  ~50-60 kJ cm-2 are commonly used as the level above which tropical cyclones
  tend to intensify (Leipper & Volgenau 1972; Shay et al. 2000; Mainelli et al. 2008).
  Rows where TCHP is undefined (shallow shelf cells) are dropped.

Inputs: the same 40 surface-derived features as the regression, plus
  clim_tchp = TCHP of the EXTERNAL climatology profile (known in advance,
  no leakage; analogous to the climatology feature chosen by CV in Phase 5).
Split: the same months as everywhere else (train 8 months / test Feb, May, Aug, Nov).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from oceanembed_ml.models import data as D
from oceanembed_ml.science.indicators import tchp

THRESHOLD = 60.0
FEATURES = D.ALL_FEATURES + ["clim_tchp"]


def load(split: str, n: int | None = None, seed: int = 0) -> pd.DataFrame:
    df = D.load(split)
    df["tchp_true"] = tchp(df[D.Y_COLS].to_numpy("float64")).astype("float32")
    df["clim_tchp"] = tchp(df[D.C_COLS].to_numpy("float64")).astype("float32")
    df = df[np.isfinite(df["tchp_true"])].reset_index(drop=True)
    df["label"] = (df["tchp_true"] >= THRESHOLD).astype("int8")
    if n is not None and n < len(df):
        df = df.sample(n=n, random_state=seed).reset_index(drop=True)
    return df
