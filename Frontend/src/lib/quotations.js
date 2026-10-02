import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Shared by Policy Holder Information's Quotation tab and the Quotations/
// Proposal page's table, so the case→policyholder join and the
// quotation→policy "converted" lookup exist in exactly one place. Fire rows
// additionally borrow their GIS fields from the Survey sharing the same
// insurance_case_id -- FirePropertyQuotation has its own location_of_risk
// but (unlike Motor Quotation) was never given its own latitude/longitude/
// flood_risk_flag/flood_risk_category columns, since a Survey for the same
// property/case already carries that data. Motor rows already have their
// own GIS fields directly on the quotation record.
export async function fetchAllQuotations() {
  const headers = authHeaders();
  const [fpQRes, motorQRes, fpPRes, motorPRes, casesRes, phRes, surveyRes] = await Promise.all([
    axios.get(`${API_BASE_URL}/fire-property/quotations`, { headers }),
    axios.get(`${API_BASE_URL}/motor/quotations`, { headers }),
    axios.get(`${API_BASE_URL}/fire-property/policies`, { headers }),
    axios.get(`${API_BASE_URL}/motor/policies`, { headers }),
    axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
    axios.get(`${API_BASE_URL}/policyholders`, { headers }),
    axios.get(`${API_BASE_URL}/fire-property/surveys`, { headers }),
  ]);

  // Same case → policyholder join Policy/Vehicle/Survey tabs already use.
  // Client Name here is the RESOLVED policyholder, deliberately independent
  // of insured_name (the raw literal field) — same relationship as
  // Policy's Client Name vs Insured Name & Address.
  const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
  const nameByPolicyholder = new Map(
    phRes.data.map((p) => [p.id, [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ")])
  );
  const resolveClientName = (caseId) => nameByPolicyholder.get(policyholderByCase.get(caseId)) || null;

  // null (not "—") when absent — formatOrDash renders it, same as every
  // other empty field, instead of a special "no policy yet" string.
  const fpPolicyByQuotation = new Map(fpPRes.data.map((p) => [p.quotation_id, p.policy_no || null]));
  const motorPolicyByQuotation = new Map(motorPRes.data.map((p) => [p.quotation_id, p.policy_no || null]));
  const fpConvertedByQuotation = new Set(fpPRes.data.map((p) => p.quotation_id));
  const motorConvertedByQuotation = new Set(motorPRes.data.map((p) => p.quotation_id));

  // A case can have multiple surveys in principle, but only ever one that
  // actually matters for "this property's GIS data" — take the latest
  // (highest id) if more than one exists for the same case.
  const surveyByCase = new Map();
  for (const s of surveyRes.data) {
    const existing = surveyByCase.get(s.insurance_case_id);
    if (!existing || s.id > existing.id) surveyByCase.set(s.insurance_case_id, s);
  }
  const gisFromSurvey = (caseId) => {
    const survey = surveyByCase.get(caseId);
    return {
      latitude: survey?.latitude ?? null,
      longitude: survey?.longitude ?? null,
      flood_risk_flag: survey?.flood_risk_flag ?? null,
      flood_risk_category: survey?.flood_risk_category ?? null,
      river_flood_category: survey?.river_flood_category ?? null,
      storm_surge_category: survey?.storm_surge_category ?? null,
    };
  };

  // Raw API fields are spread as-is so they line up 1:1 with
  // FIRE_QUOTATION_COLUMNS/MOTOR_QUOTATION_COLUMNS's dataKeys in policy.jsx.
  const fp = fpQRes.data.map((q) => ({
    ...q,
    line: "Fire & Property",
    client_name: resolveClientName(q.insurance_case_id),
    converted_policy_no: fpPolicyByQuotation.get(q.id) ?? null,
    is_converted: fpConvertedByQuotation.has(q.id),
    // A Fire quotation without its own Location of Risk shows its survey's (the map and
    // rating already come from that survey).
    address_label: q.location_of_risk || surveyByCase.get(q.insurance_case_id)?.location_of_risk || null,
    ...gisFromSurvey(q.insurance_case_id),
  }));
  const motor = motorQRes.data.map((q) => ({
    ...q,
    line: "Motor Car",
    client_name: resolveClientName(q.insurance_case_id),
    converted_policy_no: motorPolicyByQuotation.get(q.id) ?? null,
    is_converted: motorConvertedByQuotation.has(q.id),
    address_label: q.address,
    // Motor Quotation already stores its own GIS fields directly (unlike
    // Fire's fields above, which are borrowed from a Survey) — left as-is
    // from the spread.
  }));

  return [...fp, ...motor];
}
