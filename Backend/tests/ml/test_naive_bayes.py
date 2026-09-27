import numpy as np
import pytest
from sklearn.naive_bayes import CategoricalNB

from app.ml import features
from app.ml.naive_bayes import FRAUD, LEGITIMATE, NaiveBayes
from app.ml.training import NB_ALPHA

CLUES = {"within_7_days": ["Yes", "No"], "amount_over_100k": ["Yes", "No"]}
# docs/Naive_Bayes_Paper_Section.docx, Figure 4: 6 illustrative historical claims
PAPER_ROWS = [("Yes", "No", FRAUD), ("No", "No", LEGITIMATE), ("Yes", "Yes", FRAUD),
              ("No", "Yes", LEGITIMATE), ("Yes", "No", LEGITIMATE), ("No", "No", LEGITIMATE)]


def _paper_model(alpha):
    rows = [{"within_7_days": a, "amount_over_100k": b} for a, b, _ in PAPER_ROWS]
    return NaiveBayes(alpha).fit(rows, [c for *_, c in PAPER_ROWS], CLUES)


def test_paper_worked_example_without_smoothing():
    m = _paper_model(alpha=0)
    assert m.priors[FRAUD] == pytest.approx(1 / 3)
    assert m.priors[LEGITIMATE] == pytest.approx(2 / 3)
    assert m.likelihoods["within_7_days"]["Yes"][FRAUD] == pytest.approx(1.0)
    assert m.likelihoods["amount_over_100k"]["Yes"][FRAUD] == pytest.approx(0.5)
    assert m.likelihoods["within_7_days"]["Yes"][LEGITIMATE] == pytest.approx(0.25)
    assert m.likelihoods["amount_over_100k"]["Yes"][LEGITIMATE] == pytest.approx(0.25)
    new_claim = {"within_7_days": "Yes", "amount_over_100k": "Yes"}
    scores = m.class_scores(new_claim)
    assert round(scores[FRAUD], 3) == 0.167
    assert round(scores[LEGITIMATE], 3) == 0.042
    winner, confidence = m.predict(new_claim)
    assert winner == FRAUD and round(confidence, 2) == 0.80
    assert m.classify(new_claim) == (FRAUD, pytest.approx(0.8))


def test_laplace_smoothing_by_hand():
    m = _paper_model(alpha=1)
    # (count + 1) / (class size + 1 x 2 values): Fraud has 2 claims, both "Yes" within 7 days
    assert m.likelihoods["within_7_days"]["Yes"][FRAUD] == pytest.approx(3 / 4)
    assert m.likelihoods["within_7_days"]["No"][FRAUD] == pytest.approx(1 / 4)
    assert m.likelihoods["within_7_days"]["Yes"][LEGITIMATE] == pytest.approx(2 / 6)


def test_value_never_seen_in_training_gives_no_evidence():
    clues = {"a": ["x", "y", "never"], "b": ["p", "q"]}
    rows = [{"a": "x", "b": "p"}, {"a": "y", "b": "q"}, {"a": "x", "b": "q"}, {"a": "y", "b": "p"}]
    m = NaiveBayes(1).fit(rows, [FRAUD, LEGITIMATE, LEGITIMATE, LEGITIMATE], clues)
    assert not m.seen_in_training("a", "never")
    # Scores with the unseen value equal the scores computed from clue b alone
    only_b = NaiveBayes(1).fit([{"b": r["b"]} for r in rows], [FRAUD, LEGITIMATE, LEGITIMATE, LEGITIMATE], {"b": ["p", "q"]})
    assert m.class_scores({"a": "never", "b": "p"}) == pytest.approx(only_b.class_scores({"b": "p"}))
    with pytest.raises(ValueError):
        m.class_scores({"a": "not-a-value", "b": "p"})


def test_cutoff():
    m = _paper_model(alpha=0)
    claim = {"within_7_days": "Yes", "amount_over_100k": "No"}   # 0.1667 vs 0.125 -> P(Fraud) = 0.571
    p = m.fraud_probability(claim)
    assert p == pytest.approx(0.1667 / (0.1667 + 0.125), abs=1e-3)
    assert m.classify(claim, 0.5)[0] == m.predict(claim)[0] == FRAUD  # default cutoff = the documents' rule
    assert m.classify(claim, p - 0.01)[0] == FRAUD
    assert m.classify(claim, p + 0.01)[0] == LEGITIMATE


def test_matches_sklearn_categorical_nb_on_real_claims(db):
    frame = features.claim_clue_frame(db)
    frame = frame[frame["fraud_label"].notna()].reset_index(drop=True)
    clues = list(features.NB_CLUE_VALUES)
    y = frame["fraud_label"].astype(int).to_numpy()
    rows = frame[clues].to_dict("records")
    ours = NaiveBayes(NB_ALPHA).fit(rows, [FRAUD if v else LEGITIMATE for v in y], features.NB_CLUE_VALUES)

    codes = np.array([[features.NB_CLUE_VALUES[c].index(r[c]) for c in clues] for r in rows])
    sk = CategoricalNB(alpha=NB_ALPHA, min_categories=[len(features.NB_CLUE_VALUES[c]) for c in clues]).fit(codes, y)
    # Every training row only has values seen in training, so the unseen-value rule never applies
    ours_p = np.array([ours.fraud_probability(r) for r in rows])
    assert np.abs(ours_p - sk.predict_proba(codes)[:, 1]).max() < 1e-9
    assert ((ours_p > 0.5).astype(int) == sk.predict(codes)).all()


def test_save_and_load_round_trip():
    m = _paper_model(alpha=1)
    again = NaiveBayes.from_dict(m.to_dict())
    claim = {"within_7_days": "No", "amount_over_100k": "Yes"}
    assert again.class_scores(claim) == m.class_scores(claim)
