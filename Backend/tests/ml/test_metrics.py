import numpy as np
import pytest
from sklearn import metrics as sk

from app.ml.metrics import mean_sd, roc_auc, scores, stratified_kfold, stratified_split

Y = np.array([1] * 57 + [0] * 564)  # the Fire mix: 57 losses in 621 policies


def test_split_keeps_class_share_and_is_repeatable():
    train, test = stratified_split(Y, 0.25, 42)
    assert len(set(train) & set(test)) == 0 and len(train) + len(test) == len(Y)
    assert Y[test].sum() == round(57 * 0.25) and (Y[test] == 0).sum() == round(564 * 0.25)
    again = stratified_split(Y, 0.25, 42)
    assert np.array_equal(train, again[0]) and np.array_equal(test, again[1])
    assert not np.array_equal(test, stratified_split(Y, 0.25, 7)[1])


def test_kfold_covers_every_row_once_and_is_stratified():
    folds = stratified_kfold(Y, 5, 42)
    seen = np.concatenate([te for _, te in folds])
    assert sorted(seen) == list(range(len(Y)))
    for train, test in folds:
        assert len(set(train) & set(test)) == 0
        assert Y[test].sum() in (11, 12)           # 57 losses dealt over 5 folds
    assert all(np.array_equal(a[1], b[1]) for a, b in zip(folds, stratified_kfold(Y, 5, 42)))


def test_scores_match_sklearn():
    rng = np.random.RandomState(3)
    y = rng.randint(0, 2, 200)
    pred = rng.randint(0, 2, 200)
    s = scores(y, pred)
    assert s["accuracy"] == pytest.approx(sk.accuracy_score(y, pred))
    assert s["precision"] == pytest.approx(sk.precision_score(y, pred))
    assert s["recall"] == pytest.approx(sk.recall_score(y, pred))
    assert s["f1"] == pytest.approx(sk.f1_score(y, pred))
    tn, fp, fn, tp = sk.confusion_matrix(y, pred).ravel()
    assert s["confusion"] == {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def test_scores_with_no_predicted_positives():
    s = scores([1, 0, 0], [0, 0, 0])
    assert s["precision"] == 0.0 and s["recall"] == 0.0 and s["f1"] == 0.0


def test_roc_auc_matches_sklearn_including_ties():
    rng = np.random.RandomState(4)
    y = rng.randint(0, 2, 300)
    p = np.round(rng.rand(300) * 0.6 + y * 0.2, 2)  # rounded -> many ties
    assert roc_auc(y, p) == pytest.approx(sk.roc_auc_score(y, p))
    assert roc_auc([0, 0], [0.1, 0.2]) is None


def test_mean_sd_uses_sample_sd():
    r = mean_sd([{"x": 0.5}, {"x": 0.7}], "x")
    assert r["mean"] == pytest.approx(0.6) and r["sd"] == pytest.approx(np.std([0.5, 0.7], ddof=1))
