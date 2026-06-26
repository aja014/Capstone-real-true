import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import Sidebar from "../components/sidebar";

// --- Data ---
const barData = [
  { year: "2022", policies: 72 },
  { year: "2023", policies: 86 },
  { year: "2025", policies: 82 },
  { year: "2026", policies: 28 },
];

const lineData = [
  { month: "Oct", motor: 25, fire: 17 },
  { month: "Nov", motor: 20, fire: 17 },
  { month: "Dec", motor: 17, fire: 14 },
  { month: "Jan", motor: 19, fire: 8 },
  { month: "Feb", motor: 22, fire: 14 },
  { month: "Mar", motor: 12, fire: 4 },
];

const pieData = [
  { name: "Converted Accounts", value: 44 },
  { name: "Quotation", value: 56 },
];

const PIE_COLORS = ["#FBBF24", "#FEF3C7"];

const statCards = [
  {
    label: "Gross Premium Written",
    value: "₱ 43,523.01",
    sub: "Today",
    big: false,
  },
  { label: "Policies made", value: "16", sub: "As of March 2026", big: true },
  { label: "Total Quotation Offered", value: "39", sub: "As of March 2026", big: true },
  { label: "Filed Claims", value: "3", sub: "As of March 2026", big: true },
];

// Custom pie label
const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }) => {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill={name === "Quotation" ? "#92400e" : "#1f2937"} textAnchor="middle" dominantBaseline="central" fontSize={13} fontWeight={700}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

export default function Overview() {
  const [activeNav, setActiveNav] = useState("Overview");

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      {/* Sidebar */}
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem={activeNav} onNavigate={setActiveNav} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">

        {/* Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((card) => (
            <div key={card.label} className="bg-white rounded-2xl px-5 py-4 shadow-sm flex flex-col justify-between min-h-[110px]">
              <p className="text-gray-400 text-xs font-medium">{card.sub}</p>
              <p className={`font-black text-black leading-none my-2 ${card.big ? "text-4xl sm:text-5xl" : "text-2xl sm:text-4xl"}`}>
                {card.value}
              </p>
              <p className="text-gray-500 text-xs">{card.label}</p>
            </div>
          ))}
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* Bar Chart */}
          <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-sm">
            <h2 className="font-bold text-black text-sm mb-4">Policy Made (Past 4 Years)</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} barCategoryGap="10%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="year" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} domain={[0, 88]} ticks={[0, 22, 44, 66, 88]} />
                <Tooltip
                  contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }}
                  cursor={{ fill: "#f9fafb" }}
                />
                <Bar dataKey="policies" fill="#6b9bd2" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Pie Chart */}
          <div className="bg-white rounded-2xl p-5 shadow-sm flex flex-col items-center">
            <h2 className="font-bold text-black text-sm text-center mb-1">Quotation vs. Converted Accounts</h2>
            <p className="text-gray-400 text-xs mb-3">(As of March 2026)</p>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  dataKey="value"
                  labelLine={false}
                  label={renderCustomLabel}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            {/* Legend */}
            <div className="flex flex-col gap-1.5 mt-2 self-start pl-4">
              {pieData.map((entry, i) => (
                <div key={entry.name} className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-sm inline-block flex-shrink-0" style={{ backgroundColor: PIE_COLORS[i] }} />
                  <span className="text-xs text-gray-600">{entry.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Line Chart */}
        <div className="bg-white rounded-2xl p-5 shadow-sm">
          <h2 className="font-bold text-black text-sm mb-4">Policy Line (Past 6 Months)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={lineData}>
              <CartesianGrid stroke="#f3f4f6" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} domain={[0, 30]} ticks={[0, 10, 20, 30]} label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(value) => value === "motor" ? "Motor & Car" : "Fire & Prop."}
              />
              <Line
                type="monotone"
                dataKey="motor"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ r: 4, fill: "#6366f1", strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                label={{ position: "top", fontSize: 10, fill: "#6366f1" }}
              />
              <Line
                type="monotone"
                dataKey="fire"
                stroke="#f87171"
                strokeWidth={2}
                dot={{ r: 4, fill: "#f87171", strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                label={{ position: "top", fontSize: 10, fill: "#f87171" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  );
}