import { useState } from "react";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { ChevronDown, Search } from "lucide-react";
import Sidebar from "../components/sidebar";
import { FullCalendarPicker } from "../components/DatePicker";

const chartData = [
  { month: "Oct", filed: 8, fraud: 0 },
  { month: "Nov", filed: 9, fraud: 0.5 },
  { month: "Dec", filed: 7, fraud: 1 },
  { month: "Jan", filed: 8, fraud: 2 },
  { month: "Feb", filed: 6, fraud: 3 },
  { month: "March", filed: 10, fraud: 4 },
];
const pieData = [{ name: "Motor & Car", value: 3 }, { name: "Fire & Property", value: 1 }];
const PIE_COLORS = ["#b91c1c", "#ef4444"];

const ALL_CLAIMS = [
  // March 2026
  { month: "March 2026", claim: "CLM-2001", policy: "POL-1001", client: "Juan Dela Cruz", loss: "03/10/2026", reported: "03/11/2026", line: "Motor Car", type: "Collision", reserve: "₱45,000", paid: "₱45,000", status: "Paid", fraud: "No" },
  { month: "March 2026", claim: "CLM-2002", policy: "POL-1002", client: "Maria Santos", loss: "03/10/2026", reported: "03/11/2026", line: "Motor Car", type: "Theft", reserve: "₱1,200,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { month: "March 2026", claim: "CLM-2003", policy: "POL-1003", client: "Emily Fernandez", loss: "03/10/2026", reported: "03/11/2026", line: "Fire & Property", type: "Fire", reserve: "₱2,500,000", paid: "₱0", status: "Approved", fraud: "No" },
  { month: "March 2026", claim: "CLM-2004", policy: "POL-1004", client: "Juan Dela Cruz", loss: "03/10/2026", reported: "03/11/2026", line: "Motor Car", type: "Own Damage", reserve: "₱28,000", paid: "₱28,000", status: "Paid", fraud: "No" },
  { month: "March 2026", claim: "CLM-2005", policy: "POL-1005", client: "Dennis Reyes", loss: "03/10/2026", reported: "03/11/2026", line: "Fire & Property", type: "Typhoon Damage", reserve: "₱3,500,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { month: "March 2026", claim: "CLM-2006", policy: "POL-1006", client: "Lina Mercado", loss: "03/10/2026", reported: "03/11/2026", line: "Motor Car", type: "Accident", reserve: "₱45,000", paid: "₱45,000", status: "Paid", fraud: "No" },
  { month: "March 2026", claim: "CLM-2007", policy: "POL-1007", client: "Sofia Ramirez", loss: "03/12/2026", reported: "03/13/2026", line: "Fire & Property", type: "Fire", reserve: "₱1,800,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { month: "March 2026", claim: "CLM-2008", policy: "POL-1008", client: "Ricardo Santiago", loss: "03/14/2026", reported: "03/15/2026", line: "Motor Car", type: "Collision", reserve: "₱65,000", paid: "₱65,000", status: "Paid", fraud: "No" },
  // February 2026
  { month: "February 2026", claim: "CLM-2009", policy: "POL-1009", client: "Carmen Flores", loss: "02/16/2026", reported: "02/17/2026", line: "Fire & Property", type: "Flood", reserve: "₱900,000", paid: "₱0", status: "Approved", fraud: "No" },
  { month: "February 2026", claim: "CLM-2010", policy: "POL-1010", client: "Miguel Torres", loss: "02/18/2026", reported: "02/19/2026", line: "Motor Car", type: "Theft", reserve: "₱780,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { month: "February 2026", claim: "CLM-2011", policy: "POL-1011", client: "Elena Cruz", loss: "02/20/2026", reported: "02/21/2026", line: "Fire & Property", type: "Earthquake", reserve: "₱2,100,000", paid: "₱0", status: "Reported", fraud: "No" },
  { month: "February 2026", claim: "CLM-2012", policy: "POL-1012", client: "Leonor Rivera", loss: "02/22/2026", reported: "02/23/2026", line: "Motor Car", type: "Own Damage", reserve: "₱32,000", paid: "₱30,000", status: "Paid", fraud: "No" },
  // January 2026
  { month: "January 2026", claim: "CLM-2013", policy: "POL-1013", client: "Antonio Reyes", loss: "01/05/2026", reported: "01/06/2026", line: "Motor Car", type: "Collision", reserve: "₱55,000", paid: "₱55,000", status: "Paid", fraud: "No" },
  { month: "January 2026", claim: "CLM-2014", policy: "POL-1014", client: "Roberto Gomez", loss: "01/10/2026", reported: "01/11/2026", line: "Fire & Property", type: "Fire", reserve: "₱3,000,000", paid: "₱0", status: "Investigating", fraud: "Yes" },
  { month: "January 2026", claim: "CLM-2015", policy: "POL-1015", client: "Manuel Chua", loss: "01/18/2026", reported: "01/19/2026", line: "Motor Car", type: "Theft", reserve: "₱950,000", paid: "₱0", status: "Approved", fraud: "No" },
];

const PAGE_SIZE = 6;

function Dropdown({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap">
        {value || label} <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && options && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[150px]">
          {options.map(opt => (
            <button key={opt} onClick={() => { onChange?.(opt); setOpen(false); }}
              className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${(value || label) === opt ? "font-bold text-black" : "text-gray-600"}`}>
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ value, label }) {
  return (
    <div className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
      <p className="text-gray-400 text-xs">As of March 2026</p>
      <p className="text-black font-black text-5xl leading-none my-2">{value}</p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  );
}

export default function Claims() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [fromDate, setFromDate] = useState(null);
  const [lineFilter, setLine] = useState("Policy Line: All");
  const [fraudFilter, setFraud] = useState("Fraud Flag: All");

  const selectedMonth = fromDate ? fromDate.getMonth() + 1 : null;
  const selectedDay = fromDate ? fromDate.getDate() : null;
  const selectedYear = fromDate ? fromDate.getFullYear() : null;

  const filtered = ALL_CLAIMS.filter(r => {
    const matchLine = lineFilter === "Policy Line: All" || r.line === lineFilter;
    const matchFraud = fraudFilter === "Fraud Flag: All" || r.fraud === fraudFilter;
    const matchSearch = r.policy.toLowerCase().includes(search.toLowerCase()) ||
      r.client.toLowerCase().includes(search.toLowerCase());

    let matchDate = true;
    if (fromDate && r.loss) {
      const [mm, dd, yyyy] = r.loss.split("/").map(Number);
      matchDate = mm === selectedMonth && dd === selectedDay && yyyy === selectedYear;
    }

    return matchLine && matchFraud && matchSearch && matchDate;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const handleFilterChange = (setter) => (val) => { setter(val); setPage(1); };

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0"><Sidebar activeItem="Claims" /></div>
      <div className="flex-1 flex flex-col gap-4 min-w-0">

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard value="15" label="Total Claims" />
          <StatCard value="4" label="Fraud Flagged Claims" />
          <StatCard value="4" label="Approved Claims" />
          <StatCard value="4" label="Paid Claims" />
        </div>

        <div className="flex gap-4">
          <div className="flex-1 flex flex-col justify-center bg-white rounded-2xl p-5 shadow-sm min-w-0">
            <h2 className="font-bold text-black text-sm mb-4">
              Total Filed Claims vs. Fraud Flag Trend{" "}
              <span className="text-gray-400 font-normal">(Past 6 Months)</span>
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={chartData}>
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} domain={[0, 10]}
                  label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} formatter={v => v === "filed" ? "Filed Claims" : "Flagged Fraud Claims"} />
                <Bar dataKey="filed" name="filed" fill="#a5b4fc" radius={[4, 4, 0, 0]}
                  label={{ position: "center", fontSize: 10, fill: "#fff", fontWeight: 700 }} />
                <Line dataKey="fraud" name="fraud" stroke="#f87171" strokeWidth={2} dot={{ r: 4, fill: "#f87171" }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <div className="bg-white rounded-2xl p-4 shadow-sm flex-1">
              <h2 className="font-bold text-black text-sm text-center mb-1">Pending Flagged Fraud Claims</h2>
              <p className="text-gray-400 text-[10px] text-center mb-2">(As of March 2026)</p>
              <ResponsiveContainer width="100%" height={150}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={60} labelLine={false}
                    label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                      const RADIAN = Math.PI / 180;
                      const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                      return <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)}
                        fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={13} fontWeight={700}>{value}</text>;
                    }}>
                    {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-1.5 mt-2">
                {pieData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: PIE_COLORS[i] }} />
                    <span className="text-xs text-gray-600">{d.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-2xl p-4 shadow-sm">
              <p className="text-black font-bold text-sm">Fraud Flag Rate</p>
              <p className="text-gray-400 text-[10px]">As of March 2026</p>
              <p className="text-black font-black text-4xl mt-2">40.0%</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <div className="flex flex-wrap gap-2 mb-4 items-center">
            <FullCalendarPicker
              value={fromDate}
              onChange={(date) => { setFromDate(date); setPage(1); }}
            />
            <Dropdown label="Policy Line: All" options={["Policy Line: All", "Motor Car", "Fire & Property"]} value={lineFilter} onChange={handleFilterChange(setLine)} />
            <Dropdown label="Fraud Flag: All" options={["Fraud Flag: All", "Yes", "No"]} value={fraudFilter} onChange={handleFilterChange(setFraud)} />
            <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
              <Search className="w-3.5 h-3.5 text-gray-400" />
              <input className="text-xs outline-none text-gray-600 w-36" placeholder="Search Policy Number"
                value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} />
            </div>
            {fromDate && (
              <span className="text-xs text-gray-400">{filtered.length} result{filtered.length !== 1 ? "s" : ""}</span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-center">
              <thead>
                <tr className="border-b border-gray-100">
                  {["Claim Number", "Policy Number", "Client Name", "Date of Loss", "Date Reported", "Policy Line", "Claim Type", "Reserve Amount", "Paid Amount", "Status", "Fraud Flag"].map(h => (
                    <th key={h} className="py-2 px-1.5 text-gray-500 font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
                    <td className="py-2.5 px-1.5">{r.claim}</td>
                    <td className="py-2.5 px-1.5">{r.policy}</td>
                    <td className="py-2.5 px-1.5">{r.client}</td>
                    <td className="py-2.5 px-1.5">{r.loss}</td>
                    <td className="py-2.5 px-1.5">{r.reported}</td>
                    <td className="py-2.5 px-1.5">{r.line}</td>
                    <td className="py-2.5 px-1.5">{r.type}</td>
                    <td className="py-2.5 px-1.5">{r.reserve}</td>
                    <td className="py-2.5 px-1.5">{r.paid}</td>
                    <td className="py-2.5 px-1.5">{r.status}</td>
                    <td className="py-2.5 px-1.5">
                      <span className={`font-semibold ${r.fraud === "Yes" ? "text-red-500" : "text-gray-500"}`}>{r.fraud}</span>
                    </td>
                  </tr>
                ))}
                {pageRows.length === 0 && (
                  <tr><td colSpan={11} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end items-center gap-2 mt-3 text-xs text-gray-500">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={safePage === 1} className="disabled:opacity-30">«</button>
            <span>{safePage} / {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="disabled:opacity-30">»</button>
          </div>
        </div>
      </div>
    </div>
  );
}