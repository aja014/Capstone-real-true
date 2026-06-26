import { useState } from "react";
import { StatCard, PolicyTable } from "./PolicyDistributionShared";

export default function DailyView() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  return (
    <div className="flex flex-col gap-4">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard sub="As of March 24 2026" value="26"         label="Total Policies Today" />
        <StatCard sub="As of March 24 2026" value="14"         label="Fire & Property Policies" />
        <StatCard sub="As of March 24 2026" value="12"         label="Motor & Car Policies" />
        <StatCard sub="As of March 24 2026" value="₱34,123.12" label="Gross Premium Written" target="₱33,040.00" />
      </div>

      {/* Table */}
      <PolicyTable
        page={page} setPage={setPage} totalPages={3}
        search={search} setSearch={setSearch}
      />
    </div>
  );
}
