import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { StatCard, PolicyTable, MiniPie, tableData } from "./PolicyDistributionShared";
import { FullCalendarPicker } from "./DatePicker";
import { ChevronDown } from "lucide-react";

function YearPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const years = [2024, 2025, 2026, 2027];
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-medium text-gray-700 hover:border-gray-400 transition whitespace-nowrap"
      >
        {value}
        <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-white border border-gray-100 rounded-xl shadow-lg min-w-[80px]">
          {years.map(y => (
            <button key={y} onClick={() => { onChange(y); setOpen(false); }}
              className={`block w-full text-left px-4 py-2 text-xs hover:bg-yellow-50 transition ${value === y ? "font-bold text-black" : "text-gray-600"}`}>
              {y}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const mtdBarData = Array.from({ length: 24 }, (_, i) => ({
  day: String(i + 1),
  fire: [16, 16, 16, 15, 16, 16, 17, 14, 15, 15, 15, 14, 12, 11, 11, 11, 13, 14, 13, 13, 14, 13, 14, 14][i],
  motor: [15, 16, 13, 13, 12, 13, 13, 13, 14, 13, 13, 13, 13, 13, 15, 14, 13, 14, 13, 14, 14, 14, 12, 14][i],
}));
const mtdFirePie = [{ name: "Renewed Policy", value: 3 }, { name: "New Policy", value: 2 }];
const mtdMotorPie = [{ name: "Renewed Policy", value: 9 }, { name: "New Policy", value: 2 }];
const FIRE_COLORS = ["#a5b4fc", "#c4b5fd"];
const MOTOR_COLORS = ["#f87171", "#fca5a5"];

// Parse "MM/DD/YYYY" → { month (1-based), year }
function parseIssued(dateStr) {
  const [mm, , yyyy] = dateStr.split("/").map(Number);
  return { month: mm, year: yyyy };
}

export default function MTDView() {
  const [search, setSearch] = useState("");
  const [fromDate, setFromDate] = useState(null);
  const [year, setYear] = useState(2026);

  const selectedMonth = fromDate ? fromDate.getMonth() + 1 : null;
  const selectedDay = fromDate ? fromDate.getDate() : null;
  const selectedYear = year;

  const filteredData = tableData.filter((row) => {
    const [mm, dd, yyyy] = row.issued.split("/").map(Number);

    if (!fromDate) return true;

    return (
      mm === selectedMonth &&
      dd === selectedDay &&
      yyyy === selectedYear
    );
  });


  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub="As of March 2026" value="179" label="Total Policies Made" />
        <StatCard sub="As of March 2026" value="87" label="Fire & Property Policies" />
        <StatCard sub="As of March 2026" value="92" label="Motor & Car Policies" />
        <StatCard sub="As of March 2026" value="₱1,276,591.68" label="Gross Premium Written" target="₱1,028,256.68" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-sm">
          <h2 className="font-bold text-black text-sm mb-1">
            Policy Type: Motor & Car vs. Fire & Property{" "}
            <span className="text-gray-400 font-normal">(As of March 2026)</span>
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={mtdBarData} barCategoryGap="15%" margin={{ left: -10 }}>
              <CartesianGrid vertical={false} stroke="#f3f4f6" />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} domain={[0, 40]}
                label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 11 }} />
              <Bar dataKey="fire" name="Fire & Property" stackId="a" fill="#a5b4fc"
                label={{ position: "center", fontSize: 8, fill: "#fff", fontWeight: 700 }} />
              <Bar dataKey="motor" name="Motor & Car" stackId="a" fill="#f87171" radius={[2, 2, 0, 0]}
                label={{ position: "center", fontSize: 8, fill: "#fff", fontWeight: 700 }} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-1 justify-center">
            {[["#a5b4fc", "Fire & Property"], ["#f87171", "Motor & Car"]].map(([c, l]) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm" style={{ background: c }} />
                <span className="text-[10px] text-gray-500">{l}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <MiniPie title="Fire & Property" data={mtdFirePie} colors={FIRE_COLORS} sub="As of March 24 2026" />
          <MiniPie title="Motor & Car" data={mtdMotorPie} colors={MOTOR_COLORS} sub="As of March 24 2026" />
        </div>
      </div>

      <PolicyTable
        search={search}
        setSearch={setSearch}
        data={filteredData}
        extraFilters={
          <div className="flex items-center gap-2 ml-auto">
            <FullCalendarPicker value={fromDate} onChange={(date) => { setFromDate(date); setPage(1);}} />
            <span className="text-gray-400 text-xs font-medium">|</span>
            <YearPicker value={year} onChange={setYear} />
          </div>
        }
      />
    </div>
  );
}