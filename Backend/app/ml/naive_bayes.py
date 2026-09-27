"""Naive Bayes Classifier (Fraud Detection), written from scratch, following section 2.2
of docs/Algorithm_Walkthrough_LogisticRegression_NaiveBayes.docx and the Training /
Prediction Phase steps of docs/Naive_Bayes_Paper_Section.docx:

  Step 1  Input collection        -> app/ml/features.py (claim, policy, policyholder)
  Step 2  Feature encoding        -> app/ml/features.py (every attribute becomes a "clue")
  Step 3  Prior probability       P(Fraud), P(Legitimate)
  Step 4  Likelihood per clue     P(clue_i | Fraud), P(clue_i | Legitimate), each clue
                                  computed independently of every other (the "naive" part)
  Step 5  Combine via Bayes' Theorem
          P(Fraud | evidence) ∝ P(Fraud) × P(clue1|Fraud) × P(clue2|Fraud) × ...
  Step 6  Classification decision the class with the higher combined score wins; its share
          of the two scores is the normalized confidence (e.g. 0.167 vs 0.042 -> 80% Fraud)

Laplace smoothing (alpha = 1) is added to Step 4 so a clue value never seen in one class
gets a small likelihood instead of 0 (a single 0 would wipe out every other clue):
    P(value | class) = (count of value in class + alpha) / (claims in class + alpha × K)
where K is the number of possible values of that clue. alpha = 0 gives the plain counts
used in the paper's worked example.

A clue value that never appeared in ANY training claim (e.g. "Not yet submitted" when every
investigated claim already had its documents) carries no evidence either way, so it is left
out of the product. Without this, smoothing alone would make such a value look ~6x more
"fraud-like", simply because the Fraud class is the smaller one.

Adjustable cutoff: classify() calls a claim Fraud when its normalized P(Fraud) is above
`fraud_cutoff`. The default 0.5 is exactly Step 6 (the higher score wins); a lower cutoff
flags more claims (higher recall, more false alarms).
"""

FRAUD = "Fraud"
LEGITIMATE = "Legitimate"
CLASSES = (FRAUD, LEGITIMATE)
DEFAULT_FRAUD_CUTOFF = 0.5


class NaiveBayes:
    def __init__(self, alpha=1.0):
        self.alpha = alpha
        self.clue_values = {}   # clue -> list of every possible value
        self.class_counts = {}
        self.counts = {}        # clue -> value -> class -> training count
        self.priors = {}        # class -> P(class)
        self.likelihoods = {}   # clue -> value -> class -> P(value | class)

    def fit(self, rows, labels, clue_values):
        """rows: list of {clue: value} dicts; labels: FRAUD / LEGITIMATE per row."""
        self.clue_values = {c: list(v) for c, v in clue_values.items()}
        n = len(rows)
        self.class_counts = {c: sum(1 for y in labels if y == c) for c in CLASSES}
        # Step 3: prior probability from historical proportions
        self.priors = {c: self.class_counts[c] / n for c in CLASSES}
        # Step 4: likelihood per clue, separately within each class
        self.likelihoods = {}
        self.counts = {}
        for clue, values in self.clue_values.items():
            k = len(values)
            self.likelihoods[clue] = {}
            self.counts[clue] = {}
            for v in values:
                self.likelihoods[clue][v] = {}
                self.counts[clue][v] = {}
                for c in CLASSES:
                    count = sum(1 for row, y in zip(rows, labels) if y == c and row[clue] == v)
                    self.counts[clue][v][c] = count
                    self.likelihoods[clue][v][c] = (count + self.alpha) / (self.class_counts[c] + self.alpha * k)
        return self

    def seen_in_training(self, clue, value):
        return sum(self.counts[clue][value].values()) > 0

    # Step 5: combine via Bayes' Theorem
    def class_scores(self, row):
        scores = {}
        for c in CLASSES:
            score = self.priors[c]
            for clue in self.clue_values:
                value = row[clue]
                if value not in self.likelihoods[clue]:
                    raise ValueError(f"{clue}: unknown value {value!r}")
                if not self.seen_in_training(clue, value):
                    continue  # no evidence either way (see module docstring)
                score *= self.likelihoods[clue][value][c]
            scores[c] = score
        return scores

    def fraud_probability(self, row):
        """Normalized confidence of Fraud: score(Fraud) / (score(Fraud) + score(Legitimate))."""
        scores = self.class_scores(row)
        total = scores[FRAUD] + scores[LEGITIMATE]
        return scores[FRAUD] / total if total > 0 else 0.5

    # Step 6: classification decision + normalized confidence
    def predict(self, row):
        scores = self.class_scores(row)
        total = scores[FRAUD] + scores[LEGITIMATE]
        winner = FRAUD if scores[FRAUD] > scores[LEGITIMATE] else LEGITIMATE
        confidence = scores[winner] / total if total > 0 else 0.5
        return winner, confidence

    def classify(self, row, fraud_cutoff=DEFAULT_FRAUD_CUTOFF):
        """Same as predict() at the default cutoff; Fraud when P(Fraud) > fraud_cutoff."""
        p = self.fraud_probability(row)
        return (FRAUD if p > fraud_cutoff else LEGITIMATE), p

    def to_dict(self):
        return {
            "alpha": self.alpha,
            "clue_values": self.clue_values,
            "class_counts": self.class_counts,
            "counts": self.counts,
            "priors": self.priors,
            "likelihoods": self.likelihoods,
        }

    @classmethod
    def from_dict(cls, d):
        m = cls(d["alpha"])
        m.clue_values = d["clue_values"]
        m.class_counts = d["class_counts"]
        m.counts = d["counts"]
        m.priors = d["priors"]
        m.likelihoods = d["likelihoods"]
        return m
