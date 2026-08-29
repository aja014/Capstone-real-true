import { useState, useEffect, useCallback } from "react";
import { ChevronDown, Search, Upload, FileText, Trash2 } from "lucide-react";
import axios from "axios";
import Sidebar from "../components/sidebar";
import UploadModal from "../components/UploadFileModal";
import NeedsReviewModal from "../components/NeedsReviewModal";
import { FullCalendarPicker } from "../components/DatePicker";
import ImageForSurveyTable from "../img/Background_Cars.jpg"

const API_BASE_URL = "http://127.0.0.1:8000";

// ── Stat Cards
const statCards = [
  { label: "Total Policies", value: "731" },
  { label: "Total Quotation", value: "934" },
  { label: "Total Claims", value: "421" },
  { label: "Total Client Information", value: null }, // filled in dynamically at render time
  { label: "Total Survey Report", value: "1011" },
];

const TYPE_OPTIONS = ["Policy", "Quotation", "Claims", "Client Information", "Survey Report"];
const PAGE_SIZE = 8;

// ── Datasets (enough for 2+ pages each) 
const policyData = [
  { policy: "POL-1001", client: "Juan Dela Cruz", line: "Motor Car", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "New" },
  { policy: "POL-1002", client: "Maria Santos", line: "Motor Car", issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "Renewed" },
  { policy: "POL-1003", client: "Emily Fernandez", line: "Fire & Property", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "New" },
  { policy: "POL-1004", client: "Dennis Reyes", line: "Motor Car", issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "New" },
  { policy: "POL-1005", client: "Lina Mercado", line: "Fire & Property", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "Renewed" },
  { policy: "POL-1006", client: "Roberto Gomez", line: "Fire & Property", issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "Renewed" },
  { policy: "POL-1007", client: "Antonio Reyes", line: "Fire & Property", issued: "01/15/2026", expiry: "01/15/2027", premium: "₱2,500", sum: "₱850,000", status: "New" },
  { policy: "POL-1008", client: "Manuel Chua", line: "Motor Car", issued: "02/01/2026", expiry: "01/15/2027", premium: "₱1,500", sum: "₱480,000", status: "Renewed" },
  { policy: "POL-1009", client: "Teresa Villanueva", line: "Fire & Property", issued: "02/01/2026", expiry: "01/15/2027", premium: "₱6,500", sum: "₱580,000", status: "New" },
  { policy: "POL-1010", client: "Sofia Ramirez", line: "Motor Car", issued: "01/20/2026", expiry: "01/20/2027", premium: "₱3,200", sum: "₱720,000", status: "Renewed" },
  { policy: "POL-1011", client: "Ricardo Santiago", line: "Fire & Property", issued: "02/05/2026", expiry: "02/05/2027", premium: "₱4,000", sum: "₱950,000", status: "New" },
  { policy: "POL-1012", client: "Carmen Flores", line: "Motor Car", issued: "01/25/2026", expiry: "01/25/2027", premium: "₱2,800", sum: "₱660,000", status: "New" },
  { policy: "POL-1013", client: "Miguel Torres", line: "Fire & Property", issued: "02/10/2026", expiry: "02/10/2027", premium: "₱3,500", sum: "₱880,000", status: "Renewed" },
  { policy: "POL-1014", client: "Elena Cruz", line: "Motor Car", issued: "01/30/2026", expiry: "01/30/2027", premium: "₱1,800", sum: "₱510,000", status: "New" },
  { policy: "POL-1015", client: "Jose Rizal", line: "Fire & Property", issued: "02/15/2026", expiry: "02/15/2027", premium: "₱5,000", sum: "₱1,100,000", status: "Renewed" },
  { policy: "POL-1016", client: "Leonor Rivera", line: "Motor Car", issued: "01/12/2026", expiry: "01/12/2027", premium: "₱2,200", sum: "₱590,000", status: "New" },
];

const quotationData = [
  { quote: "Q-2026-001", date: "01/05/2026", client: "Ricardo Santiago", line: "Motor Car", premium: "₱21,500", sum: "₱980,000", expiry: "02/04/2026", converted: "POL-1012" },
  { quote: "Q-2026-002", date: "01/12/2026", client: "Sofia Ramirez", line: "Fire & Property", premium: "₱55,000", sum: "₱6,500,000", expiry: "02/11/2026", converted: "POL-1013" },
  { quote: "Q-2026-003", date: "01/20/2026", client: "Miguel Torres", line: "Motor Car", premium: "₱18,200", sum: "₱750,000", expiry: "02/19/2026", converted: "—" },
  { quote: "Q-2026-004", date: "02/01/2026", client: "Carmen Flores", line: "Motor Car", premium: "₱72,500", sum: "₱9,000,000", expiry: "03/03/2026", converted: "POL-1014" },
  { quote: "Q-2026-005", date: "02/10/2026", client: "Jose Rizal", line: "Fire & Property", premium: "₱25,800", sum: "₱1,350,000", expiry: "03/12/2026", converted: "—" },
  { quote: "Q-2026-006", date: "02/18/2026", client: "Elena Cruz", line: "Fire & Property", premium: "₱58,000", sum: "₱4,500,000", expiry: "03/20/2026", converted: "POL-1015" },
  { quote: "Q-2026-007", date: "02/25/2026", client: "Andres Bonifacio", line: "Motor Car", premium: "₱16,500", sum: "₱620,000", expiry: "03/27/2026", converted: "—" },
  { quote: "Q-2026-008", date: "03/02/2026", client: "Leonor Rivera", line: "Fire & Property", premium: "₱48,500", sum: "₱5,200,000", expiry: "04/01/2026", converted: "POL-1016" },
  { quote: "Q-2026-009", date: "03/10/2026", client: "Gregorio Del Pilar", line: "Motor Car", premium: "₱22,900", sum: "₱7,800,000", expiry: "04/09/2026", converted: "—" },
  { quote: "Q-2026-010", date: "03/15/2026", client: "Melchora Aquino", line: "Fire & Property", premium: "₱31,000", sum: "₱2,100,000", expiry: "04/14/2026", converted: "POL-1017" },
  { quote: "Q-2026-011", date: "03/18/2026", client: "Diego Santos", line: "Motor Car", premium: "₱19,400", sum: "₱840,000", expiry: "04/17/2026", converted: "—" },
  { quote: "Q-2026-012", date: "03/22/2026", client: "Ana Reyes", line: "Fire & Property", premium: "₱44,000", sum: "₱3,600,000", expiry: "04/21/2026", converted: "POL-1018" },
  { quote: "Q-2026-013", date: "03/25/2026", client: "Pedro Gomez", line: "Motor Car", premium: "₱17,800", sum: "₱700,000", expiry: "04/24/2026", converted: "—" },
  { quote: "Q-2026-014", date: "03/28/2026", client: "Luisa Mercado", line: "Fire & Property", premium: "₱62,000", sum: "₱5,800,000", expiry: "04/27/2026", converted: "—" },
];

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

const surveyData = [
  { id: "SURV-001", policy: "POL-1001", client: "Juan Dela Cruz", date: "01/10/2026", propType: "Motor Vehicle", location: "123 Rizal St., Malolos City", grade: "Low", findings: "Vehicle in good c...", reco: "Regular mainte...", photo: ImageForSurveyTable },
  { id: "SURV-002", policy: "POL-1002", client: "Maria Santos", date: "01/25/2026", propType: "Motor Vehicle", location: "45 Mabini St., Baliuag", grade: "Moderate", findings: "Minor scratches...", reco: "Secure accessori...", photo: ImageForSurveyTable },
  { id: "SURV-003", policy: "POL-1003", client: "Roberto Gomez", date: "01/05/2026", propType: "Commercial Building", location: "78 Purok 3, Malolos City", grade: "Moderate", findings: "Electrical wiring nee...", reco: "Update electrical s...", photo: ImageForSurveyTable },
  { id: "SURV-004", policy: "POL-1004", client: "Antonio Reyes", date: "02/28/2026", propType: "Commercial Truck", location: "56 Burgos St., Santa Maria", grade: "High", findings: "Heavy wear on tires...", reco: "Replace tires, insta...", photo: ImageForSurveyTable },
  { id: "SURV-005", policy: "POL-1007", client: "Dennis Reyes", date: "02/10/2026", propType: "Motor Vehicle", location: "89 Rizal Ave., Malolos City", grade: "Low", findings: "Well-maintaine...", reco: "No major recomme...", photo: ImageForSurveyTable },
  { id: "SURV-006", policy: "POL-1008", client: "Gregorio Fernandez", date: "01/15/2026", propType: "Residential Property", location: "34 M.H. Del Pilar St., San Jose...", grade: "Low", findings: "Concrete structure, f...", reco: "Annual fire drill practi...", photo: ImageForSurveyTable },
  { id: "SURV-007", policy: "POL-1010", client: "Manuel Chua", date: "02/20/2026", propType: "Motor Vehicle", location: "67 Purok 2, Plaridel", grade: "High", findings: "Multiple units with ...", reco: "Schedule regular m...", photo: ImageForSurveyTable },
  { id: "SURV-008", policy: "POL-1012", client: "Ricardo Santiago", date: "03/01/2026", propType: "Motor Vehicle", location: "22 F. Torres St., Meycauayan", grade: "Low", findings: "Brand new vehicle...", reco: "No recomme...", photo: ImageForSurveyTable },
  { id: "SURV-009", policy: "POL-1014", client: "Carmen Flores", date: "03/05/2026", propType: "Warehouse", location: "12 Purok 5, Marilao", grade: "High", findings: "Flammable materials...", reco: "Implement proper sto...", photo: ImageForSurveyTable },
  { id: "SURV-010", policy: "POL-1005", client: "Lina Mercado", date: "03/08/2026", propType: "Residential Property", location: "45 Purok 3, San Jose del Monte", grade: "Low", findings: "Well-kept property...", reco: "No changes needed...", photo: ImageForSurveyTable },
  { id: "SURV-011", policy: "POL-1006", client: "Roberto Gomez", date: "03/12/2026", propType: "Commercial Building", location: "78 Purok 1, Malolos City", grade: "Moderate", findings: "Minor facade issues...", reco: "Repaint exterior...", photo: ImageForSurveyTable },
  { id: "SURV-012", policy: "POL-1015", client: "Elena Cruz", date: "03/15/2026", propType: "Motor Vehicle", location: "56 Burgos St., Santa Maria", grade: "Low", findings: "Good overall cond...", reco: "Routine check...", photo: ImageForSurveyTable },
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

function RiskBadge({ grade }) {
  const colors = { Low: "text-green-600 bg-green-50", Moderate: "text-yellow-700 bg-yellow-50", High: "text-red-600 bg-red-50" };
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${colors[grade] || ""}`}>{grade}</span>;
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
        {["Quote Number", "Quote Date", "Client Name", "Policy Line", "Premium", "Sum Insured", "Expiry Date", "Converted Policy No."].map(h =>
          <th key={h} className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-3">{r.quote}</td><td className="py-3 px-3">{r.date}</td>
          <td className="py-3 px-3">{r.client}</td><td className="py-3 px-3">{r.line}</td>
          <td className="py-3 px-3">{r.premium}</td><td className="py-3 px-3">{r.sum}</td>
          <td className="py-3 px-3">{r.expiry}</td>
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
        {["Survey ID", "Policy Number", "Client Name", "Survey Date", "Property Type", "Location", "Risk Grade", "Findings Summary", "Recommendations", "Photo"].map(h =>
          <th key={h} className="py-3 px-2 text-gray-700 font-bold whitespace-nowrap">{h}</th>)}
      </tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
          <td className="py-3 px-2">{r.id}</td><td className="py-3 px-2">{r.policy}</td>
          <td className="py-3 px-2">{r.client}</td><td className="py-3 px-2">{r.date}</td>
          <td className="py-3 px-2">{r.propType}</td>
          <td className="py-3 px-2 text-left max-w-[120px] text-gray-600">{r.location}</td>
          <td className="py-3 px-2"><RiskBadge grade={r.grade} /></td>
          <td className="py-3 px-2 text-left max-w-[100px]">{r.findings}</td>
          <td className="py-3 px-2 text-left max-w-[100px]">{r.reco}</td>
          <td className="py-3 px-2">
            {r.photo && (
              <a
                href={r.photo}
                target="_blank"
                rel="noopener noreferrer"
                className="flex justify-center"
              >
                <FileText className="w-4 h-4 text-gray-500 hover:text-yellow-500 cursor-pointer" />
              </a>
            )}
          </td>        </tr>
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
  // const [month, setMonth] = useState("March 2026");
  const [year, setYear] = useState(2026);
  const handleMonthChange = (m) => { setMonth(m); setPage(1); };

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
  }, [fetchClients, fetchNeedsReview]);

  const DATA_MAP = {
    "Policy": policyData,
    "Quotation": quotationData,
    "Claims": claimsData,
    "Client Information": clientRecords,
    "Survey Report": surveyData,
  };

  const displayStatCards = statCards.map((c) =>
    c.label === "Total Client Information"
      ? { ...c, value: clientLoading ? "…" : String(clientRecords.length) }
      : c
  );

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
            {type === "Client Information" && clientLoading
              ? <p className="text-center py-8 text-gray-400 text-xs">Loading client information...</p>
              : type === "Client Information" && clientError
              ? <p className="text-center py-8 text-red-400 text-xs">{clientError}</p>
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

      <UploadModal isOpen={uploadOpen} onClose={() => setUploadOpen(false)} onUploadSuccess={refreshClientData} />
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