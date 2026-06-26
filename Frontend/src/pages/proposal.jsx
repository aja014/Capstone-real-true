import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { ChevronDown } from "lucide-react";
import Sidebar from "../components/sidebar";
import FloodRiskModal from "../components/FloodRiskModal";
import { MonthYearPicker } from "../components/DatePicker";

const BAR_DATA_BY_PERIOD = {
  "Past 6 Months": [
    { month: "Oct", converted: 25, quotation: 17 },
    { month: "Nov", converted: 9,  quotation: 20 },
    { month: "Dec", converted: 17, quotation: 14 },
    { month: "Jan", converted: 9,  quotation: 19 },
    { month: "Feb", converted: 22, quotation: 14 },
    { month: "Mar", converted: 4,  quotation: 12 },
  ],
  "Past 3 Months": [
    { month: "Jan", converted: 9,  quotation: 19 },
    { month: "Feb", converted: 22, quotation: 14 },
    { month: "Mar", converted: 4,  quotation: 12 },
  ],
  "Past 12 Months": [
    { month: "Apr", converted: 18, quotation: 22 },
    { month: "May", converted: 21, quotation: 15 },
    { month: "Jun", converted: 13, quotation: 18 },
    { month: "Jul", converted: 7,  quotation: 11 },
    { month: "Aug", converted: 19, quotation: 16 },
    { month: "Sep", converted: 11, quotation: 23 },
    { month: "Oct", converted: 25, quotation: 17 },
    { month: "Nov", converted: 9,  quotation: 20 },
    { month: "Dec", converted: 17, quotation: 14 },
    { month: "Jan", converted: 9,  quotation: 19 },
    { month: "Feb", converted: 22, quotation: 14 },
    { month: "Mar", converted: 4,  quotation: 12 },
  ],
};

const firePieData  = [{ name: "Quotation", value: 3 }, { name: "Converted Account", value: 2 }];
const motorPieData = [{ name: "Quotation", value: 9 }, { name: "Converted Account", value: 2 }];
const PIE_COLORS   = ["#a5b4fc", "#6366f1"];
const forecastData = [{ name: "March", converted: 4, forecast: 10 }];

const ALL_TABLE_DATA = [
  // March 2026
  { month:"March 2026",    quote:"Q-1016", date:"03/15/2026", client:"Juan Karlos",    type:"Motor & Car",  premium:"₱8,500.00",  sum:"₱30,000.00", risk:"Fair", claim:"YES" },
  { month:"March 2026",    quote:"Q-1017", date:"03/15/2026", client:"Marie Grace",    type:"Fire & Prop.", premium:"₱10,000.00", sum:"₱50,000.00", risk:"Good", claim:"NO"  },
  { month:"March 2026",    quote:"Q-1018", date:"03/15/2026", client:"John Lopez",     type:"Motor & Car",  premium:"₱8,500.00",  sum:"₱30,000.00", risk:"Fair", claim:"YES" },
  { month:"March 2026",    quote:"Q-1019", date:"03/15/2026", client:"Arun Sin",       type:"Fire & Prop.", premium:"₱10,000.00", sum:"₱50,000.00", risk:"Good", claim:"NO"  },
  { month:"March 2026",    quote:"Q-1020", date:"03/15/2026", client:"Atong Wang",     type:"Fire & Prop.", premium:"₱10,000.00", sum:"₱50,000.00", risk:"Good", claim:"YES" },
  { month:"March 2026",    quote:"Q-1021", date:"03/16/2026", client:"Sofia Ramirez",  type:"Motor & Car",  premium:"₱9,000.00",  sum:"₱35,000.00", risk:"Good", claim:"NO"  },
  { month:"March 2026",    quote:"Q-1022", date:"03/16/2026", client:"Carlos Mendez",  type:"Fire & Prop.", premium:"₱12,000.00", sum:"₱60,000.00", risk:"Fair", claim:"YES" },
  { month:"March 2026",    quote:"Q-1023", date:"03/17/2026", client:"Elena Cruz",     type:"Motor & Car",  premium:"₱7,500.00",  sum:"₱28,000.00", risk:"Poor", claim:"NO"  },
  { month:"March 2026",    quote:"Q-1024", date:"03/17/2026", client:"Miguel Torres",  type:"Fire & Prop.", premium:"₱11,000.00", sum:"₱45,000.00", risk:"Good", claim:"YES" },
  { month:"March 2026",    quote:"Q-1025", date:"03/18/2026", client:"Leonor Rivera",  type:"Motor & Car",  premium:"₱8,000.00",  sum:"₱32,000.00", risk:"Fair", claim:"NO"  },
  // February 2026
  { month:"February 2026", quote:"Q-1006", date:"02/05/2026", client:"Jose Rizal",     type:"Fire & Prop.", premium:"₱13,500.00", sum:"₱55,000.00", risk:"Good", claim:"YES" },
  { month:"February 2026", quote:"Q-1007", date:"02/08/2026", client:"Carmen Flores",  type:"Motor & Car",  premium:"₱9,500.00",  sum:"₱40,000.00", risk:"Fair", claim:"NO"  },
  { month:"February 2026", quote:"Q-1008", date:"02/10/2026", client:"Diego Santos",   type:"Fire & Prop.", premium:"₱10,500.00", sum:"₱48,000.00", risk:"Good", claim:"YES" },
  { month:"February 2026", quote:"Q-1009", date:"02/14/2026", client:"Ana Reyes",      type:"Motor & Car",  premium:"₱8,200.00",  sum:"₱31,000.00", risk:"Poor", claim:"NO"  },
  { month:"February 2026", quote:"Q-1010", date:"02/18/2026", client:"Pedro Gomez",    type:"Fire & Prop.", premium:"₱14,000.00", sum:"₱62,000.00", risk:"Good", claim:"YES" },
  // January 2026
  { month:"January 2026",  quote:"Q-1001", date:"01/05/2026", client:"Rosa Magtanggol",type:"Motor & Car",  premium:"₱7,800.00",  sum:"₱29,000.00", risk:"Good", claim:"NO"  },
  { month:"January 2026",  quote:"Q-1002", date:"01/08/2026", client:"Ben Aquino",     type:"Fire & Prop.", premium:"₱11,500.00", sum:"₱52,000.00", risk:"Fair", claim:"YES" },
  { month:"January 2026",  quote:"Q-1003", date:"01/12/2026", client:"Luisa Chua",     type:"Motor & Car",  premium:"₱8,900.00",  sum:"₱33,000.00", risk:"Good", claim:"NO"  },
  { month:"January 2026",  quote:"Q-1004", date:"01/18/2026", client:"Marco Velarde",  type:"Fire & Prop.", premium:"₱12,500.00", sum:"₱58,000.00", risk:"Poor", claim:"YES" },
  { month:"January 2026",  quote:"Q-1005", date:"01/25/2026", client:"Tina Bautista",  type:"Motor & Car",  premium:"₱9,200.00",  sum:"₱36,000.00", risk:"Fair", claim:"NO"  },
];

const PAGE_SIZE = 5;

function Dropdown({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap">
        {value || label} <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && options && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[140px]">
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

function StatCard({ sub, value, label }) {
  return (
    <div className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
      <p className="text-gray-400 text-xs">{sub}</p>
      <p className="text-black font-black text-5xl leading-none my-2">{value}</p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  );
}

function MiniPie({ title, data }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <p className="text-gray-400 text-[10px] mb-0.5">As of March 2026</p>
      <p className="font-bold text-black text-sm mb-2">{title}</p>
      <div className="flex items-center gap-3">
        <ResponsiveContainer width={110} height={95}>
          <PieChart>
            <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={44} labelLine={false}
              label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                const RADIAN = Math.PI / 180;
                const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                return <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)}
                  fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={700}>{value}</text>;
              }}>
              {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-col gap-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: PIE_COLORS[i] }} />
              <span className="text-[10px] text-gray-600 leading-tight">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const RoundedBar = ({ x, y, width, height, fill }) => {
  const r = 5;
  if (!height || height <= 0) return null;
  return <path d={`M${x},${y+r} Q${x},${y} ${x+r},${y} L${x+width-r},${y} Q${x+width},${y} ${x+width},${y+r} L${x+width},${y+height} L${x},${y+height} Z`} fill={fill} />;
};
const BarValueLabel = ({ x, y, width, value }) => (
  <text x={x + width / 2} y={y + 18} fill="#fff" textAnchor="middle" fontSize={12} fontWeight={700}>{value}</text>
);

function parseDate(dateStr) {
  const [mm, , yyyy] = dateStr.split("/").map(Number);
  return { month: mm, year: yyyy };
}

export default function QuotationsProposal() {
  const [page, setPage]           = useState(1);
  const [period, setPeriod]       = useState("Past 6 Months");
  const [riskFilter, setRisk]     = useState("Risk Assessment: All");
  const [lineFilter, setLine]     = useState("Policy Line: All");
  const [statusFilter, setStatus] = useState("Status: All");
  const [month, setMonth]         = useState(null);
  const [openFloodModal, setOpenFloodModal] = useState(false);

  const barData = BAR_DATA_BY_PERIOD[period] ?? BAR_DATA_BY_PERIOD["Past 6 Months"];

  const selectedMonth = month ? month.getMonth() + 1 : null;
  const selectedYear  = month ? month.getFullYear() : null;

  const filtered = ALL_TABLE_DATA.filter(r => {
    let matchMonth = true;
    if (month) {
      const { month: rowMonth, year: rowYear } = parseDate(r.date);
      matchMonth = rowMonth === selectedMonth && rowYear === selectedYear;
    }
    const matchRisk   = riskFilter   === "Risk Assessment: All" || r.risk  === riskFilter;
    const matchLine   = lineFilter   === "Policy Line: All"     || r.type  === lineFilter;
    const matchStatus = statusFilter === "Status: All"          || r.claim === statusFilter;
    return matchMonth && matchRisk && matchLine && matchStatus;
  });

  const totalPages  = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage    = Math.min(page, totalPages);
  const pageRows    = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const handleFilterChange = (setter) => (val) => { setter(val); setPage(1); };

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0"><Sidebar activeItem="Quotations/ Proposal" /></div>
      <div className="flex-1 flex flex-col gap-4 min-w-0">

        <div className="grid grid-cols-3 gap-4">
          <StatCard sub="As of March 2026" value="16" label="Total Proposal Quotes" />
          <StatCard sub="As of March 2026" value="4"  label="Converted Accounts" />
          <StatCard sub="As of March 2026" value="12" label="Offered Quotation" />
        </div>

        <div className="flex gap-4">
          <div className="flex-1 bg-white rounded-2xl p-5 shadow-sm flex flex-col gap-3 min-w-0">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-black text-sm">Monthly Quotation Conversion Trend</h2>
              <Dropdown
                label="Past 6 Months"
                options={["Past 6 Months", "Past 3 Months", "Past 12 Months"]}
                value={period}
                onChange={setPeriod}
              />
            </div>
            <ResponsiveContainer width="100%" height={270}>
              <BarChart data={barData} barCategoryGap="30%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} domain={[0, 50]}
                  label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
                <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="converted" name="Converted" stackId="a" fill="#6366f1"
                  label={{ position: "center", fontSize: 10, fill: "#fff", fontWeight: 700 }} />
                <Bar dataKey="quotation"  name="Quotation"  stackId="a" fill="#a5b4fc" radius={[4,4,0,0]}
                  label={{ position: "center", fontSize: 10, fill: "#fff", fontWeight: 700 }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <MiniPie title="Fire & Property" data={firePieData} />
            <MiniPie title="Motor & Car"     data={motorPieData} />
          </div>
        </div>

        <div className="flex gap-4">
          <div className="bg-white rounded-2xl p-5 shadow-sm min-w-0 flex flex-col flex-1">
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
              <Dropdown label="Risk Assessment: All" options={["Risk Assessment: All","Fair","Good","Poor"]} value={riskFilter} onChange={handleFilterChange(setRisk)} />
              <Dropdown label="Policy Line: All"     options={["Policy Line: All","Motor & Car","Fire & Prop."]} value={lineFilter} onChange={handleFilterChange(setLine)} />
              <Dropdown label="Status: All"          options={["Status: All","YES","NO"]} value={statusFilter} onChange={handleFilterChange(setStatus)} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-center">
                <thead>
                  <tr className="border-b border-gray-100">
                    {["Quote Number","Quote Date","Client Name","Policy Type","Premium","Sum Insured","Risk Assessment","Claim Possibility","Geospatial Information",""].map(h => (
                      <th key={h} className="py-2 px-2 text-gray-500 font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((r, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50 transition">
                      <td className="py-2.5 px-2">{r.quote}</td>
                      <td className="py-2.5 px-2">{r.date}</td>
                      <td className="py-2.5 px-2">{r.client}</td>
                      <td className="py-2.5 px-2">{r.type}</td>
                      <td className="py-2.5 px-2">{r.premium}</td>
                      <td className="py-2.5 px-2">{r.sum}</td>
                      <td className="py-2.5 px-2">{r.risk}</td>
                      <td className="py-2.5 px-2">
                        <span className={`font-bold ${r.claim === "YES" ? "text-green-500" : "text-red-500"}`}>{r.claim}</span>
                      </td>
                      <td className="py-2.5 px-2">
                        <button onClick={() => setOpenFloodModal(true)}
                          className="bg-black text-white text-[11px] px-3 py-1 rounded-lg hover:bg-gray-800 transition">View</button>
                      </td>
                    </tr>
                  ))}
                  {pageRows.length === 0 && (
                    <tr><td colSpan={10} className="py-6 text-gray-400 text-xs">No records found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end items-center gap-2 mt-auto text-xs text-gray-500">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={safePage === 1} className="disabled:opacity-30">«</button>
              <span>{safePage} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={safePage === totalPages} className="disabled:opacity-30">»</button>
            </div>
          </div>

          <div className="flex flex-col gap-3 w-64 flex-shrink-0">
            <div className="bg-white rounded-2xl p-5 shadow-sm flex items-center gap-3">
              <p className="text-black font-black text-4xl leading-none">50%</p>
              <p className="text-gray-600 text-xs leading-snug">Average Quotation<br />Claiming Rate</p>
            </div>
            <div className="bg-white rounded-2xl p-5 shadow-sm flex-1">
              <h2 className="font-bold text-black text-sm mb-3 text-center">March Policy Forecast</h2>
              <ResponsiveContainer width="100%" height={170}>
                <BarChart data={forecastData} barGap={8} barCategoryGap="25%" margin={{ top:8, right:8, left:-20, bottom:0 }}>
                  <CartesianGrid vertical={false} stroke="#f3f4f6" />
                  <XAxis dataKey="name" tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} domain={[0,10]} ticks={[0,2,4,6,8,10]} />
                  <defs>
                    <linearGradient id="fcastGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#c4b5fd"/><stop offset="100%" stopColor="#818cf8"/>
                    </linearGradient>
                  </defs>
                  <Bar dataKey="converted" barSize={50} shape={(p) => <RoundedBar {...p} fill="#7c6ff7" />} label={<BarValueLabel />} />
                  <Bar dataKey="forecast"  barSize={50} shape={(p) => <RoundedBar {...p} fill="url(#fcastGrad)" />} label={<BarValueLabel />} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <FloodRiskModal isOpen={openFloodModal} onClose={() => setOpenFloodModal(false)} />
      </div>
    </div>
  );
}