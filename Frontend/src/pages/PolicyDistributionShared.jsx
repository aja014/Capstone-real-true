import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { ChevronDown, Search } from "lucide-react";

// ─── Shared table data ────────────────────────────────────────────────────────
export const tableData = [
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
    line: "Fire & Property",
    issued: "01/15/2026",
    expiry: "01/15/2027",
    premium: "₱2,500",
    sum: "₱850,000",
    status: "Renewed",
  },
  {
    policy: "POL-1006",
    client: "Roberto Gomez",
    line: "Fire & Property",
    issued: "02/01/2026",
    expiry: "01/15/2027",
    premium: "₱1,500",
    sum: "₱480,000",
    status: "Renewed",
  },
  {
    policy: "POL-1007",
    client: "Antonio Reyes",
    line: "Fire & Property",
    issued: "01/15/2026",
    expiry: "01/15/2027",
    premium: "₱2,500",
    sum: "₱850,000",
    status: "New",
  },
  {
    policy: "POL-1008",
    client: "Manuel Chua",
    line: "Motor Car",
    issued: "02/01/2026",
    expiry: "01/15/2027",
    premium: "₱1,500",
    sum: "₱480,000",
    status: "Renewed",
  },
];

// ─── Dropdown ─────────────────────────────────────────────────────────────────
export function Dropdown({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-300 transition"
      >
        {label} <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
      </button>
      {open && options && (
        <div className="absolute top-full mt-1 left-0 bg-white border border-gray-100 rounded-xl shadow-lg z-10 min-w-[120px]">
          {options.map((o) => (
            <button
              key={o}
              onClick={() => {
                onChange?.(o);
                setOpen(false);
              }}
              className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${value === o ? "font-bold text-black" : "text-gray-600"}`}
            >
              {o}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── StatCard ─────────────────────────────────────────────────────────────────
export function StatCard({ sub, value, label, target }) {
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm min-w-0 overflow-hidden text-black">
      <p className="text-sm text-gray-500 truncate">{sub}</p>
      <p className="text-xl md:text-4xl font-bold break-words">{value}</p>
      <p className="text-sm font-medium break-words">{label}</p>
      {target && (
        <p className="text-xs text-gray-500 break-words">Target: {target}</p>
      )}
    </div>
  );
}

// ─── PolicyTable ──────────────────────────────────────────────────────────────
export function PolicyTable({
  page,
  setPage,
  totalPages = 3,
  search,
  setSearch,
  extraFilters,
}) {
  const filtered = tableData.filter(
    (r) =>
      r.policy.toLowerCase().includes(search.toLowerCase()) ||
      r.client.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm">
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <Dropdown label="Policy Line: All" />
        <Dropdown label="Status: All" />
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2">
          <Search className="w-3.5 h-3.5 text-gray-400" />
          <input
            className="text-xs outline-none text-gray-600 w-36"
            placeholder="Search Policy Number"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {extraFilters}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-center">
          <thead>
            <tr className="border-b border-gray-200">
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
                  className="py-3 px-3 text-gray-700 font-bold whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr
                key={i}
                className="border-b border-gray-50 hover:bg-gray-50 transition"
              >
                <td className="py-3 px-3">{r.policy}</td>
                <td className="py-3 px-3">{r.client}</td>
                <td className="py-3 px-3">{r.line}</td>
                <td className="py-3 px-3">{r.issued}</td>
                <td className="py-3 px-3">{r.expiry}</td>
                <td className="py-3 px-3">{r.premium}</td>
                <td className="py-3 px-3">{r.sum}</td>
                <td className="py-3 px-3">{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex justify-end items-center gap-2 mt-3 text-xs text-gray-500">
        <button onClick={() => setPage((p) => Math.max(1, p - 1))}>«</button>
        <span>
          {page} / {totalPages}
        </span>
        <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
          »
        </button>
      </div>
    </div>
  );
}

// ─── MiniPie ──────────────────────────────────────────────────────────────────
export function MiniPie({ title, data, colors, sub = "As of March 2026" }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <p className="font-bold text-black text-sm">{title}</p>
        <p className="text-gray-400 text-[10px]">{sub}</p>
      </div>
      <div className="flex items-center gap-3">
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
                <Cell key={i} fill={colors[i]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="flex flex-col gap-2">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ background: colors[i] }}
              />
              <span className="text-[10px] text-gray-600">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
