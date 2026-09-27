import { CNC_INVESTIGATION_LABEL } from "../lib/claims";

// Claim Investigation Result = the real human label (never a prediction).
const INVESTIGATION_STYLE = {
  "Legitimate": "text-gray-600",
  "Suspected Fraud": "text-amber-600 font-semibold",
  "Confirmed Fraud": "text-red-500 font-semibold",
  [CNC_INVESTIGATION_LABEL]: "text-gray-400",
};

export function InvestigationResultCell({ value }) {
  if (!value) return <span>—</span>;
  return <span className={INVESTIGATION_STYLE[value] || ""}>{value}</span>;
}

// Fraud Warning = the Naive Bayes prediction (lib/claims.js fraud_warning / fraud_flag),
// never the human label. "—" when there is none: CNC rows, claims already investigated,
// or no model yet.
export function FraudWarningCell({ value, flagged }) {
  if (!value) return <span className="text-gray-400">—</span>;
  return (
    <span className={flagged ? "text-red-500 font-semibold" : "text-gray-600"}
      title="Naive Bayes P(Fraud) — a prediction, not an investigation result">
      {value}
    </span>
  );
}
