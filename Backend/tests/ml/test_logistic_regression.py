import datetime as dt

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression as SkLogisticRegression

from app.ml import features
from app.ml.logistic_regression import LogisticRegression
from app.ml.training import LR_L2_CHOICES, lr_settings

SETTINGS = lr_settings(0.01)  # the λ the v2 models were trained with

TODAY = dt.date(2026, 9, 27)


def test_walkthrough_worked_example():
    """Section 1.4 diagram: w1 = 1, w2 = 0.5, bias = -4 (illustrative weights)."""
    m = LogisticRegression()
    m.weights = np.array([1.0, 0.5])
    m.bias = -4.0
    points = {"A": ([1, 2], -2.0, 0.119), "B": ([4, 1], 0.5, 0.622), "C": ([2, 3], -0.5, 0.378),
              "D": ([5, 4], 3.0, 0.953), "query": ([3, 5], 1.5, 0.818)}
    for name, (x, z, p) in points.items():
        X = np.array([x], dtype=float)
        assert m.linear_score(X)[0] == pytest.approx(z), name
        assert round(float(m.predict_proba(X)[0]), 3) == p, name
    assert m.sigmoid(np.array([0.0]))[0] == 0.5


def test_gradient_descent_reduces_loss_and_converges():
    rng = np.random.RandomState(0)
    X = rng.normal(size=(300, 3))
    y = (X @ np.array([1.5, -2.0, 0.0]) + rng.normal(size=300) > 0).astype(float)
    m = LogisticRegression(**SETTINGS)
    m.weights = np.zeros(3)
    start = m.loss(X, y)
    m.fit(X, y)
    assert m.final_loss < start
    assert m.epochs_run < SETTINGS["max_epochs"]  # stopped by the tolerance, not the cap
    grad = X.T @ (m.predict_proba(X) - y) / len(y) + m.l2 * m.weights
    assert np.abs(grad).max() < 1e-4
    assert m.weights[0] > 0 > m.weights[1]


def _sklearn_equivalent(X, y, l2):
    # Our loss: mean log-loss + l2/2 * |w|^2. sklearn: C * sum log-loss + 1/2 * |w|^2.
    # Same minimum when C = 1 / (l2 * n); the intercept is unpenalized in both.
    return SkLogisticRegression(C=1.0 / (l2 * len(y)), tol=1e-12, max_iter=100000).fit(X, y)


def test_matches_sklearn_on_random_data():
    rng = np.random.RandomState(1)
    X = rng.normal(size=(400, 5))
    y = (X @ np.array([1, -1, 0.5, 0, 2]) + rng.normal(size=400) > 0.3).astype(float)
    ours = LogisticRegression(**SETTINGS).fit(X, y)
    sk = _sklearn_equivalent(X, y, SETTINGS["l2"])
    assert np.allclose(ours.weights, sk.coef_[0], atol=1e-3)
    assert ours.bias == pytest.approx(sk.intercept_[0], abs=1e-3)
    assert np.allclose(ours.predict_proba(X), sk.predict_proba(X)[:, 1], atol=1e-4)


@pytest.mark.parametrize("line", ["motor", "fire"])
def test_matches_sklearn_on_real_training_data(db, line):
    frame_fn = features.motor_quotation_frame if line == "motor" else features.fire_quotation_frame
    spec = features.MOTOR_SPEC if line == "motor" else features.FIRE_SPEC
    rows = features.ended_policy_rows(frame_fn(db), TODAY)
    X = features.FeatureEncoder(spec).fit(rows).transform(rows)
    y = rows["counted_loss"].to_numpy().astype(float)
    ours = LogisticRegression(**SETTINGS).fit(X, y)
    sk = _sklearn_equivalent(X, y, SETTINGS["l2"])
    assert np.abs(ours.weights - sk.coef_[0]).max() < 1e-3
    assert np.abs(ours.predict_proba(X) - sk.predict_proba(X)[:, 1]).max() < 1e-4


def test_save_and_load_round_trip():
    rng = np.random.RandomState(2)
    X = rng.normal(size=(100, 2))
    y = (X[:, 0] > 0).astype(float)
    m = LogisticRegression(**SETTINGS).fit(X, y)
    again = LogisticRegression.from_dict(m.to_dict())
    assert np.array_equal(m.predict_proba(X), again.predict_proba(X))


@pytest.mark.parametrize("l2", LR_L2_CHOICES)
def test_every_l2_choice_converges_and_matches_sklearn(l2):
    """Every λ the cross-validation may pick trains to the same minimum as sklearn —
    including λ = 10, which diverged at the old fixed learning rate of 0.5."""
    rng = np.random.RandomState(3)
    X = rng.normal(size=(300, 4))
    y = (X @ np.array([1, -1, 0.5, 0]) + rng.normal(size=300) > 0).astype(float)
    ours = LogisticRegression(**lr_settings(l2)).fit(X, y)
    assert np.isfinite(ours.weights).all() and ours.epochs_run < ours.max_epochs
    sk = _sklearn_equivalent(X, y, l2)
    assert np.allclose(ours.weights, sk.coef_[0], atol=1e-3)
    assert np.allclose(ours.predict_proba(X), sk.predict_proba(X)[:, 1], atol=1e-4)
