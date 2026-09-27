import axios from "axios";
import { fetchClaimPredictions, formatPercent } from "./ml";

const API_BASE_URL = "http://127.0.0.1:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const CNC_CLAIM_TYPE = "CNC Issuance";
export const CNC_INVESTIGATION_LABEL = "Not applicable (CNC)";
export const NOT_YET_INVESTIGATED = "Not yet investigated";

// Shared by Policy Holder Information's Claims tab and the Claims Module page,
// so the claim → policy → quotation → case → policyholder join exists in one
// place (same pattern as lib/quotations.js). Each row keeps every raw API field
// and gains:
//   line                   "Motor Car" | "Fire & Property"
//   policy_no              the linked policy's number
//   client_name            the RESOLVED policyholder -- deliberately independent
//                          of `assured` (the literal text on the claims sheet),
//                          same Client Name vs literal-name rule as other tabs
//   investigation_display  the human label as shown; CNC Issuance rows are never
//                          investigated, so they show "Not applicable (CNC)"
//   fraud_warning          the Naive Bayes prediction as text, e.g. "Suspicious · 45%"
//                          or "Not suspicious · 8%" (the % is P(Fraud)); null ("—") when
//                          there is none -- CNC rows, claims already investigated (the
//                          human result is shown instead), or no model yet. Kept as text
//                          so the Claims tab's all-fields search matches it.
//   fraud_flag             true = flagged Suspicious (P(Fraud) above the model's stored
//                          cutoff), false = not, null = no prediction
export async function fetchAllClaims() {
  const headers = authHeaders();
  const get = (path) => axios.get(`${API_BASE_URL}${path}`, { headers });
  const [[motorC, fireC, motorP, fireP, motorQ, fireQ, casesRes, phRes], predictions] = await Promise.all([
    Promise.all([
      get("/motor/claims"), get("/fire-property/claims"),
      get("/motor/policies"), get("/fire-property/policies"),
      get("/motor/quotations"), get("/fire-property/quotations"),
      get("/insurance-cases"), get("/policyholders"),
    ]),
    fetchClaimPredictions(),
  ]);

  const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
  const nameByPolicyholder = new Map(
    phRes.data.map((p) => [p.id, [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ")])
  );
  const caseByMotorQuotation = new Map(motorQ.data.map((q) => [q.id, q.insurance_case_id]));
  const caseByFireQuotation = new Map(fireQ.data.map((q) => [q.id, q.insurance_case_id]));
  const motorPolicyById = new Map(motorP.data.map((p) => [p.id, p]));
  const firePolicyById = new Map(fireP.data.map((p) => [p.id, p]));

  const enrich = (claim, line, policy, caseByQuotation) => {
    const caseId = policy ? caseByQuotation.get(policy.quotation_id) : undefined;
    const isCnc = claim.claim_type === CNC_CLAIM_TYPE;
    // Only uninvestigated Paid Claims ever have a prediction (the backend never stores
    // one for CNC or investigated claims), so a lookup miss simply means "—".
    const prediction = isCnc ? undefined : predictions.get(`${line}-${claim.id}`);
    const flagged = prediction ? prediction.label === "Fraud" : null;
    return {
      ...claim,
      line,
      policy_no: policy?.policy_no ?? null,
      client_name: nameByPolicyholder.get(policyholderByCase.get(caseId)) || null,
      investigation_display: isCnc ? CNC_INVESTIGATION_LABEL : claim.claim_investigation_result ?? null,
      fraud_warning: prediction
        ? `${flagged ? "Suspicious" : "Not suspicious"} · ${formatPercent(prediction.fraud_probability)}`
        : null,
      fraud_flag: flagged,
    };
  };

  const motor = motorC.data.map((c) =>
    enrich(c, "Motor Car", motorPolicyById.get(c.motor_policy_id), caseByMotorQuotation));
  const fire = fireC.data.map((c) =>
    enrich(c, "Fire & Property", firePolicyById.get(c.fire_property_policy_id), caseByFireQuotation));
  return { motor, fire };
}

// Investigation Result filter value for one row -- blank non-CNC rows are
// "Not yet investigated"; CNC rows only ever match "All".
export function investigationFilterValue(row) {
  if (row.claim_type === CNC_CLAIM_TYPE) return CNC_INVESTIGATION_LABEL;
  return row.claim_investigation_result || NOT_YET_INVESTIGATED;
}
