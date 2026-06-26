import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { ChevronDown, Search } from "lucide-react";
import Sidebar from "../components/sidebar";

const barData = [
  { month: "January", renewed: 14, lost: 8, pending: 0 },
  { month: "February", renewed: 11, lost: 9, pending: 0 },
  { month: "March", renewed: 4, lost: 6, pending: 5 },
];

const firePieData = [
  { name: "Renewed Policy", value: 2 },
  { name: "Lost Policy", value: 3 },
  { name: "Pending", value: 3 },
];
const motorPieData = [
  { name: "Renewed Policy", value: 2 },
  { name: "Lost Policy", value: 3 },
  { name: "Pending", value: 2 },
];
const PIE_COLORS = ["#6366f1", "#f87171", "#d1d5db"];

const tableData = [
  {
    policy: "POL-1001",
    client: "Juan Dela Cruz",
    line: "Motor Car",
    issued: "01/15/2026",
    expiry: "01/15/2027",
    premium: "₱2,500",
    sum: "₱850,000",
    status: "New",
  },
  {
    policy: "POL-1002",
    client: "Maria Santos",
    line: "Motor Car",
    issued: "02/01/2026",
    expiry: "01/15/2027",
    premium: "₱1,500",
    sum: "₱480,000",
    status: "Renewed",
  },
  {
    policy: "POL-1003",
    client: "Emily Fernandez",
    line: "Fire & Property",
    issued: "01/15/2026",
    expiry: "01/15/2027",
    premium: "₱2,500",
    sum: "₱850,000",
    status: "New",
  },
  {
    policy: "POL-1004",
    client: "Dennis Reyes",
    line: "Motor Car",
    issued: "02/01/2026",
    expiry: "01/15/2027",
    premium: "₱1,500",
    sum: "₱480,000",
    status: "New",
  },
  {
    policy: "POL-1005",
    client: "Lina Mercado",
    line: "Motor Car",
    issued: "01/15/2026",
    expiry: "01/15/2027",
    premium: "₱2,500",
    sum: "₱850,000",
    status: "Renewed",
  },
];

function StatCard({ value, label }) {
  return (
    <div className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
      <p className="text-gray-400 text-xs">As of March 2026</p>
      <p className="text-black font-black text-5xl leading-none my-2">
        {value}
      </p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  );
}

function Dropdown({ label }) {
  return (
    <button className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-300 transition">
      {label} <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
    </button>
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
            <Pie
              data={data}
              dataKey="value"
              cx="50%"
              cy="50%"
              outerRadius={46}
              labelLine={false}
              label={({
                cx,
                cy,
                midAngle,
                innerRadius,
                outerRadius,
                value,
              }) => {
                const RADIAN = Math.PI / 180;
                const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                return (
                  <text
                    x={cx + r * Math.cos(-midAngle * RADIAN)}
                    y={cy + r * Math.sin(-midAngle * RADIAN)}
                    fill="#fff"
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={11}
                    fontWeight={700}
                  >
                    {value}
                  </text>
                );
              }}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-col gap-1.5">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ background: PIE_COLORS[i] }}
              />
              <span className="text-[10px] text-gray-600">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function RenewalRatioMonitoring() {
  const [page, setPage] = useState(1);
  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem="Renewal Ratio Monitoring" />
      </div>
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard value="15" label="Expiring Policy" />
          <StatCard value="4" label="Renewed Policy" />
          <StatCard value="6" label="Lost Policy" />
          <StatCard value="5" label="Pending" />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-black text-sm">
                YTD Policy Retention: Renewed vs. Lost{" "}
                <span className="text-gray-400 font-normal">
                  (Stacked by Month)
                </span>
              </h2>
              <Dropdown label="YTD" />
            </div>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={barData} barCategoryGap="40%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 25]}
                  label={{
                    value: "count",
                    angle: -90,
                    position: "insideLeft",
                    style: { fontSize: 10, fill: "#9ca3af" },
                  }}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: "none",
                    fontSize: 12,
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11 }}
                  formatter={(v) =>
                    v === "renewed"
                      ? "Renewed Policies"
                      : v === "lost"
                        ? "Lost Policies"
                        : "Pending"
                  }
                />
                <Bar
                  dataKey="renewed"
                  name="renewed"
                  stackId="a"
                  fill="#6366f1"
                />
                <Bar dataKey="lost" name="lost" stackId="a" fill="#f87171" />
                <Bar
                  dataKey="pending"
                  name="pending"
                  stackId="a"
                  fill="#d1d5db"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-3">
            <MiniPie title="Fire & Property" data={firePieData} />
            <MiniPie title="Motor & Car" data={motorPieData} />
          </div>
        </div>

        {/* Table */}
        <div className="flex justify-between items-start gap-4">
          <div className="bg-white rounded-2xl p-5 shadow-sm w-full">
            <div className="flex flex-wrap gap-2 mb-4 items-center">
              <Dropdown label="March 2026" />
              <Dropdown label="Policy Line: All" />
              <Dropdown label="Status: All" />
              <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 ml-auto">
                <Search className="w-3.5 h-3.5 text-gray-400" />
                <input
                  className="text-xs outline-none text-gray-600 w-36"
                  placeholder="Search Policy Number"
                />
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-center">
                <thead>
                  <tr className="border-b border-gray-100">
                    {[
                      "Policy Number",
                      "Client Name",
                      "Policy Line",
                      "Issued Date",
                      "Expiry Date",
                      "Premium",
                      "Sum Insured",
                      "Status",
                    ].map((h) => (
                      <th
                        key={h}
                        className="py-2 px-2 text-gray-500 font-semibold whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.map((r, i) => (
                    <tr
                      key={i}
                      className="border-b border-gray-50 hover:bg-gray-50 transition"
                    >
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
                </tbody>
              </table>
            </div>
            <div className="flex justify-end items-center gap-2 mt-3 text-xs text-gray-500">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))}>
                «
              </button>
              <span>{page} / 5</span>
              <button onClick={() => setPage((p) => Math.min(5, p + 1))}>
                »
              </button>
            </div>
          </div>
          <div className="h-[100px] w-110 bg-white border border-gray-200 rounded-xl px-4 py-2 ml-auto">
            <p className="text-xs font-bold text-black">Retention Rate</p>
            <p className="text-[10px] text-gray-400">As of March 2026</p>
            <p className="text-black font-black text-2xl mt-1">26.67%</p>
          </div>
        </div>
      </div>
    </div>
  );
}
