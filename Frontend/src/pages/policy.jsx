import { useState, useEffect, useCallback } from "react";
import { ChevronDown, Search, Upload, Trash2 } from "lucide-react";
import axios from "axios";
import Sidebar from "../components/sidebar";
import UploadModal from "../components/UploadFileModal";
import NeedsReviewModal from "../components/NeedsReviewModal";
import { FullCalendarPicker } from "../components/DatePicker";

const API_BASE_URL = "http://127.0.0.1:8000";

// ── Stat Cards
const statCards = [
  { label: "Total Policies", value: null }, // filled in dynamically at render time
  { label: "Total Quotation", value: null },
  { label: "Total Claims", value: "421" },
  { label: "Total Client Information", value: null },
  { label: "Total Survey Report", value: null },
];

const TYPE_OPTIONS = ["Policy", "Quotation", "Claims", "Client Information", "Survey Report"];
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
function PolicyTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Policy Number", "Client Name", "Policy Line", "Issued Date", "Expiry Date", "Premium", "Sum Insured", "Status"].map(h =>
          <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-3">{r.policy}</td><td className="py-3 px-3">{r.client}</td>
          <td className="py-3 px-3">{r.line}</td><td className="py-3 px-3">{r.issued}</td>
          <td className="py-3 px-3">{r.expiry}</td><td className="py-3 px-3">{r.premium}</td>
          <td className="py-3 px-3">{r.sum}</td><td className="py-3 px-3">{r.status}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function QuotationTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Quote Number", "Quote Date", "Client Name", "Policy Line", "Premium", "Sum Insured", "Period Cover", "Converted Policy No."].map(h =>
          <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-3">{r.quote}</td><td className="py-3 px-3">{r.date}</td>
          <td className="py-3 px-3">{r.client}</td><td className="py-3 px-3">{r.line}</td>
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

function ClientTable({ rows, onDelete }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Client ID", "Client Name", "Sex", "Contact Number", "Email Address", "Address", ""].map(h =>
          <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-3">{r.id}</td><td className="py-3 px-3">{r.client}</td>
          <td className="py-3 px-3">{r.sex}</td>
          <td className="py-3 px-3">{r.contact}</td>
          <td className="py-3 px-3 text-blue-500">{r.email}</td>
          <td className="py-3 px-3 text-left max-w-[180px]">{r.address}</td>
          <td className="py-3 px-3">
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

function SurveyTable({ rows }) {
  return (
    <table className="w-full text-xs text-center">
      <thead><tr className="border-b border-gray-100">
        {["Survey ID", "Client Name", "Survey Date", "Location of Risk", "Risk Class", "Zone", "Max. Amount Subject", "Loss Record", "Flood Risk"].map(h =>
          <th key={h} className="py-3 px-2 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-2">{r.id}</td>
          <td className="py-3 px-2">{r.client}</td><td className="py-3 px-2">{r.date}</td>
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

// ── Page ──────────────────────────────────────────────────────────────────────

// Map each table type to the date field used for month filtering
const DATE_FIELD_MAP = {
  "Policy": "issued",
  "Quotation": "date",
  "Claims": "loss",
  "Survey Report": "date",
  "Client Information": null, // no date field — month filter doesn't apply
};

// Which bulk importer the Upload button should default to for the active tab.
// The user can still switch it inside the modal — Policy/Quotation mix data
// from both lines, so there's no single correct guess for those.
const IMPORT_TARGET_BY_TYPE = {
  "Client Information": "policyholders",
  "Survey Report": "fire-property",
  "Policy": "motor",
  "Quotation": "motor",
  "Claims": "policyholders",
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
      const transformed = response.data.map((p) => ({
        id: p.id,
        client: [p.first_name, p.middle_name, p.last_name].filter(Boolean).join(" "),
        sex: p.gender || "",
        contact: p.mobile_number || "",
        email: p.email_address || "",
        address: p.present_address || "",
      }));
      setClientRecords(transformed);
    } catch (err) {
      setClientError("Failed to load client information.");
    } finally {
      setClientLoading(false);
    }
  }, []);

  const [policyRecords, setPolicyRecords] = useState([]);
  const [policyLoading, setPolicyLoading] = useState(true);
  const [policyError, setPolicyError] = useState(null);

  const fetchPolicies = useCallback(async () => {
    setPolicyLoading(true);
    setPolicyError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [fpRes, motorRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/fire-property/policies`, { headers }),
        axios.get(`${API_BASE_URL}/motor/policies`, { headers }),
      ]);
      const toRow = (p, line) => ({
        policy: p.policy_no || "—",
        client: p.insured_name_address || "—",
        line,
        issued: formatDate(p.issue_date),
        expiry: formatDate(p.period_to),
        premium: formatCurrency(p.total_amount_due),
        sum: line === "Fire & Property" ? formatCurrency(p.sum_insured) : "—",
        status: p.renewing_policy_no ? "Renewed" : "New",
      });
      setPolicyRecords([
        ...fpRes.data.map((p) => toRow(p, "Fire & Property")),
        ...motorRes.data.map((p) => toRow(p, "Motor Car")),
      ]);
    } catch (err) {
      setPolicyError("Failed to load policies.");
    } finally {
      setPolicyLoading(false);
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
      const [fpQRes, motorQRes, fpPRes, motorPRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/fire-property/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/motor/quotations`, { headers }),
        axios.get(`${API_BASE_URL}/fire-property/policies`, { headers }),
        axios.get(`${API_BASE_URL}/motor/policies`, { headers }),
      ]);
      const fpPolicyByQuotation = new Map(fpPRes.data.map((p) => [p.quotation_id, p.policy_no || "—"]));
      const motorPolicyByQuotation = new Map(motorPRes.data.map((p) => [p.quotation_id, p.policy_no || "—"]));

      const fp = fpQRes.data.map((q) => ({
        quote: `FP-Q-${q.id}`,
        date: formatDate(q.quotation_date),
        client: q.insured_name || "—",
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
      const response = await axios.get(`${API_BASE_URL}/fire-property/surveys`, { headers });
      const transformed = response.data.map((s) => ({
        id: `SURV-${s.id}`,
        client: s.name_of_insured || "—",
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
    fetchPolicies();
    fetchQuotations();
    fetchSurveys();
  }, [fetchClients, fetchNeedsReview, fetchPolicies, fetchQuotations, fetchSurveys]);

  const deletePolicyholder = useCallback(async (row) => {
    if (!window.confirm(`Delete client "${row.client}"? This moves the record to the deleted archive.`)) return;
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

  useEffect(() => {
    fetchClients();
    fetchNeedsReview();
    fetchPolicies();
    fetchQuotations();
    fetchSurveys();
  }, [fetchClients, fetchNeedsReview, fetchPolicies, fetchQuotations, fetchSurveys]);

  const DATA_MAP = {
    "Policy": policyRecords,
    "Quotation": quotationRecords,
    "Claims": claimsData,
    "Client Information": clientRecords,
    "Survey Report": surveyRecords,
  };

  const LOADING_MAP = {
    "Policy": policyLoading,
    "Quotation": quotationLoading,
    "Claims": false,
    "Client Information": clientLoading,
    "Survey Report": surveyLoading,
  };

  const ERROR_MAP = {
    "Policy": policyError,
    "Quotation": quotationError,
    "Claims": null,
    "Client Information": clientError,
    "Survey Report": surveyError,
  };

  const displayStatCards = statCards.map((c) => {
    if (c.label === "Total Client Information") return { ...c, value: clientLoading ? "…" : String(clientRecords.length) };
    if (c.label === "Total Policies") return { ...c, value: policyLoading ? "…" : String(policyRecords.length) };
    if (c.label === "Total Quotation") return { ...c, value: quotationLoading ? "…" : String(quotationRecords.length) };
    if (c.label === "Total Survey Report") return { ...c, value: surveyLoading ? "…" : String(surveyRecords.length) };
    return c;
  });

  const handleTypeChange = (t) => { setType(t); setPage(1); setSearch(""); };
  const handleSearch = (v) => { setSearch(v); setPage(1); };

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
      const [mm, dd, yyyy] = row[dateField].split("/").map(Number);
      matchDate =
        mm === selectedMonth &&
        dd === selectedDay &&
        yyyy === selectedYear;
    }

    return matchSearch && matchDate;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem="Policy Holder Information" />
      </div>

      <div className="flex-1 flex flex-col gap-4 min-w-0">

        {/* Stat Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {displayStatCards.map((c, i) => (
            <div key={c.label}
              onClick={() => handleTypeChange(TYPE_OPTIONS[i])}
              className={`bg-white rounded-2xl px-4 py-4 shadow-sm flex flex-col justify-between min-h-[100px] cursor-pointer transition hover:shadow-md
                ${type === TYPE_OPTIONS[i] ? "border-2 border-black" : "border-2 border-transparent"}`}>
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
                {type === "Policy" && <PolicyTable rows={pageRows} />}
                {type === "Quotation" && <QuotationTable rows={pageRows} />}
                {type === "Claims" && <ClaimsTable rows={pageRows} />}
                {type === "Client Information" && <ClientTable rows={pageRows} onDelete={deletePolicyholder} />}
                {type === "Survey Report" && <SurveyTable rows={pageRows} />}
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
        key={IMPORT_TARGET_BY_TYPE[type] || "policyholders"}
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadSuccess={refreshAllData}
        defaultTarget={IMPORT_TARGET_BY_TYPE[type] || "policyholders"}
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