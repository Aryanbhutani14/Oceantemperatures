"""Tests for the from-scratch GD regression and the multi-depth model wrappers."""
import numpy as np
from sklearn.linear_model import LinearRegression

from oceanembed_ml.models.metrics import evaluate
from oceanembed_ml.models.scratch import LinearRegressionGD
from oceanembed_ml.models.zoo import DepthwiseModel, NaNAwareKNN, PCARegression


def test_gd_matches_closed_form_ols():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(5000, 4))
    y = X @ np.array([1.5, -2.0, 0.5, 0.0]) + 3.0 + rng.normal(scale=0.1, size=5000)
    gd = LinearRegressionGD(lr=0.1, epochs=50, batch_size=256).fit(X, y)
    ols = LinearRegression().fit(X, y)
    np.testing.assert_allclose(gd.coef_, ols.coef_, atol=0.02)
    assert abs(gd.intercept_ - ols.intercept_) < 0.02
    assert gd.loss_history_[-1] < gd.loss_history_[0]


def _toy():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(3000, 3)).astype("float32")
    A = np.column_stack([X[:, 0] * (k + 1) / 15 for k in range(15)]).astype("float32")
    A[:500, 10:] = np.nan            # shallow cells: deep levels missing
    return X, A


def test_depthwise_handles_missing_deep_levels():
    X, A = _toy()
    P = DepthwiseModel(LinearRegression()).fit(X, A).predict(X)
    assert P.shape == A.shape and np.isfinite(P).all()
    m = np.isfinite(A)
    assert np.abs(P[m] - A[m]).max() < 1e-4


def test_knn_and_pca_regression_shapes():
    X, A = _toy()
    assert NaNAwareKNN(5).fit(X, A).predict(X[:100]).shape == (100, 15)
    assert PCARegression(3).fit(X, A).predict(X[:100]).shape == (100, 15)


def test_metrics_skill_zero_for_climatology():
    Y = np.random.default_rng(2).normal(size=(1000, 15)) + 20
    C = Y + 0.5
    m = evaluate(Y, np.zeros_like(Y), C)
    assert abs(m["per_depth"]["100"]["skill_vs_clim"]) < 1e-9
    assert abs(m["per_depth"]["100"]["bias"] - 0.5) < 1e-9
