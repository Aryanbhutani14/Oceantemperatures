"""Model zoo: every model exposes  fit(X, A) / predict(X) -> (n, 15) anomaly.

A = anomaly targets for the 15 depths (NaN below the seafloor). Three ways of
handling the 15 outputs are used (see docs/phase5_models.md):

  * DepthwiseModel   one sklearn pipeline per depth, trained on rows where that
                     depth exists (works for every sklearn regressor)
  * NaNAwareKNN      neighbours found once, then a NaN-aware mean of the
                     neighbours' 15-depth anomaly vectors (naturally multi-output)
  * PCARegression    PCA of the standardised anomaly PROFILES (vertical modes),
                     regress the first K scores, reconstruct all 15 depths

Pre-processing (median imputation, standardisation) is part of each pipeline,
so inside cross-validation it is fitted on the training folds only.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import clone
from sklearn.decomposition import PCA
from sklearn.ensemble import BaggingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor

from oceanembed_ml.models.scratch import LinearRegressionGD

SEED = 42


class Climatology:
    """Baseline: anomaly = 0, i.e. prediction = external climatology."""

    def fit(self, X, A):
        self.nz = A.shape[1]
        return self

    def predict(self, X):
        return np.zeros((len(X), self.nz), dtype="float32")


class DepthwiseModel:
    def __init__(self, estimator, depths: list[int] | None = None):
        self.estimator, self.depths = estimator, depths

    def fit(self, X, A):
        self.nz = A.shape[1]
        ks = range(self.nz) if self.depths is None else self.depths
        self.models_ = {}
        for k in ks:
            m = np.isfinite(A[:, k])
            self.models_[k] = clone(self.estimator).fit(X[m], A[m, k])
        return self

    def predict(self, X):
        out = np.full((len(X), self.nz), np.nan, dtype="float32")
        for k, mdl in self.models_.items():
            out[:, k] = mdl.predict(X)
        return out


class DepthwiseWithClim(DepthwiseModel):
    """Per-depth model whose inputs are the base features PLUS the climatology at that depth.

    X layout: [base features ..., clim_d00 ... clim_d14] (last 15 columns). For
    depth k the model sees base features + clim_dk only (decision D-024).
    """

    def __init__(self, estimator, n_base: int, depths: list[int] | None = None):
        super().__init__(estimator, depths)
        self.n_base = n_base

    def _x(self, X, k):
        return np.column_stack([X[:, : self.n_base], X[:, self.n_base + k]])

    def fit(self, X, A):
        self.nz = A.shape[1]
        ks = range(self.nz) if self.depths is None else self.depths
        self.models_ = {}
        for k in ks:
            m = np.isfinite(A[:, k])
            self.models_[k] = clone(self.estimator).fit(self._x(X[m], k), A[m, k])
        return self

    def predict(self, X):
        out = np.full((len(X), self.nz), np.nan, dtype="float32")
        for k, mdl in self.models_.items():
            out[:, k] = mdl.predict(self._x(X, k))
        return out


class NaNAwareKNN:
    def __init__(self, n_neighbors: int = 10, chunk: int = 20000):
        self.n_neighbors, self.chunk = n_neighbors, chunk

    def fit(self, X, A):
        self.prep_ = make_pipeline(SimpleImputer(strategy="median"), StandardScaler()).fit(X)
        self.nn_ = NearestNeighbors(n_neighbors=self.n_neighbors, algorithm="brute", n_jobs=-1).fit(self.prep_.transform(X))
        self.A_ = A.astype("float32")
        return self

    def predict(self, X):
        Z = self.prep_.transform(X)
        out = np.empty((len(X), self.A_.shape[1]), dtype="float32")
        for s in range(0, len(X), self.chunk):
            idx = self.nn_.kneighbors(Z[s:s + self.chunk], return_distance=False)
            with np.errstate(all="ignore"):
                out[s:s + self.chunk] = np.nanmean(self.A_[idx], axis=1)
        return out


class PCARegression:
    """Predict K principal-component scores of the vertical anomaly profile, then reconstruct.

    PCA is fitted on rows with all 15 depths valid (deep water). For shallow
    (shelf) cells the reconstructed values at non-existent depths are simply
    not evaluated.
    """

    def __init__(self, n_components: int = 6, estimator=None):
        self.n_components, self.estimator = n_components, estimator

    def fit(self, X, A):
        full = np.isfinite(A).all(1)
        Af = A[full].astype("float64")
        self.mu_, self.sd_ = Af.mean(0), Af.std(0)
        self.pca_ = PCA(n_components=self.n_components, random_state=SEED).fit((Af - self.mu_) / self.sd_)
        S = self.pca_.transform((Af - self.mu_) / self.sd_)
        est = self.estimator or HistGradientBoostingRegressor(max_iter=300, learning_rate=0.1, random_state=SEED)
        self.models_ = [clone(est).fit(X[full], S[:, j]) for j in range(self.n_components)]
        return self

    def predict(self, X):
        S = np.column_stack([m.predict(X) for m in self.models_])
        return (self.pca_.inverse_transform(S) * self.sd_ + self.mu_).astype("float32")


class Average:
    """Simple averaging ensemble (voting regressor) of already-defined zoo models."""

    def __init__(self, members: list):
        self.members = members

    def fit(self, X, A):
        for m in self.members:
            m.fit(X, A)
        return self

    def predict(self, X):
        return np.nanmean(np.stack([m.predict(X) for m in self.members]), axis=0)


def _lin(est):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), est)


def _tree(est):
    return make_pipeline(SimpleImputer(strategy="median"), est)


# ---------------------------------------------------------------------------- registry
# name -> (builder(params) -> model, param grid for CV, training-sample size, syllabus topic)
REGISTRY = {
    "climatology": (lambda p: Climatology(), [{}], 400_000, "baseline"),
    "sst_only_linear": (lambda p: DepthwiseModel(_lin(LinearRegression())), [{}], 400_000, "baseline (SST anomaly only)"),
    "linear_regression": (lambda p: DepthwiseModel(_lin(LinearRegression())), [{}], 400_000, "Linear Regression (OLS)"),
    "linear_gd_scratch": (lambda p: DepthwiseModel(_lin(LinearRegressionGD(lr=p["lr"], epochs=20))),
                          [{"lr": 0.01}, {"lr": 0.05}], 400_000, "Gradient descent (from scratch)"),
    "ridge": (lambda p: DepthwiseModel(_lin(Ridge(alpha=p["alpha"]))),
              [{"alpha": a} for a in (0.1, 10.0, 1000.0, 10000.0)], 400_000, "Ridge (L2)"),
    "lasso": (lambda p: DepthwiseModel(_lin(Lasso(alpha=p["alpha"], max_iter=3000))),
              [{"alpha": a} for a in (0.0005, 0.005, 0.05)], 400_000, "Lasso (L1)"),
    "knn": (lambda p: NaNAwareKNN(n_neighbors=p["k"]), [{"k": k} for k in (5, 15, 40)], 150_000, "KNN"),
    "svr_rbf": (lambda p: DepthwiseModel(_lin(SVR(kernel="rbf", C=p["C"], epsilon=0.05, cache_size=2000))),
                [{"C": 1.0}, {"C": 10.0}], 10_000, "SVM (SVR, RBF kernel)"),
    "decision_tree": (lambda p: DepthwiseModel(_tree(DecisionTreeRegressor(max_depth=p["max_depth"], min_samples_leaf=20, random_state=SEED))),
                      [{"max_depth": d} for d in (8, 14, 20)], 400_000, "Decision Tree"),
    "bagging_trees": (lambda p: DepthwiseModel(_tree(BaggingRegressor(DecisionTreeRegressor(min_samples_leaf=5, max_depth=p["max_depth"]),
                                                                      n_estimators=30, max_samples=0.5, n_jobs=-1, random_state=SEED))),
                      [{"max_depth": 20}], 400_000, "Bagging"),
    "random_forest": (lambda p: DepthwiseModel(_tree(RandomForestRegressor(n_estimators=60, max_features=p["max_features"], max_depth=20,
                                                                           min_samples_leaf=5, max_samples=0.5, n_jobs=-1, random_state=SEED))),
                      [{"max_features": f} for f in (0.33, 0.66)], 400_000, "Random Forest (decision forest)"),
    "gradient_boosting": (lambda p: DepthwiseModel(HistGradientBoostingRegressor(max_iter=400, learning_rate=p["lr"], max_leaf_nodes=p["leaves"],
                                                                                 l2_regularization=1.0, random_state=SEED)),
                          [{"lr": 0.05, "leaves": 63}, {"lr": 0.1, "leaves": 63}, {"lr": 0.1, "leaves": 127}], 400_000, "Boosting (gradient boosting)"),
    "pca_regression": (lambda p: PCARegression(n_components=p["K"]), [{"K": 4}, {"K": 6}, {"K": 8}], 400_000, "PCA + Boosting (vertical modes)"),
}
