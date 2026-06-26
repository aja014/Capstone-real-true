import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { ChevronDown, Search } from "lucide-react";
import Sidebar from "../components/sidebar";
import { MonthYearPicker } from "../components/DatePicker";

const BAR_DATA_BY_PERIOD = {
  "YTD": [
    { month: "2024",  renewed: 142, lost: 85 },
    { month: "2025", renewed: 116, lost: 96 },
    { month: "2026",    renewed: 124,  lost: 56,  pending: 15 },
  ],
  "MTD": [
    { month: "January", renewed: 6, lost: 6, pending: 5 },
    { month: "February", renewed: 10, lost: 2, pending: 5 },
    { month: "March", renewed: 3, lost: 6, pending: 6 },
  ],
  "Daily": [
    { month: "Mar 20", renewed: 1, lost: 2, pending: 1 },
    { month: "Mar 21", renewed: 0, lost: 1, pending: 2 },
    { month: "Mar 22", renewed: 2, lost: 1, pending: 0 },
    { month: "Mar 23", renewed: 1, lost: 2, pending: 1 },
    { month: "Mar 24", renewed: 0, lost: 0, pending: 1 },
  ],
};

const firePieData  = [{ name:"Renewed Policy", value:2 }, { name:"Lost Policy", value:3 }, { name:"Pending", value:3 }];
const motorPieData = [{ name:"Renewed Policy", value:2 }, { name:"Lost Policy", value:3 }, { name:"Pending", value:2 }];
const PIE_COLORS = ["#6366f1","#f87171","#d1d5db"];

const ALL_TABLE_DATA = [
  // March 2026
  { month:"March 2026",    policy:"POL-1001", client:"Juan Dela Cruz",    line:"Motor Car",       issued:"01/15/2026", expiry:"01/15/2027", premium:"₱2,500", sum:"₱850,000", status:"New"     },
  { month:"March 2026",    policy:"POL-1002", client:"Maria Santos",      line:"Motor Car",       issued:"02/01/2026", expiry:"01/15/2027", premium:"₱1,500", sum:"₱480,000", status:"Renewed" },
  { month:"March 2026",    policy:"POL-1003", client:"Emily Fernandez",   line:"Fire & Property", issued:"01/15/2026", expiry:"01/15/2027", premium:"₱2,500", sum:"₱850,000", status:"New"     },
  { month:"March 2026",    policy:"POL-1004", client:"Dennis Reyes",      line:"Motor Car",       issued:"02/01/2026", expiry:"01/15/2027", premium:"₱1,500", sum:"₱480,000", status:"New"     },
  { month:"March 2026",    policy:"POL-1005", client:"Lina Mercado",      line:"Motor Car",       issued:"01/15/2026", expiry:"01/15/2027", premium:"₱2,500", sum:"₱850,000", status:"Renewed" },
  { month:"March 2026",    policy:"POL-1006", client:"Lina Mercado",      line:"Motor Car",       issued:"01/15/2026", expiry:"01/15/2027", premium:"₱2,500", sum:"₱850,000", status:"Renewed" },
  // February 2026
  { month:"February 2026", policy:"POL-1006", client:"Roberto Gomez",     line:"Fire & Property", issued:"02/01/2026", expiry:"02/01/2027", premium:"₱1,500", sum:"₱480,000", status:"Renewed" },
  { month:"February 2026", policy:"POL-1007", client:"Antonio Reyes",     line:"Fire & Property", issued:"02/05/2026", expiry:"02/05/2027", premium:"₱2,500", sum:"₱850,000", status:"Lost"    },
  { month:"February 2026", policy:"POL-1008", client:"Manuel Chua",       line:"Motor Car",       issued:"02/08/2026", expiry:"02/08/2027", premium:"₱1,500", sum:"₱480,000", status:"Pending" },
  { month:"February 2026", policy:"POL-1009", client:"Sofia Ramirez",     line:"Fire & Property", issued:"02/10/2026", expiry:"02/10/2027", premium:"₱3,000", sum:"₱920,000", status:"Renewed" },
  { month:"February 2026", policy:"POL-1010", client:"Ricardo Santiago",  line:"Motor Car",       issued:"02/12/2026", expiry:"02/12/2027", premium:"₱2,000", sum:"₱600,000", status:"Lost"    },
  // January 2026
  { month:"January 2026",  policy:"POL-1011", client:"Carmen Flores",     line:"Fire & Property", issued:"01/05/2026", expiry:"01/05/2027", premium:"₱2,800", sum:"₱780,000", status:"New"     },
  { month:"January 2026",  policy:"POL-1012", client:"Miguel Torres",     line:"Motor Car",       issued:"01/10/2026", expiry:"01/10/2027", premium:"₱1,800", sum:"₱520,000", status:"Renewed" },
  { month:"January 2026",  policy:"POL-1013", client:"Elena Cruz",        line:"Motor Car",       issued:"01/15/2026", expiry:"01/15/2027", premium:"₱2,200", sum:"₱640,000", status:"Pending" },
  { month:"January 2026",  policy:"POL-1014", client:"Jose Rizal",        line:"Fire & Property", issued:"01/20/2026", expiry:"01/20/2027", premium:"₱3,200", sum:"₱990,000", status:"Lost"    },
  { month:"January 2026",  policy:"POL-1015", client:"Ana Reyes",         line:"Motor Car",       issued:"01/25/2026", expiry:"01/25/2027", premium:"₱1,600", sum:"₱500,000", status:"New"     },
];

const PAGE_SIZE = 5;
const PERIOD_OPTIONS = ["YTD","MTD","Daily"];

function Dropdown({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap">
        {value || label} <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open?"rotate-180":""}`} />
      </button>
      {open && options && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[140px]">
          {options.map(opt => (
            <button key={opt} onClick={() => { onChange?.(opt); setOpen(false); }}
              className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${(value||label)===opt?"font-bold text-black":"text-gray-600"}`}>
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

function MiniPie({ title, data }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <p className="font-bold text-black text-sm">{title}</p>
        <p className="text-gray-400 text-[10px]">As of March 2026</p>
      </div>
      <div className="flex items-center gap-2">
        <ResponsiveContainer width={110} height={100}>
          <PieChart>
            <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={46} labelLine={false}
              label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                const RADIAN = Math.PI / 180;
                const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                return <text x={cx + r*Math.cos(-midAngle*RADIAN)} y={cy + r*Math.sin(-midAngle*RADIAN)}
                  fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={700}>{value}</text>;
              }}>
              {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-col gap-1.5">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: PIE_COLORS[i] }} />
              <span className="text-[10px] text-gray-600">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function parseDate(dateStr) {
  const [mm, , yyyy] = dateStr.split("/").map(Number);
  return { month: mm, year: yyyy };
}

export default function RenewalRatioMonitoring() {
  const [page, setPage]       = useState(1);
  const [search, setSearch]   = useState("");
  const [period, setPeriod]   = useState("YTD");
  const [month, setMonth]     = useState(null);
  const [policyLine, setLine] = useState("All");
  const [status, setStatus]   = useState("All");

  const barData = BAR_DATA_BY_PERIOD[period] ?? BAR_DATA_BY_PERIOD["YTD"];

  const selectedMonth = month ? month.getMonth() + 1 : null;
  const selectedYear  = month ? month.getFullYear() : null;

  const filtered = ALL_TABLE_DATA.filter(r => {
    let matchMonth = true;
    if (month) {
      const { month: rowMonth, year: rowYear } = parseDate(r.issued);
      matchMonth = rowMonth === selectedMonth && rowYear === selectedYear;
    }
    const matchLine   = policyLine === "All" || r.line   === policyLine;
    const matchStatus = status     === "All" || r.status === status;
    const matchSearch = r.policy.toLowerCase().includes(search.toLowerCase()) ||
                        r.client.toLowerCase().includes(search.toLowerCase());
    return matchMonth && matchLine && matchStatus && matchSearch;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage   = Math.min(page, totalPages);
  const pageRows   = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const handleFilterChange = (setter) => (val) => { setter(val); setPage(1); };

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0"><Sidebar activeItem="Renewal Ratio Monitoring" /></div>
      <div className="flex-1 flex flex-col gap-4 min-w-0">

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard value="15" label="Expiring Policy" />
          <StatCard value="4"  label="Renewed Policy" />
          <StatCard value="6"  label="Lost Policy" />
          <StatCard value="5"  label="Pending" />
        </div>

        <div className="flex gap-4">
          <div className="flex-1 bg-white rounded-2xl p-5 shadow-sm min-w-0">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-black text-sm">
                YTD Policy Retention: Renewed vs. Lost{" "}
                <span className="text-gray-400 font-normal">(Stacked by Month)</span>
              </h2>
              <Dropdown label="YTD" options={PERIOD_OPTIONS} value={period} onChange={setPeriod} />
            </div>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={barData} barCategoryGap="40%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="month" tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} domain={[0,25]}
                  label={{ value:"count", angle:-90, position:"insideLeft", style:{ fontSize:10, fill:"#9ca3af" } }} />
                <Tooltip contentStyle={{ borderRadius:10, border:"none", fontSize:12 }} />
                <Legend wrapperStyle={{ fontSize:11 }} formatter={v => v==="renewed"?"Renewed Policies":v==="lost"?"Lost Policies":"Pending"} />
                <Bar dataKey="renewed" name="renewed" stackId="a" fill="#6366f1"
                  label={{ position:"center", fontSize:10, fill:"#fff", fontWeight:700 }} />
                <Bar dataKey="lost"    name="lost"    stackId="a" fill="#f87171"
                  label={{ position:"center", fontSize:10, fill:"#fff", fontWeight:700 }} />
                <Bar dataKey="pending" name="pending" stackId="a" fill="#d1d5db" radius={[4,4,0,0]}
                  label={{ position:"center", fontSize:10, fill:"#555", fontWeight:700 }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <MiniPie title="Fire & Property" data={firePieData} />
            <MiniPie title="Motor & Car"     data={motorPieData} />
          </div>
        </div>

        <div className="flex gap-4">
          <div className="bg-white min-h-[340px] rounded-2xl p-5 shadow-sm min-w-0 flex flex-col flex-1">
            <div className="flex flex-wrap gap-2 mb-4 items-center">
              <div className="flex items-center gap-2">
                {month && (
                  <button
                    type="button"
                    onClick={() => handleFilterChange(setMonth)(null)}
                    className="flex items-center cursor-pointer gap-1.5 bg-violet-50 border border-violet-200 text-violet-600 text-xs font-semibold px-3 py-1.5 rounded-xl hover:bg-violet-50 hover:border-violet-200 hover:text-violet-500 transition"
                  >
                    Show All Months
                  </button>
                )}
                <MonthYearPicker value={month} onChange={handleFilterChange(setMonth)} />
              </div>
              <Dropdown label="Policy Line: All" options={["Policy Line: All","Motor Car","Fire & Property"]}
                value={policyLine==="All"?"Policy Line: All":policyLine}
                onChange={v => { handleFilterChange(setLine)(v==="Policy Line: All"?"All":v); }} />
              <Dropdown label="Status: All" options={["Status: All","New","Renewed","Lost","Pending"]}
                value={status==="All"?"Status: All":status}
                onChange={v => { handleFilterChange(setStatus)(v==="Status: All"?"All":v); }} />
              <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
                <Search className="w-3.5 h-3.5 text-gray-400" />
                <input className="text-xs outline-none text-gray-600 w-36" placeholder="Search Policy Number"
                  value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-center">
                <thead>
                  <tr className="border-b border-gray-100">
                    {["Policy Number","Client Name","Policy Line","Issued Date","Expiry Date","Premium","Sum Insured","Status"].map(h => (
                      <th key={h} className="py-2 px-2 text-gray-500 font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((r, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="py-2.5 px-2">{r.policy}</td>
                      <td className="py-2.5 px-2">{r.client}</td>
                      <td className="py-2.5 px-2">{r.line}</td>
                      <td className="py-2.5 px-2">{r.issued}</td>
                      <td className="py-2.5 px-2">{r.expiry}</td>
                      <td className="py-2.5 px-2">{r.premium}</td>
                      <td className="py-2.5 px-2">{r.sum}</td>
                      <td className="py-2.5 px-2">{r.status}</td>
                    </tr>
                  ))}
                  {pageRows.length === 0 && (
                    <tr><td colSpan={8} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end items-center gap-2 mt-auto text-xs text-gray-500">
              <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={safePage===1} className="disabled:opacity-30">«</button>
              <span>{safePage} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={safePage===totalPages} className="disabled:opacity-30">»</button>
            </div>
          </div>

          <div className="w-64 h-fit flex-shrink-0 bg-white rounded-2xl p-5 shadow-sm flex flex-col justify-center">
            <p className="text-black font-bold text-sm">Retention Rate</p>
            <p className="text-gray-400 text-[10px] mt-0.5">As of March 2026</p>
            <p className="text-black font-black text-5xl mt-3">26.67%</p>
            <p className="text-gray-400 text-[10px] mt-2">Renewal Rate = Renewed ÷ Expiring × 100</p>
          </div>
        </div>
      </div>
    </div>
  );
}