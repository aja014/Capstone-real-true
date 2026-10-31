import { useState, useEffect, useCallback } from "react";
import { sharedGet } from "../lib/sharedGet";
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
import { StatCard, formatCurrencyPH } from "../components/PolicyDistributionShared";

import { API_BASE_URL } from "../api/config";
const PIE_COLORS = ["#FBBF24", "#FEF3C7"];

// ── QuotationConversionPie ──────────────────────────────────────────────────
// Independent of PolicyDistributionShared's MiniPie — sized back to its
// original (pre-MiniPie-refactor) dimensions: ResponsiveContainer
// width="100%" height={180}, outerRadius={80}. Duplicates (rather than
// imports) the two real fixes MiniPie carries: 0-value-slice label
// suppression, and the all-zero "No data yet" empty state (scaled up to
// match this pie's larger size).
function QuotationConversionPie({ title, data, colors, sub }) {
  const total = data.reduce((sum, d) => sum + (d.value || 0), 0);

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <p className="font-bold text-black text-sm">{title}</p>
        <p className="text-gray-400 text-[10px]">{sub}</p>
      </div>
      <div className="flex flex-col items-center justify-center flex-1 gap-2">
        {total === 0 ? (
          <div style={{ width: "100%", height: 180 }} className="flex items-center justify-center flex-shrink-0">
            <svg width={160} height={160}>
              <circle cx={80} cy={80} r={80} fill="#e5e7eb" />
              <text x={80} y={80} textAnchor="middle" dominantBaseline="central" fontSize={13} fontWeight={700} fill="#9ca3af">
                No data yet
              </text>
            </svg>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={data} dataKey="value" cx="50%" cy="50%" outerRadius={80} labelLine={false}
                label={({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
                  if (!value) return null;
                  const RADIAN = Math.PI / 180;
                  const r = innerRadius + (outerRadius - innerRadius) * 0.5;
                  return <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)}
                    fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={700}>{value}</text>;
                }}>
                {data.map((_, i) => <Cell key={i} fill={colors[i]} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        )}
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: colors[i] }} />
              <span className="text-[10px] text-gray-600">{d.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Overview() {
  const [activeNav, setActiveNav] = useState("Overview");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await sharedGet(`${API_BASE_URL}/stats/overview`, { headers });
      setStats(res.data);
    } catch {
      setError("Failed to load Overview data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // One caption for all four cards: each counts the current calendar month.
  const sub = loading ? "…" : `This Month (${stats?.month_label ?? ""})`;
  const quotationPieSub = loading ? "…" : (stats?.quotation_pie_label ?? "Past 3 Months");
  const quotationPie = stats?.quotation_pie ?? [];
  const yearlyBar = (stats?.yearly_bar ?? []).map((b) => ({
    year: b.label,
    fire: b.fire_count,
    motor: b.motor_count,
  }));
  const monthlyLine = (stats?.monthly_line ?? []).map((m) => ({
    month: m.label,
    fire: m.fire_count,
    motor: m.motor_count,
  }));

  return (
    <div className="min-h-screen bg-yellow-400 p-4 sm:p-6 flex gap-4">
      {/* Sidebar */}
      <div className="hidden md:flex flex-shrink-0">
        <Sidebar activeItem={activeNav} onNavigate={setActiveNav} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {error && <p className="text-red-500 text-xs">{error}</p>}

        {/* Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            sub={sub}
            value={loading ? "…" : formatCurrencyPH(stats?.gross_premium_written, false)}
            label="Gross Premium Written"
          />
          <StatCard
            sub={sub}
            value={loading ? "…" : String(stats?.policies_made ?? 0)}
            label="Policies Made"
          />
          <StatCard
            sub={sub}
            value={loading ? "…" : String(stats?.quotations_offered ?? 0)}
            label="Total Quotation Offered"
          />
          {/* Same basis as Total Quotation Offered: claims (both lines) whose
              Date Reported falls in the current month. */}
          <StatCard
            sub={sub}
            value={loading ? "…" : String(stats?.filed_claims ?? 0)}
            label="Filed Claims"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* Bar Chart */}
          <div className="lg:col-span-2 bg-white rounded-2xl p-5 shadow-sm">
            <h2 className="font-bold text-black text-sm mb-4">Policy Made (Past 4 Years)</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={yearlyBar} barCategoryGap="15%">
                <CartesianGrid vertical={false} stroke="#f3f4f6" />
                <XAxis dataKey="year" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 10, border: "none", fontSize: 12 }}
                  cursor={{ fill: "#f9fafb" }}
                />
                <Bar dataKey="fire" name="Fire & Property" stackId="a" fill="#a5b4fc" />
                <Bar dataKey="motor" name="Motor & Car" stackId="a" fill="#6b9bd2" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="flex items-center gap-4 mt-1 justify-center">
              {[["#a5b4fc", "Fire & Property"], ["#6b9bd2", "Motor & Car"]].map(([c, l]) => (
                <div key={l} className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm" style={{ background: c }} />
                  <span className="text-[10px] text-gray-500">{l}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Pie Chart */}
          <QuotationConversionPie
            title="Quotation vs. Converted Accounts"
            data={quotationPie}
            colors={PIE_COLORS}
            sub={quotationPieSub}
          />
        </div>

        {/* Line Chart: the card grows down to the bottom of the screen (like the tables on Policy
            Distribution and Renewal Ratio). The chart sits in an absolutely positioned box that fills
            the space under the title, so Recharts measures a fixed box and can never stretch the card;
            it keeps at least the old 220 px on short screens. */}
        <div className="bg-white rounded-2xl p-5 shadow-sm flex-1 flex flex-col">
          <h2 className="font-bold text-black text-sm mb-4">Policy Line (Past 6 Months)</h2>
          <div className="relative flex-1 min-h-[220px]">
          <div className="absolute inset-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={monthlyLine}>
              <CartesianGrid stroke="#f3f4f6" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} allowDecimals={false} label={{ value: "count", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#9ca3af" } }} />
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
              />
              <Line
                type="monotone"
                dataKey="fire"
                stroke="#f87171"
                strokeWidth={2}
                dot={{ r: 4, fill: "#f87171", strokeWidth: 0 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
          </div>
          </div>
        </div>

      </div>
    </div>
  );
}
