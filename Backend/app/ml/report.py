"""Writes one Markdown report per training run to model_reports/ (gitignored) — tables
that paste straight into Chapter 4. Wording follows the Algorithm Walkthrough steps."""
from pathlib import Path

TITLES = {
    "motor_lr": "Motor Car — Logistic Regression (Predictive Risk)",
    "fire_lr": "Fire & Property — Logistic Regression (Predictive Risk)",
    "fraud_nb": "Fraud Detection — Naive Bayes Classifier (Motor Car and Fire & Property)",
}
SYNTHETIC_NOTE = (
    "The data in this system is a synthetic learning dataset (seed 20260926). Its generator "
    "created losses and fraud from the same kinds of risk factors and red flags used here, "
    "so these results show that the algorithm learns known patterns correctly; they are not "
    "evidence of accuracy on real Maagap claims."
)
AUC_NOTE = (
    "ROC AUC = the chance that a randomly chosen positive row gets a higher probability than a "
    "randomly chosen negative row (0.5 = no better than chance, 1.0 = perfect); it does not "
    "depend on any cutoff."
)


def pct(x):
    return "—" if x is None else f"{x * 100:.1f}%"


def auc(x):
    return "—" if x is None else f"{x:.3f}"


def _scores_table(title, s, with_auc=True):
    c = s["confusion"]
    head = "| Accuracy | Precision | Recall | F1 |" + (" ROC AUC |" if with_auc else "") + " Rows |"
    sep = "|---|---|---|---|" + ("---|" if with_auc else "") + "---|"
    vals = (f"| {pct(s['accuracy'])} | {pct(s['precision'])} | {pct(s['recall'])} | {pct(s['f1'])} |"
            + (f" {auc(s.get('roc_auc'))} |" if with_auc else "") + f" {s['rows']} |")
    return [
        f"### {title}", "", head, sep, vals, "",
        "| | Predicted positive | Predicted negative |", "|---|---|---|",
        f"| **Actual positive** | {c['tp']} (true positive) | {c['fn']} (false negative) |",
        f"| **Actual negative** | {c['fp']} (false positive) | {c['tn']} (true negative) |", "",
    ]


def _cv_table(cv):
    lines = ["## 5-fold stratified cross-validation (all rows)", "",
             "Every row is used for testing exactly once; each fold keeps the same class mix. "
             "Mean ± standard deviation over the 5 folds:", "",
             "| Measure | Mean ± SD | Fold 1 | Fold 2 | Fold 3 | Fold 4 | Fold 5 |", "|---|---|---|---|---|---|---|"]
    for key, label in (("accuracy", "Accuracy"), ("precision", "Precision"), ("recall", "Recall"), ("roc_auc", "ROC AUC")):
        v = cv[key]
        fmt = auc if key == "roc_auc" else pct
        folds = " | ".join(fmt(x) for x in v["per_fold"])
        lines.append(f"| {label} | {fmt(v['mean'])} ± {fmt(v['sd'])} | {folds} |")
    return lines + ["", AUC_NOTE, ""]


def _lr_body(row, result):
    m, t, p = result["metrics"], result["thresholds"], result["parameters"]["model"]
    lines = [
        "## Steps (Algorithm Walkthrough, section 1.2)", "",
        "**Step 1: Input collection** — for each quotation:", "",
        "| Input | Source |", "|---|---|",
        *[f"| {k} | {v} |" for k, v in result["sources"].items()], "",
        "**Step 2: Feature encoding** — categories become one 0/1 column per category; numbers are "
        "scaled to mean 0 and standard deviation 1 using the training rows only; yes/no inputs stay 0/1. "
        f"This gives {len(result['parameters']['feature_names'])} inputs x1 … xn.", "",
        "**Step 3: Weighted linear combination** — z = (w1 × x1) + (w2 × x2) + ... + (wn × xn) + b", "",
        "**Step 4: Sigmoid transformation** — P(claim) = 1 / (1 + e^(−z))", "",
        f"**Step 5: Model training** — gradient descent on the log-loss, learning rate {p['learning_rate']}, "
        f"stopped after {p['epochs_run']} epochs when the loss changed by less than {p['tolerance']:g} "
        f"(final loss {p['final_loss']:.4f}). A small L2 penalty (λ = {p['l2']}) keeps the weights stable.", "",
        "**Step 6: Output / prediction** — each quotation gets a claim probability (Claim Possibility) "
        "and a risk level (Risk Assessment):", "",
        "| Risk level | Probability |", "|---|---|",
        f"| Low | below {pct(t['medium_from'])} (the training loss rate) |",
        f"| Medium | {pct(t['medium_from'])} to below {pct(t['high_from'])} |",
        f"| High | {pct(t['high_from'])} or more (twice the training loss rate) |", "",
        "## Results on held-back test data (25%, never seen during training)", "",
        f"Decision rule: {m['decision_rule']}. For comparison, always predicting \"no loss\" would be "
        f"{pct(m['baseline_accuracy'])} accurate while catching none of the losses.", "",
        *_scores_table("Test data", m["test"]),
        *_scores_table("Same test data with a 0.5 cutoff (walkthrough diagram's decision threshold)",
                       m["test_at_0_5"], with_auc=False),
        "### Actual loss rate by predicted risk level (test data)", "",
        "| Risk level | Quotations | With a counted loss | Loss rate |", "|---|---|---|---|",
        *[f"| {lvl} | {v['rows']} | {v['losses']} | {pct(v['loss_rate'])} |" for lvl, v in m["loss_rate_by_level"].items()], "",
        *_cv_table(m["cross_validation"]),
        "## Most important clues (largest weights)", "",
        "Positive weight = raises the claim probability. Odds ratio = how the odds of a loss change "
        "when the input is 1 instead of 0 (or 1 standard deviation higher for numbers).", "",
        "| Input | Weight | Odds ratio |", "|---|---|---|",
        *[f"| {f['feature']} | {f['weight']:+.3f} | {f['odds_ratio']:.2f} |" for f in m["top_features"]], "",
    ]
    if "control_check" in m:
        lines += ["## Control check — vehicle color", "",
                  "Color should not affect losses, so its weights show how much weight pure noise receives "
                  "with this amount of data. Weights of a similar size elsewhere should not be read as real "
                  "effects on their own.", "",
                  "| Color | Weight |", "|---|---|",
                  *[f"| {c['feature'].replace('color = ', '')} | {c['weight']:+.3f} |" for c in m["control_check"]], ""]
    return lines


def _nb_body(row, result):
    m, p, t = result["metrics"], result["parameters"]["model"], result["thresholds"]
    lines = [
        "## Training Phase", "",
        "**Step 1. Gather historical claims** — Paid Claims (not CNC Issuance) that already have a "
        "Claim Investigation Result; Suspected Fraud and Confirmed Fraud are labeled Fraud, Legitimate "
        "is labeled Legitimate.", "",
        "**Step 2. Encode clues** — each attribute becomes a discrete clue:", "",
        "| Clue | Source | Values |", "|---|---|---|",
        *[f"| {k} | {result['sources'][k]} | {', '.join(v)} |" for k, v in p["clue_values"].items()], "",
        "**Step 3. Compute prior probability and likelihoods** — from the training claims:", "",
        f"P(Fraud) = {p['priors']['Fraud']:.3f}, P(Legitimate) = {p['priors']['Legitimate']:.3f} "
        f"({p['class_counts']['Fraud']} Fraud, {p['class_counts']['Legitimate']} Legitimate). Each clue's "
        f"likelihood is computed separately within each class, with Laplace smoothing (alpha = {p['alpha']}): "
        "P(value | class) = (count + alpha) ÷ (claims in class + alpha × number of values). A clue value that "
        "never appeared in any training claim gives no evidence either way and is left out of the product.", "",
        "## Prediction Phase", "",
        "**Step 1. New claim input** — the claim's clues are encoded the same way.", "",
        "**Step 2. Combine via Bayes Theorem** — P(Fraud | evidence) ∝ P(Fraud) × P(clue1|Fraud) × "
        "P(clue2|Fraud) × ... (and the same for Legitimate).", "",
        "**Step 3. Classification decision** — the class with the higher combined score is returned; "
        "its share of the two scores is the normalized confidence P(Fraud). The stored fraud cutoff is "
        f"{t['fraud_cutoff']} (a claim is Fraud when P(Fraud) > {t['fraud_cutoff']}; 0.5 is the same as "
        "\"the higher score wins\").", "",
        "## Results on held-back test data (25%, never seen during training)", "",
        f"Decision rule: {m['decision_rule']}. Always answering \"Legitimate\" would be "
        f"{pct(m['baseline_accuracy'])} accurate while catching no fraud.", "",
        *_scores_table("Test data", m["test"]),
        *_cv_table(m["cross_validation"]),
        "## Choosing the fraud cutoff (5-fold cross-validation)", "",
        "Same 5 folds, different cutoffs: a lower cutoff flags more claims — more fraud is caught "
        "(recall) but more flagged claims turn out legitimate (precision).", "",
        "| Flag as Fraud when P(Fraud) > | Precision (mean ± SD) | Recall (mean ± SD) | Accuracy (mean ± SD) | Claims flagged |",
        "|---|---|---|---|---|",
        *[f"| {r['cutoff']} | {pct(r['precision']['mean'])} ± {pct(r['precision']['sd'])} | "
          f"{pct(r['recall']['mean'])} ± {pct(r['recall']['sd'])} | "
          f"{pct(r['accuracy']['mean'])} ± {pct(r['accuracy']['sd'])} | {pct(r['flagged_share'])} |"
          for r in m["cutoff_table"]], "",
        "## Most important clues (strongest fraud signals)", "",
        "Ratio = P(value | Fraud) ÷ P(value | Legitimate): how many times more common the clue is among "
        "fraud. Only values seen in at least 5 training claims are listed.", "",
        "| Clue | Value | Fraud claims | Legitimate claims | P(value / Fraud) | P(value / Legitimate) | Ratio |",
        "|---|---|---|---|---|---|---|",
        *[f"| {r['clue']} | {r['value']} | {r['fraud_count']} | {r['legitimate_count']} | {r['p_fraud']:.3f} | "
          f"{r['p_legitimate']:.3f} | {r['ratio']:.2f} |" for r in m["top_features"]], "",
    ]
    return lines


def write_report(row, result, report_dir):
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{row.data_as_of.isoformat()}_{row.model_name}_v{row.version}.md"
    lines = [
        f"# {TITLES[row.model_name]} — version {row.version}", "",
        f"Trained {row.trained_at:%B %d, %Y %H:%M} · data as of {row.data_as_of:%B %d, %Y}", "",
        "## Data", "",
        f"{result['total_rows']} rows, {result['positive_rows']} positive "
        f"({pct(result['positive_rows'] / result['total_rows'])}). Split 75% training ({result['train_rows']}) / "
        f"25% test ({result['test_rows']}), stratified (same positive share in both), fixed seed 42.", "",
    ]
    if row.model_name == "fraud_nb":
        lines += _nb_body(row, result)
    else:
        lines += [
            "Rows: issued policies whose coverage has ended (period_to before the data date). Positive = "
            "the policy has at least one Paid Claim whose Final Status is Closed Claim, Waiting for LOA, "
            "Waiting for Billing or Waiting for Claim Check (a counted loss). Every input comes from the "
            "quotation, its vehicle or its survey — information that existed on the quotation date.", "",
        ]
        lines += _lr_body(row, result)
    lines += ["## Note on the data", "", SYNTHETIC_NOTE, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
