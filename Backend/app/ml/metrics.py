"""Train/test split, cross-validation folds and evaluation scores — written by us
(numpy only); tests/ml/ cross-checks them against scikit-learn."""
import numpy as np


def stratified_split(y, test_fraction=0.25, seed=42):
    """Hold back `test_fraction` of each class (fixed seed) so the test data keeps the
    same Fraud/Legitimate or loss/no-loss mix as the whole dataset."""
    y = np.asarray(y)
    rng = np.random.RandomState(seed)
    test = np.zeros(len(y), dtype=bool)
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        test[idx[: int(round(len(idx) * test_fraction))]] = True
    return np.where(~test)[0], np.where(test)[0]


def stratified_kfold(y, k=5, seed=42):
    """k folds; each class is dealt round-robin into the folds after a fixed-seed shuffle,
    so every fold has (almost) the same class mix. Returns [(train_idx, test_idx), ...]."""
    y = np.asarray(y)
    rng = np.random.RandomState(seed)
    fold_of = np.empty(len(y), dtype=int)
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        fold_of[idx] = np.arange(len(idx)) % k
    return [(np.where(fold_of != f)[0], np.where(fold_of == f)[0]) for f in range(k)]


def scores(y_true, y_pred):
    """Accuracy, precision, recall, F1 and the confusion matrix (1 = loss / Fraud)."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": (tp + tn) / n if n else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "rows": n,
    }


def roc_auc(y_true, probability):
    """ROC AUC: the chance that a randomly chosen positive (loss / Fraud) row gets a higher
    probability than a randomly chosen negative row (ties count half). 0.5 = no better than
    chance, 1.0 = perfect ranking. Independent of any cutoff."""
    y_true = np.asarray(y_true).astype(int)
    probability = np.asarray(probability, dtype=float)
    pos = probability[y_true == 1]
    neg = probability[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    higher = (pos[:, None] > neg[None, :]).sum()
    ties = (pos[:, None] == neg[None, :]).sum()
    return float((higher + 0.5 * ties) / (len(pos) * len(neg)))


def mean_sd(fold_scores, key):
    values = [s[key] for s in fold_scores]
    return {
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        "per_fold": [float(v) for v in values],
    }
