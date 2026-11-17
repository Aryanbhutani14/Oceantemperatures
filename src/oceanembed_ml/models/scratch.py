"""Linear regression trained with mini-batch gradient descent — implemented from scratch (NumPy only).

Cost:      J(w, b) = (1 / 2m) * sum_i (x_i . w + b - y_i)^2        (+ optional L2: (lambda / 2m) * ||w||^2)
Gradients: dJ/dw = (1/m) X^T (Xw + b - y) + (lambda/m) w ;  dJ/db = (1/m) sum (Xw + b - y)
Update:    w <- w - lr * dJ/dw ;  b <- b - lr * dJ/db

Features must be standardised (done by the surrounding pipeline) for GD to
converge with a single learning rate. Loss history is kept for the
convergence plot used in the report.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin


class LinearRegressionGD(BaseEstimator, RegressorMixin):
    def __init__(self, lr: float = 0.05, epochs: int = 30, batch_size: int = 4096, l2: float = 0.0, seed: int = 0):
        self.lr, self.epochs, self.batch_size, self.l2, self.seed = lr, epochs, batch_size, l2, seed

    def fit(self, X, y):
        X = np.asarray(X, dtype="float64")
        y = np.asarray(y, dtype="float64")
        n, d = X.shape
        rng = np.random.default_rng(self.seed)
        self.coef_ = np.zeros(d)
        self.intercept_ = float(y.mean())
        self.loss_history_ = []
        for _ in range(self.epochs):
            order = rng.permutation(n)
            for s in range(0, n, self.batch_size):
                idx = order[s:s + self.batch_size]
                xb, yb = X[idx], y[idx]
                err = xb @ self.coef_ + self.intercept_ - yb
                m = len(idx)
                grad_w = xb.T @ err / m + self.l2 * self.coef_ / m
                grad_b = err.mean()
                self.coef_ -= self.lr * grad_w
                self.intercept_ -= self.lr * grad_b
            full_err = X @ self.coef_ + self.intercept_ - y
            self.loss_history_.append(float(0.5 * np.mean(full_err**2)))
        return self

    def predict(self, X):
        return np.asarray(X, dtype="float64") @ self.coef_ + self.intercept_
