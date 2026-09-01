import { useState, useEffect, useCallback } from "react";
import { ChevronDown, Search, Upload, Trash2 } from "lucide-react";
import axios from "axios";
import Sidebar from "../components/sidebar";
import UploadModal from "../components/UploadFileModal";
import NeedsReviewModal from "../components/NeedsReviewModal";
import { FullCalendarPicker } from "../components/DatePicker";

const API_BASE_URL = "http://127.0.0.1:8000";

// ── Stat Cards
// `type` is the TYPE_OPTIONS value each card switches to on click.
const statCards = [
  { label: "Total Policies", value: null, type: "Policy" }, // filled in dynamically at render time
  { label: "Total Quotation", value: null, type: "Quotation" },
  { label: "Total Claims", value: "421", type: "Claims" },
  { label: "Total Client Information", value: null, type: "Client Information" },
  { label: "Total Survey Report", value: null, type: "Survey Report" },
  { label: "Total Vehicle Information", value: null, type: "Vehicle Information" },
];

const TYPE_OPTIONS = ["Policy", "Quotation", "Claims", "Client Information", "Survey Report", "Vehicle Information"];
const LINE_OPTIONS = ["All Lines", "Fire & Property", "Motor Car"];
// Policy has no merged/"All Lines" view (that's the reason it was split into
// two column sets in the first place) — this dedicated dropdown only
// appears on the Policy tab, mirroring the Quotation tab's own line filter.
const POLICY_LINE_OPTIONS = ["Fire & Property", "Motor Car"];
const PAGE_SIZE = 8;

// ── Helpers for backend data → display strings ─────────────────────────────
function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d)) return "—";
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  return `${mm}/${dd}/${yyyy}`;
}

function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (isNaN(n)) return "—";
  return `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatOrDash(value) {
  if (value === null || value === undefined || value === "") return "—";
  return value;
}

function formatCell(value, type) {
  if (type === "date") return formatDate(value);
  if (type === "currency") return formatCurrency(value);
  return formatOrDash(value);
}

// The date filter's underlying rows aren't all formatted the same way —
// most tabs pre-format their date field to "MM/DD/YYYY" during fetch, but
// Policy shows raw API rows (like Client Information) with an ISO date
// string instead. Rather than reformatting Policy's data to match, this
// parses either shape into the same {month, day, year} so one filter works
// against both.
function extractDateParts(value) {
  if (!value) return null;
  if (typeof value === "string" && value.includes("/")) {
    const [mm, dd, yyyy] = value.split("/").map(Number);
    if (!mm || !dd || !yyyy) return null;
    return { month: mm, day: dd, year: yyyy };
  }
  const d = new Date(value);
  if (isNaN(d)) return null;
  return { month: d.getUTCMonth() + 1, day: d.getUTCDate(), year: d.getUTCFullYear() };
}

const claimsData = [
  { claim: "CLM-3001", policy: "POL-1012", client: "Ricardo Santiago", loss: "02/15/2026", reported: "02/16/2026", line: "Motor Car", type: "Collision", reserve: "₱65,000", paid: "₱65,000", status: "Paid", fraud: "No" },
  { claim: "CLM-3002", policy: "POL-1013", client: "Sofia Ramirez", loss: "02/20/2026", reported: "02/21/2026", line: "Fire & Property", type: "Fire", reserve: "₱1,800,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { claim: "CLM-3003", policy: "POL-1001", client: "Juan Dela Cruz", loss: "01/28/2026", reported: "01/29/2026", line: "Motor Car", type: "Own Damage", reserve: "₱22,500", paid: "₱20,000", status: "Paid", fraud: "No" },
  { claim: "CLM-3004", policy: "POL-1014", client: "Carmen Flores", loss: "03/05/2026", reported: "03/06/2026", line: "Fire & Property", type: "Typhoon Damage", reserve: "₱950,000", paid: "₱0", status: "Approved", fraud: "No" },
  { claim: "CLM-3005", policy: "POL-1007", client: "Dennis Reyes", loss: "02/25/2026", reported: "02/26/2026", line: "Motor Car", type: "Theft", reserve: "₱920,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { claim: "CLM-3006", policy: "POL-1015", client: "Elena Cruz", loss: "03/01/2026", reported: "03/02/2026", line: "Motor Car", type: "Collision", reserve: "₱48,000", paid: "₱45,000", status: "Paid", fraud: "No" },
  { claim: "CLM-3007", policy: "POL-1016", client: "Leonor Rivera", loss: "03/10/2026", reported: "03/11/2026", line: "Fire & Property", type: "Flood", reserve: "₱620,000", paid: "₱0", status: "Investigating", fraud: "No" },
  { claim: "CLM-3008", policy: "POL-1003", client: "Roberto Gomez", loss: "02/05/2026", reported: "02/06/2026", line: "Fire & Property", type: "Fire", reserve: "₱2,200,000", paid: "₱0", status: "Paid", fraud: "No" },
  { claim: "CLM-3009", policy: "POL-1017", client: "Melchora Aquino", loss: "03/18/2026", reported: "03/19/2026", line: "Fire & Property", type: "Earthquake", reserve: "₱3,500,000", paid: "₱0", status: "Reported", fraud: "No" },
  { claim: "CLM-3010", policy: "POL-1010", client: "Sofia Ramirez", loss: "03/20/2026", reported: "03/21/2026", line: "Motor Car", type: "Accident", reserve: "₱38,000", paid: "₱38,000", status: "Paid", fraud: "No" },
  { claim: "CLM-3011", policy: "POL-1011", client: "Ricardo Santiago", loss: "03/22/2026", reported: "03/23/2026", line: "Fire & Property", type: "Vandalism", reserve: "₱410,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { claim: "CLM-3012", policy: "POL-1005", client: "Lina Mercado", loss: "03/25/2026", reported: "03/26/2026", line: "Fire & Property", type: "Fire", reserve: "₱1,550,000", paid: "₱0", status: "Approved", fraud: "No" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function Dropdown({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap">
        {value || label}
        <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[160px]">
          {options.map(opt => (
            <button key={opt} onClick={() => { onChange(opt); setOpen(false); }}
              className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${value === opt ? "font-bold text-black" : "text-gray-600"}`}>
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RiskClassBadge({ riskClass }) {
  const labels = { a: "Class A (Concrete)", b: "Class B (Concrete & Wood)" };
  const colors = { a: "text-green-600 bg-green-50", b: "text-yellow-700 bg-yellow-50" };
  const key = (riskClass || "").toLowerCase();
  if (!labels[key]) return <span className="text-gray-400">—</span>;
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold whitespace-nowrap ${colors[key]}`}>{labels[key]}</span>;
}

// ── Table renderers (receive sliced `rows`) ───────────────────────────────────
function QuotationTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Quote Number", "Policyholder ID", "Quotation ID", "Quote Date", "Client Name", "Policy Line", "Premium", "Sum Insured", "Period Cover", "Converted Policy No."].map(h =>
          <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-3">{r.quote}</td>
          <td className="py-3 px-3 text-gray-500">{r.policyholderId}</td>
          <td className="py-3 px-3 text-gray-500">{r.quotationId}</td>
          <td className="py-3 px-3">{r.date}</td>
          <td className="py-3 px-3">{r.client}</td>
          <td className="py-3 px-3">{r.line}</td>
          <td className="py-3 px-3">{r.premium}</td><td className="py-3 px-3">{r.sum}</td>
          <td className="py-3 px-3">{r.period}</td>
          <td className="py-3 px-3 font-medium">{r.converted}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function ClaimsTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Claim Number", "Policy Number", "Client Name", "Date of Loss", "Date Reported", "Policy Line", "Claim Type", "Reserve Amount", "Paid Amount", "Status", "Fraud Flag"].map(h =>
          <th key={h} className="py-3 px-2 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-2">{r.claim}</td><td className="py-3 px-2">{r.policy}</td>
          <td className="py-3 px-2">{r.client}</td><td className="py-3 px-2">{r.loss}</td>
          <td className="py-3 px-2">{r.reported}</td><td className="py-3 px-2">{r.line}</td>
          <td className="py-3 px-2">{r.type}</td><td className="py-3 px-2">{r.reserve}</td>
          <td className="py-3 px-2">{r.paid}</td><td className="py-3 px-2">{r.status}</td>
          <td className="py-3 px-2">
            <span className={`font-semibold ${r.fraud === "Yes" ? "text-red-500" : "text-gray-500"}`}>{r.fraud}</span>
          </td>
        </tr>
      ))}</tbody>
    </table>
  );
}

// Every displayed column maps 1:1 to a field on PolicyholderOut (Backend/app/schemas.py).
// created_at / updated_at are deliberately excluded — internal audit timestamps, not client-facing info.
const CLIENT_COLUMNS = [
  { key: "id", header: "Client ID", width: "min-w-[70px]" },
  { key: "last_name", header: "Last Name", width: "min-w-[130px]", align: "text-left" },
  { key: "first_name", header: "First Name", width: "min-w-[130px]", align: "text-left" },
  { key: "middle_name", header: "Middle Name", width: "min-w-[130px]", align: "text-left" },
  { key: "gender", header: "Sex", width: "min-w-[70px]" },
  { key: "nationality", header: "Nationality", width: "min-w-[110px]" },
  { key: "marital_status", header: "Marital Status", width: "min-w-[120px]" },
  { key: "spouse_full_name", header: "Spouse Name", width: "min-w-[150px]", align: "text-left" },
  { key: "present_address", header: "Present Address", width: "min-w-[200px]", align: "text-left" },
  { key: "permanent_address", header: "Permanent Address", width: "min-w-[200px]", align: "text-left" },
  { key: "residence_phone", header: "Residence Phone", width: "min-w-[130px]" },
  { key: "mobile_number", header: "Mobile Number", width: "min-w-[130px]" },
  { key: "email_address", header: "Email Address", width: "min-w-[190px]", align: "text-left text-blue-500" },
  { key: "zip_code", header: "Zip Code", width: "min-w-[90px]" },
  { key: "occupation", header: "Occupation", width: "min-w-[130px]", align: "text-left" },
  { key: "employer", header: "Employer", width: "min-w-[150px]", align: "text-left" },
  { key: "tin", header: "TIN", width: "min-w-[110px]" },
  { key: "sss_no", header: "SSS No.", width: "min-w-[110px]" },
];

function clientDisplayName(row) {
  return [row.last_name, row.first_name].filter(Boolean).join(", ") || `Client #${row.id}`;
}

function ClientTable({ rows, onDelete }) {
  return (
    <table className="min-w-max text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {CLIENT_COLUMNS.map(col =>
          <th key={col.key} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{col.header}</th>)}
        <th className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">Actions</th>
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          {CLIENT_COLUMNS.map(col => (
            <td key={col.key} className={`py-3 px-3 whitespace-nowrap ${col.width} ${col.align || ""}`}>
              {formatOrDash(r[col.key])}
            </td>
          ))}
          <td className="py-3 px-3 whitespace-nowrap">
            <button
              type="button"
              title="Delete client"
              onClick={() => onDelete?.(r)}
              className="text-gray-400 hover:text-red-500 transition"
            >
              <Trash2 className="w-3.5 h-3.5 mx-auto" />
            </button>
          </td>
        </tr>
      ))}</tbody>
    </table>
  );
}

// Both policy tables expose every real column from FirePropertyPolicyOut /
// MotorPolicyOut (Backend/app/schemas.py), plus one synthesized field:
// "Client Name" resolves the real policyholder via quotation_id →
// insurance_case → policyholder (the same join Vehicle Information already
// uses — see fetchFirePropertyPolicies/fetchMotorPolicies below), while
// "Insured Name & Address" stays the raw literal text field straight off
// the policy record, unchanged. The two usually agree, but a mismatch is a
// real data signal worth seeing, not a bug to reconcile.
const FIRE_POLICY_COLUMNS = [
  { id: "id", dataKey: "id", header: "Policy ID", width: "min-w-[80px]" },
  { id: "policy_no", dataKey: "policy_no", header: "Policy No.", width: "min-w-[130px]" },
  { id: "quotation_id", dataKey: "quotation_id", header: "Quotation ID", width: "min-w-[110px]" },
  { id: "client_name", dataKey: "client_name", header: "Client Name", width: "min-w-[220px]", align: "text-left" },
  { id: "insured_name_address", dataKey: "insured_name_address", header: "Insured Name & Address", width: "min-w-[220px]", align: "text-left" },
  { id: "line_of_insurance", dataKey: "line_of_insurance", header: "Line of Insurance", width: "min-w-[150px]" },
  { id: "issue_date", dataKey: "issue_date", header: "Issue Date", type: "date", width: "min-w-[110px]" },
  { id: "period_from", dataKey: "period_from", header: "Period From", type: "date", width: "min-w-[110px]" },
  { id: "period_to", dataKey: "period_to", header: "Period To", type: "date", width: "min-w-[110px]" },
  { id: "renewing_policy_no", dataKey: "renewing_policy_no", header: "Renewing Policy No.", width: "min-w-[150px]" },
  { id: "tin", dataKey: "tin", header: "TIN", width: "min-w-[110px]" },
  { id: "agency_code", dataKey: "agency_code", header: "Agency Code", width: "min-w-[110px]" },
  { id: "total_amount_due", dataKey: "total_amount_due", header: "Total Amount Due", type: "currency", width: "min-w-[150px]" },
  { id: "replacing_cover_note_no", dataKey: "replacing_cover_note_no", header: "Replacing Cover Note No.", width: "min-w-[170px]" },
  { id: "premium_invoice_no", dataKey: "premium_invoice_no", header: "Premium Invoice No.", width: "min-w-[150px]" },
  { id: "official_receipt_no", dataKey: "official_receipt_no", header: "Official Receipt No.", width: "min-w-[150px]" },
  { id: "coverage_description", dataKey: "coverage_description", header: "Coverage Description", width: "min-w-[220px]", align: "text-left" },
  { id: "sum_insured", dataKey: "sum_insured", header: "Sum Insured", type: "currency", width: "min-w-[150px]" },
  { id: "unit_cost_premium", dataKey: "unit_cost_premium", header: "Unit Cost Premium", type: "currency", width: "min-w-[150px]" },
  { id: "property_insured", dataKey: "property_insured", header: "Property Insured", width: "min-w-[170px]", align: "text-left" },
  { id: "construction", dataKey: "construction", header: "Construction", width: "min-w-[130px]" },
  { id: "occupancy", dataKey: "occupancy", header: "Occupancy", width: "min-w-[130px]" },
];

const MOTOR_POLICY_COLUMNS = [
  { id: "id", dataKey: "id", header: "Policy ID", width: "min-w-[80px]" },
  { id: "policy_no", dataKey: "policy_no", header: "Policy No.", width: "min-w-[130px]" },
  { id: "quotation_id", dataKey: "quotation_id", header: "Quotation ID", width: "min-w-[110px]" },
  { id: "client_name", dataKey: "client_name", header: "Client Name", width: "min-w-[220px]", align: "text-left" },
  { id: "insured_name_address", dataKey: "insured_name_address", header: "Insured Name & Address", width: "min-w-[220px]", align: "text-left" },
  { id: "line_of_insurance", dataKey: "line_of_insurance", header: "Line of Insurance", width: "min-w-[150px]" },
  { id: "issue_date", dataKey: "issue_date", header: "Issue Date", type: "date", width: "min-w-[110px]" },
  { id: "period_from", dataKey: "period_from", header: "Period From", type: "date", width: "min-w-[110px]" },
  { id: "period_to", dataKey: "period_to", header: "Period To", type: "date", width: "min-w-[110px]" },
  { id: "renewing_policy_no", dataKey: "renewing_policy_no", header: "Renewing Policy No.", width: "min-w-[150px]" },
  { id: "tin", dataKey: "tin", header: "TIN", width: "min-w-[110px]" },
  { id: "agency_code", dataKey: "agency_code", header: "Agency Code", width: "min-w-[110px]" },
  { id: "total_amount_due", dataKey: "total_amount_due", header: "Total Amount Due", type: "currency", width: "min-w-[150px]" },
  { id: "replacing_cover_note_no", dataKey: "replacing_cover_note_no", header: "Replacing Cover Note No.", width: "min-w-[170px]" },
  { id: "premium_invoice_no", dataKey: "premium_invoice_no", header: "Premium Invoice No.", width: "min-w-[150px]" },
  { id: "official_receipt_no", dataKey: "official_receipt_no", header: "Official Receipt No.", width: "min-w-[150px]" },
  { id: "coc_no", dataKey: "coc_no", header: "COC No.", width: "min-w-[120px]" },
  { id: "coi_no", dataKey: "coi_no", header: "COI No.", width: "min-w-[120px]" },
  { id: "endorsement_no", dataKey: "endorsement_no", header: "Endorsement No.", width: "min-w-[140px]" },
  { id: "deductible", dataKey: "deductible", header: "Deductible", type: "currency", width: "min-w-[130px]" },
];

function GenericPolicyTable({ columns, rows, onDelete }) {
  return (
    <table className="min-w-max text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {columns.map(col =>
          <th key={col.id} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{col.header}</th>)}
        <th className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">Actions</th>
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          {columns.map(col => (
            <td key={col.id} className={`py-3 px-3 whitespace-nowrap ${col.width} ${col.align || ""}`}>
              {formatCell(r[col.dataKey], col.type)}
            </td>
          ))}
          <td className="py-3 px-3 whitespace-nowrap">
            <button
              type="button"
              title="Delete policy"
              onClick={() => onDelete?.(r)}
              className="text-gray-400 hover:text-red-500 transition"
            >
              <Trash2 className="w-3.5 h-3.5 mx-auto" />
            </button>
          </td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function SurveyTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Survey ID", "Policyholder ID", "Quotation ID(s)", "Client Name", "Survey Date", "Location of Risk", "Risk Class", "Zone", "Max. Amount Subject", "Loss Record", "Flood Risk"].map(h =>
          <th key={h} className="py-3 px-2 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-2">{r.id}</td>
          <td className="py-3 px-2 text-gray-500">{r.policyholderId}</td>
          <td className="py-3 px-2 text-gray-500">{r.quotationIds}</td>
          <td className="py-3 px-2">{r.client}</td>
          <td className="py-3 px-2">{r.date}</td>
          <td className="py-3 px-2 text-left max-w-[160px] text-gray-600">{r.location}</td>
          <td className="py-3 px-2"><RiskClassBadge riskClass={r.riskClass} /></td>
          <td className="py-3 px-2">{r.zone}</td>
          <td className="py-3 px-2">{r.maxAmount}</td>
          <td className="py-3 px-2 text-left max-w-[160px] text-gray-600">{r.lossRecord}</td>
          <td className="py-3 px-2">{r.floodRisk}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function VehicleTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Vehicle ID", "Policyholder ID", "Quotation ID(s)", "Client Name", "Make", "Model", "Body Type", "Color", "Plate No.", "Engine No.", "Chassis No.", "Authorized Capacity"].map(h =>
          <th key={h} className="py-3 px-2 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-2">{r.id}</td>
          <td className="py-3 px-2 text-gray-500">{r.policyholderId}</td>
          <td className="py-3 px-2 text-gray-500">{r.quotationIds}</td>
          <td className="py-3 px-2">{r.client}</td>
          <td className="py-3 px-2">{r.make}</td>
          <td className="py-3 px-2">{r.model}</td>
          <td className="py-3 px-2">{r.bodyType}</td>
          <td className="py-3 px-2">{r.color}</td>
          <td className="py-3 px-2">{r.plateNo}</td>
          <td className="py-3 px-2">{r.engineNo}</td>
          <td className="py-3 px-2">{r.chassisNo}</td>
          <td className="py-3 px-2">{r.authorizedCapacity}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

// Map each table type to the date field used for month filtering.
// Policy filters on issue_date — the direct analog of Quotation's
// quotation_date, and the natural "when did this policy start" anchor;
// period_from/period_to are a coverage window rather than a single date.
// Its rows are raw ISO date strings rather than the "MM/DD/YYYY" strings
// other tabs pre-format — extractDateParts() (above) is what lets the same
// filter logic below handle both without reformatting Policy's data.
const DATE_FIELD_MAP = {
  "Policy": "issue_date",
  "Quotation": "date",
  "Claims": "loss",
  "Survey Report": "date",
  "Client Information": null, // no date field — month filter doesn't apply
  "Vehicle Information": null, // created_at is an import timestamp, not a business date
};

// Which bulk importer the Upload button should default to for the active
// tab. The user can still switch it inside the modal — Quotation mixes data
// from both lines, so there's no single correct guess for it. Policy's
// default is resolved separately below (via policyLine), since it depends
// on which of the two line sub-filters is currently selected.
const IMPORT_TARGET_BY_TYPE = {
  "Client Information": "policyholders",
  "Survey Report": "fire-property",
  "Quotation": "motor",
  "Claims": "policyholders",
  "Vehicle Information": "motor",
};

function parseMonthLabel(label) {
  const MONTHS = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];
  const [monthName, year] = label.split(" ");
  return { month: MONTHS.indexOf(monthName) + 1, year: parseInt(year) };
}

// Check if a date string "MM/DD/YYYY" matches the selected month/year
function dateMatchesMonth(dateStr, monthLabel) {
  if (!dateStr || !monthLabel) return true;
  const { month, year } = parseMonthLabel(monthLabel);
  const [mm, , yyyy] = dateStr.split("/").map(Number);
  return mm === month && yyyy === year;
}

export default function PolicyHolderInformation() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("Policy");
  const [lineFilter, setLineFilter] = useState("All Lines");
  // Which of the two Policy line views is showing — defaults to Fire &
  // Property, matching the original tab ordering before the split.
  const [policyLine, setPolicyLine] = useState("Fire & Property");
  const [uploadOpen, setUploadOpen] = useState(false);

  const [fromDate, setFromDate] = useState(null);
  const [year, setYear] = useState(2026);

  const [clientRecords, setClientRecords] = useState([]);
  const [clientLoading, setClientLoading] = useState(true);
  const [clientError, setClientError] = useState(null);

  const fetchClients = useCallback(async () => {
    setClientLoading(true);
    setClientError(null);
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(`${API_BASE_URL}/policyholders`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setClientRecords(response.data);
    } catch (err) {
      setClientError("Failed to load client information.");
    } finally {
      setClientLoading(false);
    }
  }, []);

  const [firePolicyRecords, setFirePolicyRecords] = useState([]);
  const [firePolicyLoading, setFirePolicyLoading] = useState(true);
  const [firePolicyError, setFirePolicyError] = useState(null);

  const fetchFirePropertyPolicies = useCallback(async () => {
    setFirePolicyLoading(true);
    setFirePolicyError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [policyRes, quotationRes, casesRes, phRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/fire-property/policies`, { headers }),
        axios.get(`${API_BASE_URL}/fire-property/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
        axios.get(`${API_BASE_URL}/policyholders`, { headers }),
      ]);
      // A policy only stores quotation_id — walk quotation → case →
      // policyholder to resolve the real Client Name, same join Vehicle
      // Information uses. insured_name_address (kept as-is below) is a
      // separate literal field and can legitimately disagree with this.
      const caseByQuotation = new Map(quotationRes.data.map((q) => [q.id, q.insurance_case_id]));
      const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
      const nameByPolicyholder = new Map(
        phRes.data.map((p) => [p.id, [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ")])
      );
      const withClientName = policyRes.data.map((p) => {
        const caseId = caseByQuotation.get(p.quotation_id);
        const policyholderId = caseId !== undefined ? policyholderByCase.get(caseId) : undefined;
        return { ...p, client_name: nameByPolicyholder.get(policyholderId) || null };
      });
      setFirePolicyRecords(withClientName);
    } catch (err) {
      setFirePolicyError("Failed to load Fire/Property policies.");
    } finally {
      setFirePolicyLoading(false);
    }
  }, []);

  const [motorPolicyRecords, setMotorPolicyRecords] = useState([]);
  const [motorPolicyLoading, setMotorPolicyLoading] = useState(true);
  const [motorPolicyError, setMotorPolicyError] = useState(null);

  const fetchMotorPolicies = useCallback(async () => {
    setMotorPolicyLoading(true);
    setMotorPolicyError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [policyRes, quotationRes, casesRes, phRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/motor/policies`, { headers }),
        axios.get(`${API_BASE_URL}/motor/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
        axios.get(`${API_BASE_URL}/policyholders`, { headers }),
      ]);
      // Same join as fetchFirePropertyPolicies above (and Vehicle
      // Information): quotation_id → insurance_case → policyholder.
      const caseByQuotation = new Map(quotationRes.data.map((q) => [q.id, q.insurance_case_id]));
      const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
      const nameByPolicyholder = new Map(
        phRes.data.map((p) => [p.id, [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ")])
      );
      const withClientName = policyRes.data.map((p) => {
        const caseId = caseByQuotation.get(p.quotation_id);
        const policyholderId = caseId !== undefined ? policyholderByCase.get(caseId) : undefined;
        return { ...p, client_name: nameByPolicyholder.get(policyholderId) || null };
      });
      setMotorPolicyRecords(withClientName);
    } catch (err) {
      setMotorPolicyError("Failed to load Motor/Car policies.");
    } finally {
      setMotorPolicyLoading(false);
    }
  }, []);

  const [quotationRecords, setQuotationRecords] = useState([]);
  const [quotationLoading, setQuotationLoading] = useState(true);
  const [quotationError, setQuotationError] = useState(null);

  const fetchQuotations = useCallback(async () => {
    setQuotationLoading(true);
    setQuotationError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [fpQRes, motorQRes, fpPRes, motorPRes, casesRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/fire-property/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/motor/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/fire-property/policies`, { headers }),
        axios.get(`${API_BASE_URL}/motor/policies`, { headers }),
        axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
      ]);
      const fpPolicyByQuotation = new Map(fpPRes.data.map((p) => [p.quotation_id, p.policy_no || "—"]));
      const motorPolicyByQuotation = new Map(motorPRes.data.map((p) => [p.quotation_id, p.policy_no || "—"]));
      const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));

      const fp = fpQRes.data.map((q) => ({
        quote: `FP-Q-${q.id}`,
        date: formatDate(q.quotation_date),
        client: q.insured_name || "—",
        caseId: q.insurance_case_id ?? "—",
        policyholderId: policyholderByCase.get(q.insurance_case_id) ?? "—",
        quotationId: q.id,
        line: "Fire & Property",
        premium: formatCurrency(q.total_premium),
        sum: formatCurrency(q.total_sum_insured),
        period: q.period_cover || "—",
        converted: fpPolicyByQuotation.get(q.id) || "—",
      }));
      const motor = motorQRes.data.map((q) => ({
        quote: `MC-Q-${q.id}`,
        date: formatDate(q.quotation_date),
        client: q.insured_name || "—",
        caseId: q.insurance_case_id ?? "—",
        policyholderId: policyholderByCase.get(q.insurance_case_id) ?? "—",
        quotationId: q.id,
        line: "Motor Car",
        premium: formatCurrency(q.total_amount_due),
        sum: "—",
        period: "—",
        converted: motorPolicyByQuotation.get(q.id) || "—",
      }));
      setQuotationRecords([...fp, ...motor]);
    } catch (err) {
      setQuotationError("Failed to load quotations.");
    } finally {
      setQuotationLoading(false);
    }
  }, []);

  const [surveyRecords, setSurveyRecords] = useState([]);
  const [surveyLoading, setSurveyLoading] = useState(true);
  const [surveyError, setSurveyError] = useState(null);

  const fetchSurveys = useCallback(async () => {
    setSurveyLoading(true);
    setSurveyError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [surveyRes, casesRes, fpQRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/fire-property/surveys`, { headers }),
        axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
        axios.get(`${API_BASE_URL}/fire-property/quotations`, { headers }),
      ]);
      const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
      // A survey has no direct FK to a quotation — both link to the same
      // insurance case instead, and one case can have multiple quotations
      // (re-quotes reuse the case), so group rather than map 1:1.
      const quotationsByCase = new Map();
      for (const q of fpQRes.data) {
        const list = quotationsByCase.get(q.insurance_case_id) || [];
        list.push(`FP-Q-${q.id}`);
        quotationsByCase.set(q.insurance_case_id, list);
      }
      const transformed = surveyRes.data.map((s) => ({
        id: `SURV-${s.id}`,
        client: s.name_of_insured || "—",
        caseId: s.insurance_case_id ?? "—",
        policyholderId: policyholderByCase.get(s.insurance_case_id) ?? "—",
        quotationIds: (quotationsByCase.get(s.insurance_case_id) || []).join(", ") || "—",
        date: formatDate(s.created_at),
        location: s.location_of_risk || "—",
        riskClass: s.risk_class || null,
        zone: s.zone || "—",
        maxAmount: formatCurrency(s.maximum_amount_subject),
        lossRecord: s.loss_record || "—",
        floodRisk:
          s.flood_risk_category ||
          (s.flood_risk_flag === null || s.flood_risk_flag === undefined
            ? "—"
            : s.flood_risk_flag ? "Flood-Prone" : "Not Flood-Prone"),
      }));
      setSurveyRecords(transformed);
    } catch (err) {
      setSurveyError("Failed to load survey reports.");
    } finally {
      setSurveyLoading(false);
    }
  }, []);

  const [vehicleRecords, setVehicleRecords] = useState([]);
  const [vehicleLoading, setVehicleLoading] = useState(true);
  const [vehicleError, setVehicleError] = useState(null);

  const fetchVehicles = useCallback(async () => {
    setVehicleLoading(true);
    setVehicleError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [vehicleRes, casesRes, motorQRes, phRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/motor/vehicles`, { headers }),
        axios.get(`${API_BASE_URL}/insurance-cases`, { headers }),
        axios.get(`${API_BASE_URL}/motor/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/policyholders`, { headers }),
      ]);
      const policyholderByCase = new Map(casesRes.data.map((c) => [c.id, c.policyholder_id]));
      const nameByPolicyholder = new Map(
        phRes.data.map((p) => [p.id, [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" ")])
      );
      // A vehicle has no direct FK to a quotation — both link to the same
      // insurance case instead, and one case can have multiple quotations
      // (re-quotes reuse the case), so group rather than map 1:1.
      const quotationsByCase = new Map();
      for (const q of motorQRes.data) {
        const list = quotationsByCase.get(q.insurance_case_id) || [];
        list.push(`MC-Q-${q.id}`);
        quotationsByCase.set(q.insurance_case_id, list);
      }
      const transformed = vehicleRes.data.map((v) => {
        const policyholderId = policyholderByCase.get(v.insurance_case_id);
        return {
          id: `VEH-${v.id}`,
          caseId: v.insurance_case_id ?? "—",
          policyholderId: policyholderId ?? "—",
          quotationIds: (quotationsByCase.get(v.insurance_case_id) || []).join(", ") || "—",
          client: nameByPolicyholder.get(policyholderId) || "—",
          make: v.make || "—",
          model: v.model || "—",
          bodyType: v.body_type || "—",
          color: v.color || "—",
          plateNo: v.plate_no || "—",
          engineNo: v.motor_engine_no || "—",
          chassisNo: v.serial_chassis_no || "—",
          authorizedCapacity: v.authorized_capacity || "—",
        };
      });
      setVehicleRecords(transformed);
    } catch (err) {
      setVehicleError("Failed to load vehicle information.");
    } finally {
      setVehicleLoading(false);
    }
  }, []);

  const [needsReviewOpen, setNeedsReviewOpen] = useState(false);
  const [needsReviewRecords, setNeedsReviewRecords] = useState([]);
  const [needsReviewLoading, setNeedsReviewLoading] = useState(true);

  const fetchNeedsReview = useCallback(async () => {
    setNeedsReviewLoading(true);
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(`${API_BASE_URL}/import/policyholders/needs-review`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setNeedsReviewRecords(response.data);
    } catch (err) {
      // Non-fatal for the page — the badge just won't update.
    } finally {
      setNeedsReviewLoading(false);
    }
  }, []);

  const refreshClientData = useCallback(() => {
    fetchClients();
    fetchNeedsReview();
  }, [fetchClients, fetchNeedsReview]);

  // A bulk import can touch policyholders, cases, surveys, vehicles, and
  // quotations depending on which importer ran — refresh everything rather
  // than guessing which tabs are affected.
  const refreshAllData = useCallback(() => {
    fetchClients();
    fetchNeedsReview();
    fetchFirePropertyPolicies();
    fetchMotorPolicies();
    fetchQuotations();
    fetchSurveys();
    fetchVehicles();
  }, [fetchClients, fetchNeedsReview, fetchFirePropertyPolicies, fetchMotorPolicies, fetchQuotations, fetchSurveys, fetchVehicles]);

  const deletePolicyholder = useCallback(async (row) => {
    if (!window.confirm(`Delete client "${clientDisplayName(row)}"? This moves the record to the deleted archive.`)) return;
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`${API_BASE_URL}/policyholders/${row.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      refreshClientData();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete this client.");
    }
  }, [refreshClientData]);

  const deleteFirePropertyPolicy = useCallback(async (row) => {
    if (!window.confirm(`Delete policy "${row.policy_no || `#${row.id}`}"? This moves the record to the deleted archive.`)) return;
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`${API_BASE_URL}/fire-property/policies/${row.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      fetchFirePropertyPolicies();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete this policy.");
    }
  }, [fetchFirePropertyPolicies]);

  const deleteMotorPolicy = useCallback(async (row) => {
    if (!window.confirm(`Delete policy "${row.policy_no || `#${row.id}`}"? This moves the record to the deleted archive.`)) return;
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`${API_BASE_URL}/motor/policies/${row.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      fetchMotorPolicies();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete this policy.");
    }
  }, [fetchMotorPolicies]);

  useEffect(() => {
    fetchClients();
    fetchNeedsReview();
    fetchFirePropertyPolicies();
    fetchMotorPolicies();
    fetchQuotations();
    fetchSurveys();
    fetchVehicles();
  }, [fetchClients, fetchNeedsReview, fetchFirePropertyPolicies, fetchMotorPolicies, fetchQuotations, fetchSurveys, fetchVehicles]);

  // Policy is one tab again, but still backed by two entirely separate
  // column sets/fetches — policyLine picks which one is currently showing.
  const isMotorLine = policyLine === "Motor Car";
  const policyRecords = isMotorLine ? motorPolicyRecords : firePolicyRecords;
  const policyLoading = isMotorLine ? motorPolicyLoading : firePolicyLoading;
  const policyError = isMotorLine ? motorPolicyError : firePolicyError;
  const policyColumns = isMotorLine ? MOTOR_POLICY_COLUMNS : FIRE_POLICY_COLUMNS;
  const deletePolicyForLine = isMotorLine ? deleteMotorPolicy : deleteFirePropertyPolicy;

  const DATA_MAP = {
    "Policy": policyRecords,
    "Quotation": quotationRecords,
    "Claims": claimsData,
    "Client Information": clientRecords,
    "Survey Report": surveyRecords,
    "Vehicle Information": vehicleRecords,
  };

  const LOADING_MAP = {
    "Policy": policyLoading,
    "Quotation": quotationLoading,
    "Claims": false,
    "Client Information": clientLoading,
    "Survey Report": surveyLoading,
    "Vehicle Information": vehicleLoading,
  };

  const ERROR_MAP = {
    "Policy": policyError,
    "Quotation": quotationError,
    "Claims": null,
    "Client Information": clientError,
    "Survey Report": surveyError,
    "Vehicle Information": vehicleError,
  };

  // Combined count (fire + motor together) — the stat card isn't split by line.
  const totalPoliciesLoading = firePolicyLoading || motorPolicyLoading;
  const totalPolicyCount = firePolicyRecords.length + motorPolicyRecords.length;

  const displayStatCards = statCards.map((c) => {
    if (c.label === "Total Client Information") return { ...c, value: clientLoading ? "…" : String(clientRecords.length) };
    if (c.label === "Total Policies") return { ...c, value: totalPoliciesLoading ? "…" : String(totalPolicyCount) };
    if (c.label === "Total Quotation") return { ...c, value: quotationLoading ? "…" : String(quotationRecords.length) };
    if (c.label === "Total Survey Report") return { ...c, value: surveyLoading ? "…" : String(surveyRecords.length) };
    if (c.label === "Total Vehicle Information") return { ...c, value: vehicleLoading ? "…" : String(vehicleRecords.length) };
    return c;
  });

  const handleTypeChange = (t) => { setType(t); setPage(1); setSearch(""); setLineFilter("All Lines"); setPolicyLine("Fire & Property"); setFromDate(null); };
  const handleSearch = (v) => { setSearch(v); setPage(1); };

  // Insurance-line filter only makes sense where rows mix both lines.
  const showLineFilter = type === "Quotation";
  // Policy's own line switch — same idea, but selects between two entirely
  // separate column sets/fetches rather than filtering rows within one array.
  const showPolicyLineFilter = type === "Policy";

  // Filter by search + month then paginate
  const allRows = DATA_MAP[type] || [];
  const dateField = DATE_FIELD_MAP[type];

  const selectedMonth = fromDate ? fromDate.getMonth() + 1 : null;
  const selectedDay = fromDate ? fromDate.getDate() : null;
  const selectedYear = fromDate ? fromDate.getFullYear() : null;

  const filtered = allRows.filter((row) => {
    const searchText = search.toLowerCase();

    const matchSearch =
      searchText === "" ||
      Object.values(row).some((value) =>
        String(value).toLowerCase().includes(searchText)
      );

    let matchDate = true;

    if (dateField && row[dateField] && selectedMonth && selectedDay && selectedYear) {
      const parts = extractDateParts(row[dateField]);
      matchDate =
        !!parts &&
        parts.month === selectedMonth &&
        parts.day === selectedDay &&
        parts.year === selectedYear;
    }

    const matchLine =
      !showLineFilter || lineFilter === "All Lines" || row.line === lineFilter;

    return matchSearch && matchDate && matchLine;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  // Policy's importer default depends on which line sub-filter is active,
  // rather than a single static entry in IMPORT_TARGET_BY_TYPE.
  const uploadTarget = type === "Policy"
    ? (isMotorLine ? "motor" : "fire-property")
    : (IMPORT_TARGET_BY_TYPE[type] || "policyholders");

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem="Policy Holder Information" />
      </div>

      <div className="flex-1 flex flex-col gap-4 min-w-0">

        {/* Stat Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {displayStatCards.map((c) => (
            <div key={c.label}
              onClick={() => handleTypeChange(c.type)}
              className={`bg-white rounded-2xl px-4 py-4 shadow-sm flex flex-col justify-between min-h-[100px] cursor-pointer transition hover:shadow-md
                ${type === c.type ? "border-2 border-black" : "border-2 border-transparent"}`}>
              <p className="text-gray-500 text-xs">{c.label}</p>
              <p className="text-black font-black text-3xl sm:text-4xl leading-none mt-2">{c.value}</p>
            </div>
          ))}
        </div>

        {/* Table Card */}
        <div className="bg-white rounded-2xl p-5 shadow-sm flex flex-col flex-1">

          {/* Toolbar */}
          <div className="flex flex-wrap gap-2 mb-4 items-center">
            <button onClick={() => setUploadOpen(true)}
              className="flex items-center gap-1.5 bg-white border border-gray-200 rounded-xl px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition"
              title="Upload file">
              <Upload className="w-3.5 h-3.5 text-gray-500" />
            </button>
            <button onClick={() => setNeedsReviewOpen(true)}
              className="flex items-center gap-1.5 bg-white border border-gray-200 rounded-xl px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition"
              title="Import rows needing review">
              Needs Review
              {!needsReviewLoading && needsReviewRecords.length > 0 && (
                <span className="bg-red-500 text-white rounded-full text-[10px] leading-none px-1.5 py-0.5">
                  {needsReviewRecords.length}
                </span>
              )}
            </button>
            <Dropdown label="Type" options={TYPE_OPTIONS} value={type} onChange={handleTypeChange} />

            {showLineFilter && (
              <Dropdown
                label="Insurance Line"
                options={LINE_OPTIONS}
                value={lineFilter}
                onChange={(v) => { setLineFilter(v); setPage(1); }}
              />
            )}

            {showPolicyLineFilter && (
              <Dropdown
                label="Insurance Line"
                options={POLICY_LINE_OPTIONS}
                value={policyLine}
                onChange={(v) => { setPolicyLine(v); setPage(1); }}
              />
            )}

            {/* Month filter — */}

            {DATE_FIELD_MAP[type] !== null && (
              <FullCalendarPicker
                value={fromDate}
                onChange={(date) => { setFromDate(date); setPage(1); }}
              />

            )}


            <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
              <Search className="w-3.5 h-3.5 text-gray-400" />
              <input className="text-xs outline-none text-gray-600 w-36"
                placeholder={`Search ${type}...`}
                value={search}
                onChange={e => handleSearch(e.target.value)} />
            </div>
            {search && (
              <span className="text-xs text-gray-400">{filtered.length} result{filtered.length !== 1 ? "s" : ""}</span>
            )}

          </div>

          {/* Dynamic Table */}
          <div className="overflow-x-auto flex-1">
            {LOADING_MAP[type]
              ? <p className="text-center py-8 text-gray-400 text-xs">Loading {type.toLowerCase()}...</p>
              : ERROR_MAP[type]
              ? <p className="text-center py-8 text-red-400 text-xs">{ERROR_MAP[type]}</p>
              : pageRows.length === 0
              ? <p className="text-center py-8 text-gray-400 text-xs">No records found.</p>
              : <>
                {type === "Policy" && (
                  <GenericPolicyTable columns={policyColumns} rows={pageRows} onDelete={deletePolicyForLine} />
                )}
                {type === "Quotation" && <QuotationTable rows={pageRows} />}
                {type === "Claims" && <ClaimsTable rows={pageRows} />}
                {type === "Client Information" && <ClientTable rows={pageRows} onDelete={deletePolicyholder} />}
                {type === "Survey Report" && <SurveyTable rows={pageRows} />}
                {type === "Vehicle Information" && <VehicleTable rows={pageRows} />}
              </>
            }
          </div>

          {/* Pagination */}
          <div className="flex justify-end items-center gap-2 mt-auto pt-4 text-xs text-gray-500">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={safePage === 1} className="disabled:opacity-30">«</button>
            <span>{safePage} / {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="disabled:opacity-30">»</button>
          </div>
        </div>
      </div>

      <UploadModal
        key={uploadTarget}
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadSuccess={refreshAllData}
        defaultTarget={uploadTarget}
      />
      <NeedsReviewModal
        isOpen={needsReviewOpen}
        onClose={() => setNeedsReviewOpen(false)}
        records={needsReviewRecords}
        loading={needsReviewLoading}
        policyholders={clientRecords}
        onResolved={refreshClientData}
      />
    </div>
  );
}