import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { StatCard, PolicyTable, MiniPie, Dropdown } from "./PolicyDistributionShared";

// ─── YTD Data ─────────────────────────────────────────────────────────────────
const ytdBarData = [
  { month: "January",  fire: 130, motor: 150 },
  { month: "February", fire: 100, motor: 160 },
  { month: "March",    fire: 87,  motor: 92  },
];

const firePieData  = [{ name: "New Policy", value: 58 }, { name: "Renewed Policy", value: 29 }];
const motorPieData = [{ name: "New Policy", value: 21 }, { name: "Renewed Policy", value: 71 }];
const PIE_COLORS   = ["#a5b4fc", "#f87171"];

export default function YTDView() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  return (
    <div className="flex flex-col gap-4">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub="As of 2026" value="719"            label="Total Policies Made" />
        <StatCard sub="As of 2026" value="317"            label="Fire & Property Policies" />
        <StatCard sub="As of 2026" value="402"            label="Motor & Car Policies" />
        <StatCard sub="As of 2026" value="₱2,413,123.12"  label="Gross Premium Written" target="₱3,166,493.77" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Stacked Bar */}
        <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-sm">
          <h2 className="font-bold text-black text-sm mb-1">
            Policy Type: Motor & Car vs. Fire & Property{" "}
            <span className="text-gray-400 font-normal">(As of 2026)</span>
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={ytdBarData} barCategoryGap="35%">
              <CartesianGrid vertical={false} stroke="#f3f4f6" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} domain={[0, 300]}
                label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
              <Tooltip contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }} />
              <Bar dataKey="fire"  name="Fire & Property" stackId="a" fill="#a5b4fc"
                label={{ position: "center", fontSize: 11, fill: "#fff", fontWeight: 700 }} />
              <Bar dataKey="motor" name="Motor & Car"      stackId="a" fill="#f87171" radius={[4, 4, 0, 0]}
                label={{ position: "center", fontSize: 11, fill: "#fff", fontWeight: 700 }} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie Charts */}
        <div className="flex flex-col gap-3">
          <MiniPie title="Fire & Property" data={firePieData}  colors={PIE_COLORS} />
          <MiniPie title="Motor & Car"     data={motorPieData} colors={["#f87171", "#a5b4fc"]} />
        </div>
      </div>

      {/* Table */}
      <PolicyTable
        page={page} setPage={setPage} totalPages={3}
        search={search} setSearch={setSearch}
        extraFilters={<Dropdown label="March 2026" />}
      />
    </div>
  );
}
