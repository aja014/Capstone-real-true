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

// Fraud Warning: placeholder until the Naive Bayes fraud model exists -- the same
// honest gray "Pending" as Proposal's Risk Assessment. null (CNC rows) -> "—".
export function FraudWarningCell({ value }) {
  if (!value) return <span>—</span>;
  return <span className="text-gray-400">{value}</span>;
}
