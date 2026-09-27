"""Logistic Regression, written from scratch with numpy, following section 1.2 of
docs/Algorithm_Walkthrough_LogisticRegression_NaiveBayes.docx:

  Step 1  Input collection        -> app/ml/features.py (quotation, survey, vehicle, GIS)
  Step 2  Feature encoding        -> app/ml/features.py (FeatureEncoder)
  Step 3  Weighted linear combination   z = (w1 × x1) + (w2 × x2) + ... + (wn × xn) + b
  Step 4  Sigmoid transformation        P(claim) = 1 / (1 + e^(−z))
  Step 5  Model training                gradient descent on the log-loss
  Step 6  Output / prediction           a probability between 0 and 1

scikit-learn is NOT used here — tests/ml/ uses it only to cross-check our results.
"""
import numpy as np


class LogisticRegression:
    def __init__(self, learning_rate=0.5, max_epochs=50000, tolerance=1e-12, l2=0.01):
        self.learning_rate = learning_rate
        self.max_epochs = max_epochs
        # Training stops once the loss changes by less than this between two epochs
        # ("repeats until the weights converge", Step 5).
        self.tolerance = tolerance
        # Small L2 penalty (λ/2 × Σw²) added to the loss. Not in the walkthrough: it keeps
        # weights stable when one-hot categories overlap (e.g. the surveyor's overall
        # rating vs the facts it summarizes). The bias is not penalized.
        self.l2 = l2
        self.weights = None
        self.bias = 0.0
        self.epochs_run = 0
        self.final_loss = None

    # Step 3: weighted linear combination
    def linear_score(self, X):
        return X @ self.weights + self.bias

    # Step 4: sigmoid transformation
    @staticmethod
    def sigmoid(z):
        # Clipping only avoids an overflow warning in exp() for extreme z; the result
        # is already 0 or 1 to machine precision there.
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

    # Step 6: output / prediction
    def predict_proba(self, X):
        return self.sigmoid(self.linear_score(X))

    def loss(self, X, y):
        """Log-loss (how far predictions are from actual outcomes) + the L2 penalty."""
        p = np.clip(self.predict_proba(X), 1e-15, 1 - 1e-15)
        log_loss = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        return log_loss + self.l2 / 2 * float(self.weights @ self.weights)

    # Step 5: model training (gradient descent)
    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        n, k = X.shape
        self.weights = np.zeros(k)
        self.bias = 0.0
        previous = self.loss(X, y)
        for epoch in range(1, self.max_epochs + 1):
            error = self.predict_proba(X) - y          # predictions compared against actual outcomes
            grad_w = X.T @ error / n + self.l2 * self.weights
            grad_b = float(error.mean())
            self.weights -= self.learning_rate * grad_w  # each weight nudged against the error
            self.bias -= self.learning_rate * grad_b
            current = self.loss(X, y)
            self.epochs_run = epoch
            if abs(previous - current) < self.tolerance:
                break
            previous = current
        self.final_loss = current
        return self

    def to_dict(self):
        return {
            "weights": [float(w) for w in self.weights],
            "bias": float(self.bias),
            "learning_rate": self.learning_rate,
            "max_epochs": self.max_epochs,
            "tolerance": self.tolerance,
            "l2": self.l2,
            "epochs_run": self.epochs_run,
            "final_loss": float(self.final_loss) if self.final_loss is not None else None,
        }

    @classmethod
    def from_dict(cls, d):
        m = cls(d["learning_rate"], d["max_epochs"], d["tolerance"], d["l2"])
        m.weights = np.array(d["weights"], dtype=float)
        m.bias = d["bias"]
        m.epochs_run = d.get("epochs_run", 0)
        m.final_loss = d.get("final_loss")
        return m
