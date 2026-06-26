import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { StatCard, PolicyTable, MiniPie, Dropdown } from "./PolicyDistributionShared";

// ─── MTD Data ─────────────────────────────────────────────────────────────────
const mtdBarData = Array.from({ length: 24 }, (_, i) => ({
  day: String(i + 1),
  fire:  [16,16,16,15,16,16,17,14,15,15,15,14,12,11,11,11,13,14,13,13,14,13,14,14][i],
  motor: [15,16,13,13,12,13,13,13,14,13,13,13,13,13,15,14,13,14,13,14,14,14,12,14][i],
}));

const mtdFirePie  = [{ name: "Renewed Policy", value: 3 }, { name: "New Policy", value: 2 }];
const mtdMotorPie = [{ name: "Renewed Policy", value: 9 }, { name: "New Policy", value: 2 }];
const MTD_PIE_COLORS_FIRE  = ["#a5b4fc", "#c4b5fd"];
const MTD_PIE_COLORS_MOTOR = ["#f87171", "#fca5a5"];

export default function MTDView() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [month, setMonth] = useState("March 24");
  const [year, setYear]   = useState("2026");

  return (
    <div className="flex flex-col gap-4">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub="As of March 2026" value="179"            label="Total Policies Made" />
        <StatCard sub="As of March 2026" value="87"             label="Fire & Property Policies" />
        <StatCard sub="As of March 2026" value="92"             label="Motor & Car Policies" />
        <StatCard sub="As of March 2026" value="₱1,276,591.68"  label="Gross Premium Written" target="₱1,028,256.68" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Daily Bar Chart */}
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
              <Bar dataKey="fire"  name="Fire & Property" stackId="a" fill="#a5b4fc"
                label={{ position: "center", fontSize: 8, fill: "#fff", fontWeight: 700 }} />
              <Bar dataKey="motor" name="Motor & Car"      stackId="a" fill="#f87171" radius={[2, 2, 0, 0]}
                label={{ position: "center", fontSize: 8, fill: "#fff", fontWeight: 700 }} />
            </BarChart>
          </ResponsiveContainer>
          {/* Legend */}
          <div className="flex items-center gap-4 mt-1 justify-center">
            {[["#a5b4fc","Fire & Property"],["#f87171","Motor & Car"]].map(([c,l]) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm" style={{ background: c }} />
                <span className="text-[10px] text-gray-500">{l}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Pie Charts */}
        <div className="flex flex-col gap-3">
          <MiniPie title="Fire & Property" data={mtdFirePie}  colors={MTD_PIE_COLORS_FIRE}  sub="As of March 24 2026" />
          <MiniPie title="Motor & Car"     data={mtdMotorPie} colors={MTD_PIE_COLORS_MOTOR} sub="As of March 24 2026" />
        </div>
      </div>

      {/* Table */}
      <PolicyTable
        page={page} setPage={setPage} totalPages={3}
        search={search} setSearch={setSearch}
        extraFilters={
          <div className="flex items-center gap-2 ml-auto">
            <Dropdown label={month} options={["March 1","March 7","March 14","March 24"]} value={month} onChange={setMonth} />
            <span className="text-gray-300">|</span>
            <Dropdown label={year}  options={["2024","2025","2026"]} value={year}  onChange={setYear} />
          </div>
        }
      />
    </div>
  );
}
